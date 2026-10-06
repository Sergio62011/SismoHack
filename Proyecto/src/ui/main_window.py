from pathlib import Path
import sys
import re
import unicodedata
from datetime import datetime, timezone
from PySide6.QtCore import QDateTime, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDateTimeEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QDialog,
    QDialogButtonBox 
)

from models.map import Zona
from models.report import Reporte
from services.sistema_sismico import SistemaSismico
from services.historial import Accion
from services.archivo import archivar_rama, previsualizar_archivo
from services.consultas import (
    primeros_k_pendientes,
    eventos_por_magnitud,
    eventos_por_profundidad_y_fecha,
    asociaciones_de_evento,
)
from persistence.json_loader import JsonLoader, ErrorJsonPersistencia
from persistence.json_saver import JsonSaver
from persistence.versiones import (
    ErrorVersionesPersistentes,
    GestorVersiones,
)
from structure.bst import BST
from services.auditoria import verificar_estructura

class DialogoCorregirEvento(QDialog):
    """Modal dialog to edit an active event."""

    def __init__(self, evento, parent=None):
        super().__init__(parent)
        self.evento = evento
        self.setWindowTitle(f"Edit event SIS-{evento.id_evento:06d}")
        self.setMinimumWidth(420)
        self._crear_ui()

    def _crear_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # === Encabezado con info no editable ===
        info = QLabel(
            f"<b>ID:</b> {self.evento.id_evento}<br>"
            f"<b>Current revision:</b> {self.evento.revision}<br>"
            f"<b>Status:</b> {self._estado_en_ingles(self.evento.estado)}<br>"
            f"<b>Current priority:</b> P{self.evento.prioridad}"
        )
        info.setStyleSheet(
            "background: #e8eef4; padding: 10px; border-radius: 5px;"
            "color: #172b4d;"
        )
        layout.addWidget(info)

        # === Formulario editable ===
        form = QFormLayout()
        form.setSpacing(8)

        self.campo_magnitud = QDoubleSpinBox()
        self.campo_magnitud.setRange(-2.0, 10.0)
        self.campo_magnitud.setDecimals(1)
        self.campo_magnitud.setSingleStep(0.1)
        self.campo_magnitud.setValue(self.evento.magnitud)

        self.campo_profundidad = QDoubleSpinBox()
        self.campo_profundidad.setRange(0.0, 700.0)
        self.campo_profundidad.setDecimals(1)
        self.campo_profundidad.setSingleStep(0.1)
        self.campo_profundidad.setValue(self.evento.profundidad)

        self.campo_x = QDoubleSpinBox()
        self.campo_x.setRange(0.0, 1000.0)
        self.campo_x.setDecimals(1)
        self.campo_x.setSingleStep(0.1)
        self.campo_x.setValue(self.evento.x)

        self.campo_y = QDoubleSpinBox()
        self.campo_y.setRange(0.0, 1000.0)
        self.campo_y.setDecimals(1)
        self.campo_y.setSingleStep(0.1)
        self.campo_y.setValue(self.evento.y)

        self.campo_fecha = QDateTimeEdit()
        self.campo_fecha.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.campo_fecha.setCalendarPopup(True)
        self.campo_fecha.setDateTime(
            QDateTime.fromString(
                self.evento.fecha_hora.strftime("%Y-%m-%d %H:%M:%S"),
                "yyyy-MM-dd HH:mm:ss",
            )
        )

        form.addRow("Magnitude", self.campo_magnitud)
        form.addRow("Depth (km)", self.campo_profundidad)
        form.addRow("X coordinate", self.campo_x)
        form.addRow("Y coordinate", self.campo_y)
        form.addRow("Date (UTC)", self.campo_fecha)
        layout.addLayout(form)

        # === Nota ===
        nota = QLabel(
            "Editing this event will increase its revision by 1 and set its "
            "status back to 'pending'."
        )
        nota.setWordWrap(True)
        nota.setStyleSheet("color: #52616f; font-size: 11px;")
        layout.addWidget(nota)

        # === Botones ===
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        botones.button(QDialogButtonBox.StandardButton.Ok).setText("Save changes")
        botones.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancel")
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)

    def datos(self):
        """Devuelve los nuevos datos del evento listos para el servicio."""
        fecha = datetime.strptime(
            self.campo_fecha.dateTime().toString("yyyy-MM-dd HH:mm:ss"),
            "%Y-%m-%d %H:%M:%S",
        ).replace(tzinfo=timezone.utc)
        return {
            "magnitud": self.campo_magnitud.value(),
            "profundidad": self.campo_profundidad.value(),
            "x": self.campo_x.value(),
            "y": self.campo_y.value(),
            "fecha_hora": fecha,
        }

    @staticmethod
    def _estado_en_ingles(estado):
        return {
            "pendiente": "pending",
            "revisado": "reviewed",
            "archivado": "archived",
        }.get(estado, estado)

class VistaArbolConZoom(QGraphicsView):

    def __init__(self, escena, parent=None):
        super().__init__(escena, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.setBackgroundBrush(QBrush(QColor("#fafbfc")))
        self.setMinimumHeight(290)
        self.setStyleSheet(
            "QGraphicsView { background: #fafbfc; border: 1px solid #d8e0e8; }"
        )

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)

class VentanaPrincipal(QMainWindow):
    """Desktop view that uses the existing SismoLab service."""

    def __init__(self):
        super().__init__()
        self.sistema = SistemaSismico()
        # Store persistent versions separately from ordinary JSON files.
        self.gestor_versiones = GestorVersiones(
            self._data_dir() / "versiones"
        )
        # The comparison BST preserves an insertion-load sequence when available.
        self.bst_comparativo = None
        self._crear_ventana()
        self._crear_timer_reloj()
        self._crear_timer_procesamiento()
        self.actualizar_vistas()


    def _crear_timer_reloj(self):
        self.timer_reloj = QTimer(self)
        self.timer_reloj.setInterval(1000)
        self.timer_reloj.timeout.connect(self._tick_reloj)
        self.timer_reloj.start()

    def _tick_reloj(self):
        self.sistema.reloj.avanzar(1)
        self._actualizar_reloj()
    
    def _crear_timer_procesamiento(self):
        self.timer_procesamiento = QTimer(self)
        self.timer_procesamiento.setInterval(800)
        self.timer_procesamiento.timeout.connect(self._procesar_un_paso)

    def _procesar_un_paso(self):
        if not self.sistema.hay_reportes_pendientes():
            self.timer_procesamiento.stop()
            self.boton_procesar_todos.setText("Process entire queue")
            self.statusBar().showMessage("Queue is empty", 3000)
            return
        resultado = self.sistema.procesar_siguiente_reporte()
        self._mostrar_resultados([resultado])
        self.actualizar_vistas()

    def saltar_reloj(self):
        texto = self.campo_salto.dateTime().toString(
            "yyyy-MM-dd HH:mm:ss"
        )
        fecha = datetime.strptime(
            texto, "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
        try:
            self.sistema.saltar_reloj(fecha)
            self.statusBar().showMessage(
                f"Clock moved to {fecha.strftime('%Y-%m-%d %H:%M:%S')}",
                4000,
            )
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))

    def _crear_ventana(self):
        self.setWindowTitle("SismoLab AVL")
        self.resize(1220, 780)
        self.setMinimumSize(980, 640)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(self._crear_encabezado())

        pestanas = QTabWidget()
        pestanas.addTab(self._crear_resumen(), "Overview")
        pestanas.addTab(self._crear_eventos(), "Events")
        pestanas.addTab(self._crear_reportes(), "Reports")
        pestanas.addTab(self._crear_mapa(), "Map and zones")
        pestanas.addTab(self._crear_comparacion(), "AVL vs BST")
        pestanas.addTab(self._crear_historico(), "History")
        pestanas.addTab(self._crear_consultas(), "Queries")
        pestanas.addTab(self._crear_versiones(), "Versions")
        pestanas.addTab(self._crear_auditoria(), "Audit")
        layout.addWidget(pestanas, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("System ready")
        self.statusBar().setStyleSheet(
            "QStatusBar { background: #e8eef4; color: #172b4d; }"
        )

        self.etiqueta_modo = QLabel("Mode: normal")
        self.etiqueta_modo.setStyleSheet(
            "color: #52616f; padding-right: 10px;"
        )
        self.statusBar().addPermanentWidget(self.etiqueta_modo)

        self.setStyleSheet(
            "QMainWindow { background: #f5f7fa; }"
            "QGroupBox { font-weight: 600; border: 1px solid #cdd6df; "
            "border-radius: 6px; margin-top: 10px; padding: 10px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; "
            "padding: 0 4px; }"
            "QPushButton { background: #1967a8; color: white; border: 0; "
            "border-radius: 4px; padding: 7px 11px; }"
            "QPushButton:hover { background: #12568f; }"
            "QPushButton:disabled { background: #9aa6b2; }"
            "QTableWidget { background: white; color: #172b4d; "
            "gridline-color: #d9e0e6; }"
            "QTableWidget::item { color: #172b4d; }"
            "QHeaderView::section { background: #e8eef4; color: #172b4d; "
            "padding: 6px; border: 0; border-bottom: 1px solid #cdd6df; "
            "font-weight: 600; }"
            "QTabBar::tab { padding: 8px 14px; }"
        )

    def _crear_encabezado(self):
        contenedor = QFrame()
        layout = QHBoxLayout(contenedor)
        layout.setContentsMargins(0, 0, 0, 0)

        textos = QVBoxLayout()
        textos.setSpacing(0)
        titulo = QLabel("SismoLab AVL")
        titulo.setStyleSheet(
            "font-size: 24px; font-weight: 700; color: #17324d;"
        )
        subtitulo = QLabel("Earthquake monitoring system")
        subtitulo.setStyleSheet("color: #52616f;")
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        layout.addLayout(textos)
        layout.addStretch()

        self.boton_guardar = QPushButton("Save JSON")
        self.boton_guardar.clicked.connect(self.guardar_json)
        layout.addWidget(self.boton_guardar)

        self.boton_cargar_topologia = QPushButton("Load topology")
        self.boton_cargar_topologia.clicked.connect(self.cargar_json_topologia)
        layout.addWidget(self.boton_cargar_topologia)

        self.boton_cargar_inserciones = QPushButton("Load insertion sequence")
        self.boton_cargar_inserciones.clicked.connect(self.cargar_json_inserciones)
        layout.addWidget(self.boton_cargar_inserciones)

        self.boton_estres = QPushButton("Stress mode")
        self.boton_estres.setCheckable(True)
        self.boton_estres.toggled.connect(self._switch_modo_estres)
        self.boton_estres.setStyleSheet(
            "QPushButton {"
            "   background: #1967a8; color: white;"
            "   border: 0; border-radius: 4px;"
            "   padding: 7px 11px;"
            "}"
            "QPushButton:checked {"
            "   background: #c0392b;"
            "}"
        )
        layout.addWidget(self.boton_estres)

        self.boton_deshacer = QPushButton("Undo")
        self.boton_deshacer.clicked.connect(self.deshacer)
        self.boton_deshacer.setEnabled(False)
        layout.addWidget(self.boton_deshacer)

        self.campo_salto = QDateTimeEdit()
        self.campo_salto.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.campo_salto.setCalendarPopup(True)
        self.campo_salto.setDateTime(self._qdatetime_del_reloj())
        self.campo_salto.setStyleSheet(
            "QDateTimeEdit {"
            "   background: white;"
            "   color: #172b4d;"
            "   border: 1px solid #cdd6df;"
            "   border-radius: 4px;"
            "   padding: 5px 8px;"
            "   min-width: 170px;"
            "}"
            "QDateTimeEdit:focus {"
            "   border: 1px solid #1967a8;"
            "}"
            "QDateTimeEdit::drop-down {"
            "   subcontrol-origin: padding;"
            "   subcontrol-position: center right;"
            "   width: 20px;"
            "   border-left: 1px solid #cdd6df;"
            "   background: #e8eef4;"
            "}"
            "QDateTimeEdit::down-arrow {"
            "   image: none;"
            "   border-left: 4px solid transparent;"
            "   border-right: 4px solid transparent;"
            "   border-top: 6px solid #17324d;"
            "   width: 0;"
            "   height: 0;"
            "}"
        )
        layout.addWidget(self.campo_salto)

        self.boton_saltar = QPushButton("Set clock to this time")
        self.boton_saltar.clicked.connect(self.saltar_reloj)
        layout.addWidget(self.boton_saltar)

        self.etiqueta_reloj = QLabel()
        self.etiqueta_reloj.setStyleSheet(
            "background: #e1f1ed; color: #155d4a; padding: 7px 10px; "
            "border-radius: 4px; font-weight: 600;"
        )
        layout.addWidget(self.etiqueta_reloj)
        return contenedor

    def _crear_resumen(self):
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        metricas = QGroupBox("Scenario status")
        rejilla = QGridLayout(metricas)
        self.etiquetas_resumen = {}
        datos = [
            ("Active events", "eventos"),
            ("AVL height", "altura"),
            ("AVL leaves", "hojas"),
            ("Reports in queue", "cola"),
            ("Accepted corrections", "correcciones"),
            ("Conflicts", "conflictos"),
            ("Confirmations", "confirmaciones"),
            ("Created from reports", "creados"),
        ]
        for indice, (texto, clave) in enumerate(datos):
            tarjeta = QFrame()
            tarjeta.setStyleSheet(
                "QFrame { background: white; border: 1px solid #d8e0e8; "
                "border-radius: 5px; }"
            )
            tarjeta_layout = QVBoxLayout(tarjeta)
            nombre = QLabel(texto)
            nombre.setStyleSheet("color: #52616f;")
            valor = QLabel("0")
            valor.setStyleSheet(
                "font-size: 22px; font-weight: 700; color: #17324d;"
            )
            tarjeta_layout.addWidget(nombre)
            tarjeta_layout.addWidget(valor)
            self.etiquetas_resumen[clave] = valor
            rejilla.addWidget(tarjeta, indice // 4, indice % 4)
        layout.addWidget(metricas)

        grupo_arbol = QGroupBox("AVL tree view")
        arbol_layout = QVBoxLayout(grupo_arbol)
        ayuda = QLabel(
            "Each node shows its ID and priority. Drag to move around. "
            "Hold Ctrl and use the mouse wheel to zoom."
        )
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color: #52616f;")
        arbol_layout.addWidget(ayuda)

        barra_arbol = QHBoxLayout()
        boton_zoom_in = QPushButton("Zoom +")
        boton_zoom_out = QPushButton("Zoom -")
        boton_reset = QPushButton("Reset view")
        boton_zoom_in.clicked.connect(
            lambda: self.vista_arbol.scale(1.2, 1.2)
        )
        boton_zoom_out.clicked.connect(
            lambda: self.vista_arbol.scale(1 / 1.2, 1 / 1.2)
        )
        boton_reset.clicked.connect(self._reset_vista_arbol)
        barra_arbol.addWidget(boton_zoom_in)
        barra_arbol.addWidget(boton_zoom_out)
        barra_arbol.addWidget(boton_reset)
        boton_costo = QPushButton("Show costly searches")
        boton_costo.clicked.connect(self._mostrar_acceso_costoso)
        barra_arbol.addWidget(boton_costo)
        boton_verificar = QPushButton("Check structure")
        boton_verificar.clicked.connect(self.verificar_estructura)
        barra_arbol.addWidget(boton_verificar)
        barra_arbol.addStretch()
        arbol_layout.addLayout(barra_arbol)

        self.escena_arbol = QGraphicsScene(self)
        self.vista_arbol = VistaArbolConZoom(self.escena_arbol)
        arbol_layout.addWidget(self.vista_arbol)
        layout.addWidget(grupo_arbol, 1)

        grupo_orden = QGroupBox("In-order traversal")
        orden_layout = QVBoxLayout(grupo_orden)
        self.texto_inorden = QTextEdit()
        self.texto_inorden.setReadOnly(True)
        self.texto_inorden.setMaximumHeight(90)
        orden_layout.addWidget(self.texto_inorden)
        layout.addWidget(grupo_orden)
        return pagina

    def _crear_eventos(self):
        pagina = QWidget()
        division = QSplitter(Qt.Orientation.Horizontal)
        formulario = QGroupBox("Create event")
        formulario_layout = QVBoxLayout(formulario)
        self.campos_evento = self._crear_formulario(formulario_layout)
        boton_crear = QPushButton("Create event")
        boton_crear.clicked.connect(self.crear_evento)
        formulario_layout.addWidget(boton_crear)
        formulario_layout.addStretch()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        grupo_tabla = QGroupBox("Active events")
        tabla_layout = QVBoxLayout(grupo_tabla)
        self.tabla_eventos = self._crear_tabla(
            ["ID", "Magnitude", "Depth", "Priority", "Revision",
             "Status", "Zone", "Costly"]
        )
        self.tabla_eventos.itemSelectionChanged.connect(
            self._actualizar_botones_evento
        )
        self.tabla_eventos.itemDoubleClicked.connect(
            lambda _item: self.corregir_evento()   # doble clic = corregir
        )
        tabla_layout.addWidget(self.tabla_eventos)
        panel_layout.addWidget(grupo_tabla, 1)

        acciones = QHBoxLayout()

        self.boton_corregir = QPushButton("Edit event")
        self.boton_corregir.clicked.connect(self.corregir_evento)
        self.boton_corregir.setEnabled(False)
        acciones.addWidget(self.boton_corregir)

        self.boton_revisar = QPushButton("Mark as reviewed")
        self.boton_revisar.clicked.connect(self.marcar_revisado)
        self.boton_revisar.setEnabled(False)
        acciones.addWidget(self.boton_revisar)

        self.boton_eliminar = QPushButton("Delete event")
        self.boton_eliminar.setStyleSheet("background: #ae3e3e;")
        self.boton_eliminar.clicked.connect(self.eliminar_evento)
        self.boton_eliminar.setEnabled(False)
        acciones.addWidget(self.boton_eliminar)

        acciones.addStretch()
        panel_layout.addLayout(acciones)
        division.addWidget(formulario)
        division.addWidget(panel)
        division.setSizes([330, 780])
        layout = QVBoxLayout(pagina)
        layout.addWidget(division)
        return pagina

    def _crear_reportes(self):
        pagina = QWidget()
        division = QSplitter(Qt.Orientation.Horizontal)
        formulario = QGroupBox("New station report")
        formulario_layout = QVBoxLayout(formulario)
        self.campos_reporte = self._crear_formulario(formulario_layout, True)
        boton_encolar = QPushButton("Add to queue")
        boton_encolar.clicked.connect(self.encolar_reporte)
        formulario_layout.addWidget(boton_encolar)
        formulario_layout.addStretch()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        grupo_cola = QGroupBox("Report queue (FIFO)")
        cola_layout = QVBoxLayout(grupo_cola)
        self.tabla_reportes = self._crear_tabla(
            ["ID", "Magnitude", "Revision", "Station", "Date (UTC)"]
        )
        cola_layout.addWidget(self.tabla_reportes)
        acciones = QHBoxLayout()
        boton_uno = QPushButton("Process next")
        boton_uno.clicked.connect(self.procesar_siguiente_reporte)
        self.boton_procesar_todos = QPushButton("Process entire queue")
        self.boton_procesar_todos.clicked.connect(self.procesar_todos_los_reportes)
        acciones.addWidget(boton_uno)
        acciones.addWidget(self.boton_procesar_todos)
        acciones.addStretch()
        cola_layout.addLayout(acciones)
        panel_layout.addWidget(grupo_cola, 1)

        grupo_resultado = QGroupBox("Processing result")
        resultado_layout = QVBoxLayout(grupo_resultado)
        self.texto_resultado = QTextEdit()
        self.texto_resultado.setReadOnly(True)
        self.texto_resultado.setMinimumHeight(125)
        resultado_layout.addWidget(self.texto_resultado)
        panel_layout.addWidget(grupo_resultado)
        division.addWidget(formulario)
        division.addWidget(panel)
        division.setSizes([330, 780])
        layout = QVBoxLayout(pagina)
        layout.addWidget(division)
        return pagina

    def _crear_mapa(self):
        pagina = QWidget()
        division = QSplitter(Qt.Orientation.Horizontal)
        formulario = QGroupBox("Add zone")
        formulario_layout = QVBoxLayout(formulario)
        datos = QFormLayout()
        self.nombre_zona = QLineEdit()
        self.nombre_zona.setPlaceholderText("e.g. North City")
        self.x_min_zona = self._campo_decimal(0, 1000)
        self.y_min_zona = self._campo_decimal(0, 1000)
        self.x_max_zona = self._campo_decimal(0, 1000)
        self.y_max_zona = self._campo_decimal(0, 1000)
        self.zona_poblada = QCheckBox("Populated area")
        datos.addRow("Name", self.nombre_zona)
        datos.addRow("Minimum X", self.x_min_zona)
        datos.addRow("Minimum Y", self.y_min_zona)
        datos.addRow("Maximum X", self.x_max_zona)
        datos.addRow("Maximum Y", self.y_max_zona)
        datos.addRow("Type", self.zona_poblada)
        formulario_layout.addLayout(datos)
        boton_agregar = QPushButton("Add zone")
        boton_agregar.clicked.connect(self.agregar_zona)
        formulario_layout.addWidget(boton_agregar)
        leyenda = QLabel("P: populated   N: not populated   E: event")
        leyenda.setWordWrap(True)
        leyenda.setStyleSheet("color: #52616f;")
        formulario_layout.addWidget(leyenda)
        formulario_layout.addStretch()

        grupo_mapa = QGroupBox("Seismic map")
        mapa_layout = QVBoxLayout(grupo_mapa)
        self.tabla_mapa = QTableWidget()
        self.tabla_mapa.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla_mapa.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tabla_mapa.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_mapa.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        mapa_layout.addWidget(self.tabla_mapa)
        division.addWidget(formulario)
        division.addWidget(grupo_mapa)
        division.setSizes([330, 780])
        layout = QVBoxLayout(pagina)
        layout.addWidget(division)
        return pagina

    def _crear_comparacion(self):
        pagina = QWidget()
        layout = QVBoxLayout(pagina)

        explicacion = QLabel(
            "AVL vs BST comparison. The AVL tree is shown as it is stored "
            "in memory. When a JSON file is loaded by insertion sequence, "
            "the BST uses the same sequence. Otherwise, it is rebuilt by "
            "inserting active events in ascending K order."
        )

        explicacion.setStyleSheet("color: #52616f;")
        explicacion.setWordWrap(True)
        layout.addWidget(explicacion)

        barra_botones = QHBoxLayout()
        boton_cargar = QPushButton("Load JSON by insertion sequence")
        boton_cargar.clicked.connect(self.cargar_json_inserciones)
        barra_botones.addWidget(boton_cargar)
        barra_botones.addStretch()
        layout.addLayout(barra_botones)

        metricas = QGroupBox("Structural metrics")
        rejilla = QGridLayout(metricas)
        self.etiquetas_comparacion = {}
        datos = [
            ("AVL height", "avl_altura"),
            ("AVL leaves", "avl_hojas"),
            ("AVL root", "avl_raiz"),
            ("AVL nodes", "avl_nodos"),
            ("BST height", "bst_altura"),
            ("BST leaves", "bst_hojas"),
            ("BST root", "bst_raiz"),
            ("BST nodes", "bst_nodos"),
        ]
        for indice, (texto, clave) in enumerate(datos):
            tarjeta = QFrame()
            tarjeta.setStyleSheet(
                "QFrame { background: white; border: 1px solid #d8e0e8; "
                "border-radius: 5px; }"
            )
            tarjeta_layout = QVBoxLayout(tarjeta)
            nombre = QLabel(texto)
            nombre.setStyleSheet("color: #52616f;")
            valor = QLabel("-")
            valor.setStyleSheet(
                "font-size: 18px; font-weight: 700; color: #17324d;"
            )
            tarjeta_layout.addWidget(nombre)
            tarjeta_layout.addWidget(valor)
            self.etiquetas_comparacion[clave] = valor
            rejilla.addWidget(tarjeta, indice // 4, indice % 4)
        layout.addWidget(metricas)

        arboles = QSplitter(Qt.Orientation.Horizontal)
        grupo_avl = QGroupBox("Current AVL")
        avl_layout = QVBoxLayout(grupo_avl)
        self.escena_avl_comparacion = QGraphicsScene(self)
        self.vista_avl_comparacion = VistaArbolConZoom(
            self.escena_avl_comparacion
        )
        avl_layout.addWidget(self.vista_avl_comparacion)

        grupo_bst = QGroupBox("Unbalanced BST")
        bst_layout = QVBoxLayout(grupo_bst)
        self.escena_bst_comparacion = QGraphicsScene(self)
        self.vista_bst_comparacion = VistaArbolConZoom(
            self.escena_bst_comparacion
        )
        bst_layout.addWidget(self.vista_bst_comparacion)

        arboles.addWidget(grupo_avl)
        arboles.addWidget(grupo_bst)
        arboles.setSizes([600, 600])
        layout.addWidget(arboles, 1)
        return pagina

    def _crear_historico(self):
        pagina = QWidget()
        division = QSplitter(Qt.Orientation.Horizontal)
        self._archivo_previsualizado = None

        archivo = QGroupBox("Branch archiving")
        archivo_layout = QVBoxLayout(archivo)
        ayuda = QLabel(
            "The system archives the largest eligible branch: low-priority "
            "events older than the T limit."
        )
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color: #52616f;")
        archivo_layout.addWidget(ayuda)
        self.etiqueta_previsualizacion_archivo = QLabel(
            "No branch has been checked yet."
        )
        self.etiqueta_previsualizacion_archivo.setWordWrap(True)
        self.etiqueta_previsualizacion_archivo.setStyleSheet(
            "background: white; color: #172b4d; border: 1px solid #d8e0e8; "
            "padding: 8px;"
        )
        archivo_layout.addWidget(self.etiqueta_previsualizacion_archivo)
        boton_previsualizar = QPushButton("Preview archive")
        boton_previsualizar.clicked.connect(self.previsualizar_archivo_historico)
        self.boton_archivar_rama = QPushButton("Archive branch")
        self.boton_archivar_rama.clicked.connect(self.archivar_rama_historico)
        self.boton_archivar_rama.setEnabled(False)
        archivo_layout.addWidget(boton_previsualizar)
        archivo_layout.addWidget(self.boton_archivar_rama)
        archivo_layout.addStretch()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        grupo_tabla = QGroupBox("Archived events")
        tabla_layout = QVBoxLayout(grupo_tabla)
        self.tabla_historico = self._crear_tabla(
            ["ID", "Magnitude", "Priority", "Revision", "Status", "Date (UTC)"]
        )
        self.tabla_historico.itemSelectionChanged.connect(
            self._actualizar_detalle_historico
        )
        tabla_layout.addWidget(self.tabla_historico)
        panel_layout.addWidget(grupo_tabla, 1)

        grupo_detalle = QGroupBox("Archived event details")
        detalle_layout = QVBoxLayout(grupo_detalle)
        self.texto_detalle_historico = QTextEdit()
        self.texto_detalle_historico.setReadOnly(True)
        self.texto_detalle_historico.setMinimumHeight(150)
        detalle_layout.addWidget(self.texto_detalle_historico)
        panel_layout.addWidget(grupo_detalle)

        division.addWidget(archivo)
        division.addWidget(panel)
        division.setSizes([330, 780])
        layout = QVBoxLayout(pagina)
        layout.addWidget(division)
        return pagina

    def _crear_consultas(self):
        pagina = QWidget()
        layout = QVBoxLayout(pagina)

        parametros = QGroupBox("Scenario parameters")
        parametros_layout = QHBoxLayout(parametros)

        self.campo_w = QDoubleSpinBox()
        self.campo_w.setRange(0.1, 100000.0)
        self.campo_w.setDecimals(1)
        self.campo_w.setValue(self.sistema.parametros.w)

        self.campo_r = QDoubleSpinBox()
        self.campo_r.setRange(0.1, 100000.0)
        self.campo_r.setDecimals(1)
        self.campo_r.setValue(self.sistema.parametros.r)

        self.campo_l = QSpinBox()
        self.campo_l.setRange(0, 999999)
        self.campo_l.setValue(self.sistema.parametros.l)

        self.campo_t = QDoubleSpinBox()
        self.campo_t.setRange(0.1, 100000.0)
        self.campo_t.setDecimals(1)
        self.campo_t.setValue(self.sistema.parametros.t)

        parametros_layout.addWidget(QLabel("W (h)"))
        parametros_layout.addWidget(self.campo_w)
        parametros_layout.addWidget(QLabel("R (km)"))
        parametros_layout.addWidget(self.campo_r)
        parametros_layout.addWidget(QLabel("L"))
        parametros_layout.addWidget(self.campo_l)
        parametros_layout.addWidget(QLabel("T (h)"))
        parametros_layout.addWidget(self.campo_t)

        boton_parametros = QPushButton("Apply parameters")
        boton_parametros.clicked.connect(self.aplicar_parametros)
        parametros_layout.addWidget(boton_parametros)
        layout.addWidget(parametros)

        consultas = QSplitter(Qt.Orientation.Horizontal)

        izquierda = QWidget()
        izquierda_layout = QVBoxLayout(izquierda)

        grupo_k = QGroupBox("Top k pending events — descending K")
        grupo_k_layout = QVBoxLayout(grupo_k)
        fila_k = QHBoxLayout()
        self.campo_k_consulta = QSpinBox()
        self.campo_k_consulta.setRange(1, 999999)
        self.campo_k_consulta.setValue(5)
        boton_k = QPushButton("Search")
        boton_k.clicked.connect(self.consultar_primeros_k)
        fila_k.addWidget(QLabel("k:"))
        fila_k.addWidget(self.campo_k_consulta)
        fila_k.addWidget(boton_k)
        grupo_k_layout.addLayout(fila_k)
        self.texto_consulta_k = QTextEdit()
        self.texto_consulta_k.setReadOnly(True)
        grupo_k_layout.addWidget(self.texto_consulta_k)
        izquierda_layout.addWidget(grupo_k, 1)

        grupo_m = QGroupBox("Events by magnitude range")
        grupo_m_layout = QVBoxLayout(grupo_m)
        fila_m = QHBoxLayout()
        self.campo_m_min = self._campo_decimal(-2, 10)
        self.campo_m_max = self._campo_decimal(-2, 10)
        self.campo_m_min.setValue(-2.0)
        self.campo_m_max.setValue(10.0)
        boton_m = QPushButton("Search")
        boton_m.clicked.connect(self.consultar_magnitud)
        fila_m.addWidget(QLabel("Min:"))
        fila_m.addWidget(self.campo_m_min)
        fila_m.addWidget(QLabel("Max:"))
        fila_m.addWidget(self.campo_m_max)
        fila_m.addWidget(boton_m)
        grupo_m_layout.addLayout(fila_m)
        self.texto_consulta_m = QTextEdit()
        self.texto_consulta_m.setReadOnly(True)
        grupo_m_layout.addWidget(self.texto_consulta_m)
        izquierda_layout.addWidget(grupo_m, 1)

        consultas.addWidget(izquierda)

        derecha = QWidget()
        derecha_layout = QVBoxLayout(derecha)

        grupo_pf = QGroupBox("Depth and date range")
        grupo_pf_layout = QVBoxLayout(grupo_pf)
        form_pf = QFormLayout()
        self.campo_profundidad_consulta = self._campo_decimal(0, 700)
        self.campo_profundidad_consulta.setValue(700.0)
        self.campo_fecha_inicio_consulta = QDateTimeEdit()
        self.campo_fecha_fin_consulta = QDateTimeEdit()
        for campo in (self.campo_fecha_inicio_consulta, self.campo_fecha_fin_consulta):
            campo.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            campo.setCalendarPopup(True)
            campo.setDateTime(self._qdatetime_del_reloj())
        form_pf.addRow("Maximum depth (km)", self.campo_profundidad_consulta)
        form_pf.addRow("From (UTC)", self.campo_fecha_inicio_consulta)
        form_pf.addRow("To (UTC)", self.campo_fecha_fin_consulta)
        grupo_pf_layout.addLayout(form_pf)
        boton_pf = QPushButton("Search")
        boton_pf.clicked.connect(self.consultar_profundidad_fecha)
        grupo_pf_layout.addWidget(boton_pf)
        self.texto_consulta_pf = QTextEdit()
        self.texto_consulta_pf.setReadOnly(True)
        grupo_pf_layout.addWidget(self.texto_consulta_pf)
        derecha_layout.addWidget(grupo_pf, 1)

        grupo_a = QGroupBox("Associations")
        grupo_a_layout = QVBoxLayout(grupo_a)
        fila_a = QHBoxLayout()
        self.campo_id_asociaciones = QSpinBox()
        self.campo_id_asociaciones.setRange(1, 999999)
        boton_a = QPushButton("View associations")
        boton_a.clicked.connect(self.consultar_asociaciones)
        fila_a.addWidget(QLabel("ID:"))
        fila_a.addWidget(self.campo_id_asociaciones)
        fila_a.addWidget(boton_a)
        grupo_a_layout.addLayout(fila_a)
        self.texto_asociaciones = QTextEdit()
        self.texto_asociaciones.setReadOnly(True)
        grupo_a_layout.addWidget(self.texto_asociaciones)
        derecha_layout.addWidget(grupo_a, 1)

        consultas.addWidget(derecha)
        consultas.setSizes([600, 600])
        layout.addWidget(consultas, 1)
        return pagina

    def aplicar_parametros(self):
        try:
            cambio = self.sistema.actualizar_parametros(
                w=self.campo_w.value(),
                r=self.campo_r.value(),
                l=self.campo_l.value(),
                t=self.campo_t.value(),
            )
            mensaje = "Parameters updated" if cambio else "No parameter changes"
            self.statusBar().showMessage(mensaje, 4000)
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))

    @staticmethod
    def _texto_eventos_consulta(eventos):
        if not eventos:
            return "No results."
        return "\n".join(
            f"SIS-{evento.id_evento:06d} | K={evento.calcular_clave()} | "
            f"M={evento.magnitud:.1f} | Depth={evento.profundidad:.1f} | "
            f"{DialogoCorregirEvento._estado_en_ingles(evento.estado)}"
            for evento in eventos
        )

    def consultar_primeros_k(self):
        try:
            resultado = primeros_k_pendientes(
                self.sistema, self.campo_k_consulta.value()
            )
            self.texto_consulta_k.setPlainText(
                f"AVL nodes checked: {resultado['nodos_examinados']}\n\n"
                + self._texto_eventos_consulta(resultado["eventos"])
            )
        except ValueError as error:
            self._mostrar_error(str(error))

    def consultar_magnitud(self):
        try:
            resultado = eventos_por_magnitud(
                self.sistema,
                self.campo_m_min.value(),
                self.campo_m_max.value(),
            )
            self.texto_consulta_m.setPlainText(
                f"AVL nodes checked: {resultado['nodos_examinados']}\n\n"
                + self._texto_eventos_consulta(resultado["eventos"])
            )
        except ValueError as error:
            self._mostrar_error(str(error))

    def consultar_profundidad_fecha(self):
        try:
            fecha_inicio = self._leer_fecha(self.campo_fecha_inicio_consulta)
            fecha_fin = self._leer_fecha(self.campo_fecha_fin_consulta)
            resultado = eventos_por_profundidad_y_fecha(
                self.sistema,
                self.campo_profundidad_consulta.value(),
                fecha_inicio,
                fecha_fin,
            )
            self.texto_consulta_pf.setPlainText(
                f"AVL nodes checked: {resultado['nodos_examinados']}\n\n"
                + self._texto_eventos_consulta(resultado["eventos"])
            )
        except ValueError as error:
            self._mostrar_error(str(error))

    def consultar_asociaciones(self):
        try:
            resultado = asociaciones_de_evento(
                self.sistema, self.campo_id_asociaciones.value()
            )
            evento = resultado["evento"]
            referencia = resultado["referencia"]
            lineas = [
                f"Event: SIS-{evento.id_evento:06d} ({DialogoCorregirEvento._estado_en_ingles(resultado['estado'])})",
                f"AVL nodes checked: {resultado['nodos_examinados']}",
                "",
                "Candidates:",
            ]
            if resultado["candidatos"]:
                lineas.extend(
                    f"- SIS-{item['evento'].id_evento:06d} | "
                    f"M={item['evento'].magnitud:.1f} | "
                    f"{DialogoCorregirEvento._estado_en_ingles(item['estado'])}"
                    for item in resultado["candidatos"]
                )
            else:
                lineas.append("- None")

            lineas.append("")
            if referencia is None:
                lineas.append("Selected reference: none")
            else:
                estado_ref = (
                    "active"
                    if referencia.id_evento in self.sistema._eventos_activos
                    else "archived"
                )
                lineas.append(
                    f"Selected reference: SIS-{referencia.id_evento:06d} "
                    f"({estado_ref})"
                )

            lineas.append("")
            lineas.append("Events that use it as a reference:")
            if resultado["referenciados_por"]:
                lineas.extend(
                    f"- SIS-{item['evento'].id_evento:06d} | "
                    f"{DialogoCorregirEvento._estado_en_ingles(item['estado'])}"
                    for item in resultado["referenciados_por"]
                )
            else:
                lineas.append("- None")

            self.texto_asociaciones.setPlainText("\n".join(lineas))
        except ValueError as error:
            self._mostrar_error(str(error))

    def _crear_versiones(self):
        pagina = QWidget()
        division = QSplitter(Qt.Orientation.Horizontal)

        guardar = QGroupBox("Save version")
        guardar_layout = QVBoxLayout(guardar)
        ayuda = QLabel(
            "A version keeps the full system state, including the AVL tree, "
            "history, queue, clock, parameters, and metrics."
        )
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color: #52616f;")
        guardar_layout.addWidget(ayuda)

        form = QFormLayout()
        self.campo_nombre_version = QLineEdit()
        self.campo_nombre_version.setPlaceholderText("e.g. Before the event")
        form.addRow("Name", self.campo_nombre_version)
        guardar_layout.addLayout(form)
        boton_guardar_version = QPushButton("Save version")
        boton_guardar_version.clicked.connect(self.guardar_version)
        guardar_layout.addWidget(boton_guardar_version)
        ruta = QLabel(f"Folder: {self.gestor_versiones.directorio}")
        ruta.setWordWrap(True)
        ruta.setStyleSheet("color: #52616f;")
        guardar_layout.addWidget(ruta)
        guardar_layout.addStretch()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        listado = QGroupBox("Saved versions")
        listado_layout = QVBoxLayout(listado)
        self.tabla_versiones = self._crear_tabla(
            ["Name", "Date (UTC)", "Active", "Historical", "Height", "Mode"]
        )
        self.tabla_versiones.itemSelectionChanged.connect(
            self._actualizar_botones_versiones
        )
        listado_layout.addWidget(self.tabla_versiones)
        acciones = QHBoxLayout()
        self.boton_restaurar_version = QPushButton("Restore version")
        self.boton_restaurar_version.clicked.connect(self.restaurar_version)
        self.boton_eliminar_version = QPushButton("Delete version")
        self.boton_eliminar_version.setStyleSheet("background: #ae3e3e;")
        self.boton_eliminar_version.clicked.connect(self.eliminar_version)
        acciones.addWidget(self.boton_restaurar_version)
        acciones.addWidget(self.boton_eliminar_version)
        acciones.addStretch()
        listado_layout.addLayout(acciones)
        panel_layout.addWidget(listado, 1)

        division.addWidget(guardar)
        division.addWidget(panel)
        division.setSizes([330, 780])
        layout = QVBoxLayout(pagina)
        layout.addWidget(division)
        return pagina
    
    def _crear_auditoria(self):
        # Contenido real de la pestaña
        contenido = QWidget()
        layout = QVBoxLayout(contenido)
        layout.setSpacing(12)

        # === Barra superior con botón y estado ===
        barra = QHBoxLayout()
        boton_verificar = QPushButton("Check structure")
        boton_verificar.clicked.connect(self.verificar_estructura)
        barra.addWidget(boton_verificar)

        self.etiqueta_auditoria = QLabel("Not checked")
        self.etiqueta_auditoria.setStyleSheet(
            "background: #e8eef4; color: #52616f; padding: 9px 14px; "
            "border-radius: 4px; font-weight: 600; font-size: 13px;"
        )
        barra.addWidget(self.etiqueta_auditoria)
        barra.addStretch()
        layout.addLayout(barra)

        # === Errores ===
        grupo_errores = QGroupBox("Errors found")
        errores_layout = QVBoxLayout(grupo_errores)
        self.texto_errores = QTextEdit()
        self.texto_errores.setReadOnly(True)
        self.texto_errores.setMinimumHeight(100)
        self.texto_errores.setMaximumHeight(150)
        errores_layout.addWidget(self.texto_errores)
        layout.addWidget(grupo_errores)

        # === Indicadores ===
        grupo_indicadores = QGroupBox("Metrics")
        indicadores_layout = QGridLayout(grupo_indicadores)
        indicadores_layout.setSpacing(8)
        indicadores_layout.setContentsMargins(10, 16, 10, 10)

        self.etiquetas_auditoria = {}
        campos = [
            ("activos", "Active", 0, 0),
            ("historicos", "Historical", 0, 1),
            ("eliminados", "Eliminated", 0, 2),
            ("altura", "AVL height", 0, 3),
            ("hojas", "Leaves", 0, 4),

            ("rotaciones_realizadas", "Rotations", 1, 0),
            ("casos_ll", "LL", 1, 1),
            ("casos_rr", "RR", 1, 2),
            ("casos_lr", "LR", 1, 3),
            ("casos_rl", "RL", 1, 4),

            ("giros_simples_izquierda", "Left turns", 2, 0),
            ("giros_simples_derecha", "Right turns", 2, 1),
            ("correcciones_aceptadas", "Corrections", 2, 2),
            ("reportes_descartados", "Discarded", 2, 3),
            ("conflictos", "Conflictos", 2, 4),

            ("confirmaciones", "Confirmed", 3, 0),
            ("creados_por_reporte", "Created", 3, 1),
            ("reactivados", "Reactivated", 3, 2),
            ("archivos_masivos", "Bulk archives", 3, 3),
            ("eventos_archivados", "Archived", 3, 4),

            ("por_prioridad_1", "P1", 4, 0),
            ("por_prioridad_2", "P2", 4, 1),
            ("por_prioridad_3", "P3", 4, 2),
            ("pendientes", "Pending", 4, 3),
            ("con_acceso_costoso", "Costly", 4, 4),
        ]

        for clave, etiqueta, fila, columna in campos:
            contenedor = QFrame()
            contenedor.setFixedHeight(60)
            contenedor.setMinimumWidth(130)
            contenedor.setStyleSheet(
                "QFrame {"
                "   background: white;"
                "   border: 1px solid #d8e0e8;"
                "   border-radius: 4px;"
                "}"
                "QFrame QLabel {"
                "   color: #172b4d;"
                "   background: transparent;"
                "}"
            )
            contenedor_layout = QVBoxLayout(contenedor)
            contenedor_layout.setContentsMargins(10, 6, 10, 6)
            contenedor_layout.setSpacing(2)

            nombre = QLabel(etiqueta)
            nombre.setStyleSheet(
                "color: #52616f; font-size: 11px; border: 0; "
                "background: transparent;"
            )

            valor = QLabel("0")
            valor.setStyleSheet(
                "font-size: 18px; font-weight: 700; color: #17324d; "
                "border: 0; background: transparent;"
            )

            contenedor_layout.addWidget(nombre)
            contenedor_layout.addWidget(valor)
            self.etiquetas_auditoria[clave] = valor
            indicadores_layout.addWidget(
                contenedor, fila, columna,
                Qt.AlignmentFlag.AlignTop
            )

        for columna in range(5):
            indicadores_layout.setColumnStretch(columna, 1)

        layout.addWidget(grupo_indicadores)

        # === Recorridos ===
        grupo_recorridos = QGroupBox("Tree traversals")
        recorridos_layout = QVBoxLayout(grupo_recorridos)
        self.texto_recorridos = QTextEdit()
        self.texto_recorridos.setReadOnly(True)
        self.texto_recorridos.setMinimumHeight(110)
        recorridos_layout.addWidget(self.texto_recorridos)
        layout.addWidget(grupo_recorridos)

        self._actualizar_auditoria()

        # === Envolver todo en un scroll ===
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(contenido)
        scroll.setStyleSheet(
            "QScrollArea { border: 0; background: transparent; }"
        )
        return scroll
    
    def verificar_estructura(self):
        reporte = verificar_estructura(self.sistema)

        if reporte["ok"]:
            self.etiqueta_auditoria.setText("Structure is valid")
            self.etiqueta_auditoria.setStyleSheet(
                "background: #d4edda; color: #155d4a; padding: 7px 12px; "
                "border-radius: 4px; font-weight: 600;"
            )
            self.texto_errores.setPlainText("No inconsistencies were found.")
        else:
            n = len(reporte["errores"])
            self.etiqueta_auditoria.setText(f"{n} errors found")
            self.etiqueta_auditoria.setStyleSheet(
                "background: #fdecea; color: #c0392b; padding: 7px 12px; "
                "border-radius: 4px; font-weight: 600;"
            )
            self.texto_errores.setPlainText(
                "\n".join(f"- {self._traducir_mensaje(e)}" for e in reporte["errores"])
            )

        self._pintar_indicadores(reporte["indicadores"])

    def _pintar_indicadores(self, ind):
        valores = {
            "activos": ind["activos"],
            "historicos": ind["historicos"],
            "eliminados": ind["eliminados"],
            "altura": ind["altura"],
            "hojas": ind["hojas"],
            "rotaciones_realizadas": ind["rotaciones_realizadas"],
            "casos_ll": ind["casos_ll"],
            "casos_rr": ind["casos_rr"],
            "casos_lr": ind["casos_lr"],
            "casos_rl": ind["casos_rl"],
            "giros_simples_izquierda": ind["giros_simples_izquierda"],
            "giros_simples_derecha": ind["giros_simples_derecha"],
            "correcciones_aceptadas": ind["correcciones_aceptadas"],
            "reportes_descartados": ind["reportes_descartados"],
            "conflictos": ind["conflictos"],
            "confirmaciones": ind["confirmaciones"],
            "creados_por_reporte": ind["creados_por_reporte"],
            "reactivados": ind["reactivados"],
            "archivos_masivos": ind["archivos_masivos"],
            "eventos_archivados": ind["eventos_archivados"],
            "por_prioridad_1": ind["por_prioridad"].get(1, 0),
            "por_prioridad_2": ind["por_prioridad"].get(2, 0),
            "por_prioridad_3": ind["por_prioridad"].get(3, 0),
            "pendientes": ind["pendientes"],
            "con_acceso_costoso": ind["con_acceso_costoso"],
        }
        for clave, valor in valores.items():
            self.etiquetas_auditoria[clave].setText(str(valor))

        self.texto_recorridos.setPlainText(
            f"In-order:     {ind['inorden']}\n"
            f"Pre-order:    {ind['preorden']}\n"
            f"Post-order:   {ind['postorden']}\n"
            f"By level:     {ind['por_niveles']}\n"
            f"Nodes per level: {ind['nodos_por_nivel']}"
        )
        
    def _actualizar_auditoria(self):
        reporte = verificar_estructura(self.sistema)
        self._pintar_indicadores(reporte["indicadores"])

    def _crear_formulario(self, layout, incluir_revision=False):
        form = QFormLayout()
        campos = {
            "id": QSpinBox(),
            "magnitud": self._campo_decimal(-2, 10),
            "profundidad": self._campo_decimal(0, 700),
            "x": self._campo_decimal(0, 1000),
            "y": self._campo_decimal(0, 1000),
            "fecha": QDateTimeEdit(),
            "estacion": QLineEdit(),
        }
        campos["id"].setRange(1, 999999)
        campos["magnitud"].setValue(5.0)
        campos["profundidad"].setValue(20.0)
        campos["x"].setValue(100.0)
        campos["y"].setValue(100.0)
        campos["fecha"].setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        campos["fecha"].setCalendarPopup(True)
        campos["fecha"].setDateTime(self._qdatetime_del_reloj())
        campos["estacion"].setPlaceholderText("e.g. ST-01")
        form.addRow("ID", campos["id"])
        form.addRow("Magnitude", campos["magnitud"])
        form.addRow("Depth (km)", campos["profundidad"])
        form.addRow("X coordinate", campos["x"])
        form.addRow("Y coordinate", campos["y"])
        form.addRow("Date (UTC)", campos["fecha"])
        if incluir_revision:
            campos["revision"] = QSpinBox()
            campos["revision"].setRange(1, 999999)
            form.addRow("Revision", campos["revision"])
        form.addRow("Station", campos["estacion"])
        layout.addLayout(form)
        return campos

    @staticmethod
    def _campo_decimal(minimo, maximo):
        campo = QDoubleSpinBox()
        campo.setRange(minimo, maximo)
        campo.setDecimals(1)
        campo.setSingleStep(0.1)
        return campo

    @staticmethod
    def _crear_tabla(encabezados):
        tabla = QTableWidget(0, len(encabezados))
        tabla.setHorizontalHeaderLabels(encabezados)
        tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        tabla.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tabla.verticalHeader().setVisible(False)
        tabla.setStyleSheet(
            "QTableWidget { color: #172b4d; background: white; }"
            "QTableWidget::item { color: #172b4d; }"
        )
        return tabla

    def _qdatetime_del_reloj(self):
        return QDateTime.fromString(
            self.sistema.reloj.instante.strftime("%Y-%m-%d %H:%M:%S"),
            "yyyy-MM-dd HH:mm:ss",
        )

    @staticmethod
    def _leer_fecha(campo):
        texto = campo.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        return datetime.strptime(texto, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

    def _leer_datos(self, campos):
        return {
            "id_evento": campos["id"].value(),
            "magnitud": campos["magnitud"].value(),
            "profundidad": campos["profundidad"].value(),
            "x": campos["x"].value(),
            "y": campos["y"].value(),
            "fecha_hora": self._leer_fecha(campos["fecha"]),
            "estacion": campos["estacion"].text().strip(),
        }

    def crear_evento(self):
        try:
            evento = self.sistema.crear_evento(**self._leer_datos(self.campos_evento))
            self.statusBar().showMessage(f"Event {evento.id_evento} created", 4000)
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))
            
    def corregir_evento(self):
        """Abre el diálogo de edit para el evento selected."""
        event_id = self._id_seleccionado()
        if event_id is None:
            return

        evento = self.sistema.buscar_por_id(event_id)
        if evento is None:
            self._mostrar_error(
                f"Event {event_id} is not active."
            )
            return

        dialogo = DialogoCorregirEvento(evento, parent=self)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        datos = dialogo.datos()

        # Si no cambió nada, no hace falta corregir
        if (
            round(evento.magnitud, 1) == round(datos["magnitud"], 1)
            and round(evento.profundidad, 1) == round(datos["profundidad"], 1)
            and round(evento.x, 1) == round(datos["x"], 1)
            and round(evento.y, 1) == round(datos["y"], 1)
            and evento.fecha_hora == datos["fecha_hora"]
        ):
            self.statusBar().showMessage(
                "No changes: the event was not modified.", 4000
            )
            return

        try:
            self.sistema.corregir_evento(event_id, **datos)
            self.statusBar().showMessage(
                f"Event {event_id} updated "
                f"(new revision: {self.sistema.buscar_por_id(event_id).revision})",
                5000,
            )
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))

    def marcar_revisado(self):
        event_id = self._id_seleccionado()
        if event_id is None:
            return
        try:
            self.sistema.marcar_revisado(event_id)
            self.statusBar().showMessage(f"Event {event_id} marked as reviewed", 4000)
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))

    def deshacer(self):
        if self.timer_procesamiento.isActive():
            self.timer_procesamiento.stop()
            self.boton_procesar_todos.setText("Process entire queue")
        descripcion = self.sistema.descripcion_ultima_accion()
        if descripcion is None:
            self.statusBar().showMessage("There are no actions to undo", 4000)
            return
        if not self.sistema.deshacer():
            self.statusBar().showMessage("The action could not be undone", 4000)
            return
        self.statusBar().showMessage(
            f"Undone: {self._traducir_mensaje(descripcion)}", 4000
        )
        self.actualizar_vistas()

    def _switch_modo_estres(self, activo):
        try:
            if activo:
                self.sistema.activar_modo_estres()
                self.statusBar().showMessage("Stress mode enabled", 4000)
            else:
                pausado = False
                if self.timer_procesamiento.isActive():
                    self.timer_procesamiento.stop()
                    self.boton_procesar_todos.setText("Process entire queue")
                    pausado = True

                costo = self.sistema.desactivar_modo_estres()
                prefijo = "Processing paused. " if pausado else ""
                self.statusBar().showMessage(
                    f"{prefijo}Balance restored: height from "
                    f"{costo['altura_antes']} to {costo['altura_despues']}, "
                    f"{costo['giros']} rotations, "
                    f"{costo['nodos_visitados']} nodes visited, "
                    f"{costo['pasadas']} passes",
                    10000,
                )
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))
            self._actualizar_boton_estres()

    def _actualizar_boton_estres(self):
        en_estres = self.sistema.en_modo_estres()
        self.boton_estres.blockSignals(True)
        self.boton_estres.setChecked(en_estres)
        if en_estres:
            self.boton_estres.setText("Stress mode: ON")
        else:
            self.boton_estres.setText("Stress mode")
        self.boton_estres.blockSignals(False)

    def _actualizar_indicador_modo(self):
        if self.sistema.en_modo_estres():
            self.etiqueta_modo.setText("Mode: STRESS")
            self.etiqueta_modo.setStyleSheet(
                "color: #c0392b; font-weight: 600; padding-right: 10px;"
            )
        else:
            self.etiqueta_modo.setText("Mode: normal")
            self.etiqueta_modo.setStyleSheet(
                "color: #52616f; padding-right: 10px;"
            )

    def eliminar_evento(self):
        event_id = self._id_seleccionado()
        if event_id is None:
            return
        respuesta = QMessageBox.question(
            self, "Delete event",
            f"Event {event_id} cannot be restored after deletion. Delete it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        try:
            self.sistema.eliminar_evento(event_id)
            self.statusBar().showMessage(f"Event {event_id} deleted", 4000)
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))

    def encolar_reporte(self):
        try:
            datos = self._leer_datos(self.campos_reporte)
            reporte = Reporte(revision=self.campos_reporte["revision"].value(), **datos)
            self.sistema.encolar_reporte(reporte)
            self.statusBar().showMessage("Report added to the queue", 4000)
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))

    def procesar_siguiente_reporte(self):
        self._mostrar_resultados([self.sistema.procesar_siguiente_reporte()])
        self.actualizar_vistas()

    def procesar_todos_los_reportes(self):
        if self.timer_procesamiento.isActive():
            self.timer_procesamiento.stop()
            self.boton_procesar_todos.setText("Process entire queue")
            self.statusBar().showMessage("Processing paused", 3000)
            return
        if not self.sistema.hay_reportes_pendientes():
            self.statusBar().showMessage("There are no pending reports", 3000)
            return
        self.timer_procesamiento.start()
        self.boton_procesar_todos.setText("Pause processing")
        self.statusBar().showMessage("Processing queue...", 3000)

    def agregar_zona(self):
        nombre = self.nombre_zona.text().strip()
        if not nombre:
            self._mostrar_error("A zone name is required.")
            return
        if (self.x_min_zona.value() > self.x_max_zona.value()
                or self.y_min_zona.value() > self.y_max_zona.value()):
            self._mostrar_error(
                "Minimum values cannot be greater than maximum values."
            )
            return
        zona = Zona(
            nombre, self.x_min_zona.value(), self.y_min_zona.value(),
            self.x_max_zona.value(), self.y_max_zona.value(),
            self.zona_poblada.isChecked(),
        )
        try:
            afectados = self.sistema.agregar_zona(zona)
            self.statusBar().showMessage(
                f"Zone '{zona.nombre}' added. "
                f"{afectados} events changed priority.",
                5000,
            )
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))

    def actualizar_vistas(self):
        self._actualizar_reloj()
        self._actualizar_resumen()
        self._actualizar_tabla_eventos()
        self._actualizar_tabla_reportes()
        self._actualizar_mapa()
        self._actualizar_comparacion()
        self._actualizar_tabla_historico()
        self._actualizar_estado_archivo()
        self._actualizar_botones_evento()
        self._actualizar_boton_deshacer()
        self._actualizar_boton_estres()
        self._actualizar_indicador_modo()
        self._actualizar_tabla_versiones()
        self._actualizar_auditoria()

    def _actualizar_boton_deshacer(self):
        puede = self.sistema.puede_deshacer()
        self.boton_deshacer.setEnabled(puede)
        if puede:
            descripcion = self.sistema.descripcion_ultima_accion()
            f"Undo: {self._traducir_mensaje(descripcion)}", 5000
        else:
            self.boton_deshacer.setToolTip("There are no actions to undo")

    def _actualizar_tabla_versiones(self):
        try:
            versiones = self.gestor_versiones.listar()
        except ErrorVersionesPersistentes as error:
            self.tabla_versiones.setRowCount(0)
            self.statusBar().showMessage(f"Invalid version catalog: {self._traducir_mensaje(str(error))}", 8000)
            self._actualizar_botones_versiones()
            return

        self.tabla_versiones.setRowCount(len(versiones))
        for fila, version in enumerate(versiones):
            valores = [
                version["name"],
                version["created_at"].replace("T", " ").replace("Z", ""),
                version["active_events"],
                version["historical_events"],
                version["avl_height"],
                "Stress" if version["stress_mode"] else "Normal",
            ]
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                item.setForeground(QBrush(QColor("#172b4d")))
                if columna == 0:
                    item.setData(Qt.ItemDataRole.UserRole, version["name"])
                self.tabla_versiones.setItem(fila, columna, item)
        self._actualizar_botones_versiones()

    def _actualizar_botones_versiones(self):
        seleccionada = self._version_seleccionada() is not None
        self.boton_restaurar_version.setEnabled(seleccionada)
        self.boton_eliminar_version.setEnabled(seleccionada)

    def _version_seleccionada(self):
        fila = self.tabla_versiones.currentRow()
        if fila < 0:
            return None
        item = self.tabla_versiones.item(fila, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _actualizar_reloj(self):
        instante = self.sistema.reloj.instante
        self.etiqueta_reloj.setText(
            "UTC clock: " + instante.strftime("%Y-%m-%d %H:%M:%S")
        )
        if not self.campo_salto.hasFocus():
            self.campo_salto.setDateTime(self._qdatetime_del_reloj())

    def _actualizar_resumen(self):
        metricas = self.sistema.metricas
        valores = {
            "eventos": self.sistema.avl.size(),
            "altura": self.sistema.avl.height(),
            "hojas": self.sistema.avl.number_of_leaves(),
            "cola": self.sistema.cantidad_reportes_pendientes(),
            "correcciones": metricas["correcciones_aceptadas"],
            "conflictos": metricas["conflictos"],
            "confirmaciones": metricas["confirmaciones"],
            "creados": metricas["creados_por_reporte"],
        }
        for clave, valor in valores.items():
            self.etiquetas_resumen[clave].setText(str(valor))
        eventos = self.sistema.avl.in_order()
        self._actualizar_grafico_arbol()
        if not eventos:
            self.texto_inorden.setPlainText("There are no events in the AVL yet.")
            return
        lineas = [
            f"ID {evento.id_evento} | key {evento.calcular_clave()} | "
            f"{DialogoCorregirEvento._estado_en_ingles(evento.estado)}"
            for evento in eventos
        ]
        self.texto_inorden.setPlainText("\n".join(lineas))

    def _actualizar_tabla_eventos(self):
        eventos = self.sistema.avl.in_order()
        self.tabla_eventos.setRowCount(len(eventos))
        for fila, evento in enumerate(eventos):
            valores = [
                evento.id_evento, f"{evento.magnitud:.1f}",
                f"{evento.profundidad:.1f}", f"P{evento.prioridad}",
                evento.revision, DialogoCorregirEvento._estado_en_ingles(evento.estado),
                "Populated" if evento.en_zona_poblada else "Not populated",
                "Yes" if evento.acceso_costoso else "No",
            ]
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                item.setForeground(QBrush(QColor("#172b4d")))
                if columna == 0:
                    item.setData(Qt.ItemDataRole.UserRole, evento.id_evento)
                if columna == 7 and evento.acceso_costoso:
                    item.setForeground(QBrush(QColor("#c0392b")))
                self.tabla_eventos.setItem(fila, columna, item)

    def _actualizar_tabla_reportes(self):
        reportes = list(self.sistema.cola_reportes)
        self.tabla_reportes.setRowCount(len(reportes))
        for fila, reporte in enumerate(reportes):
            valores = [
                reporte.id_evento, f"{float(reporte.magnitud):.1f}",
                reporte.revision, reporte.estacion,
                reporte.fecha_hora.strftime("%Y-%m-%d %H:%M"),
            ]
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                item.setForeground(QBrush(QColor("#172b4d")))
                self.tabla_reportes.setItem(fila, columna, item)

    def _actualizar_mapa(self):
        matriz = self.sistema.mapa.crear_matriz_con_eventos(self.sistema.avl.in_order())
        filas = self.sistema.mapa.filas
        columnas = self.sistema.mapa.columnas
        self.tabla_mapa.setRowCount(filas)
        self.tabla_mapa.setColumnCount(columnas)
        colores = {
            ".": QColor("#ffffff"), "P": QColor("#bfe3d5"),
            "N": QColor("#e8d9a8"), "E": QColor("#e56a5d"),
        }
        for fila in range(filas):
            for columna in range(columnas):
                simbolo = matriz[fila][columna]
                item = QTableWidgetItem(simbolo)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setForeground(QBrush(QColor("#172b4d")))
                item.setBackground(colores[simbolo])
                self.tabla_mapa.setItem(fila, columna, item)
        self.tabla_mapa.setHorizontalHeaderLabels([str(i) for i in range(columnas)])
        self.tabla_mapa.setVerticalHeaderLabels([str(i) for i in range(filas)])

    def _actualizar_comparacion(self):
        avl = self.sistema.avl
        bst = self._obtener_bst_comparativo()

        valores = {
            "avl_altura": avl.height(),
            "avl_hojas": avl.number_of_leaves(),
            "avl_raiz": avl.root.event.id_evento if avl.root else "-",
            "avl_nodos": avl.size(),
            "bst_altura": bst.height(),
            "bst_hojas": bst.number_of_leaves(),
            "bst_raiz": bst.root.event.id_evento if bst.root else "-",
            "bst_nodos": bst.size(),
        }
        for clave, valor in valores.items():
            self.etiquetas_comparacion[clave].setText(str(valor))
        self._dibujar_arbol_comparativo(
            self.escena_avl_comparacion, avl.root, "AVL"
        )
        self._dibujar_arbol_comparativo(
            self.escena_bst_comparacion, bst.root, "BST"
        )
        QTimer.singleShot(
            0,
            lambda: self._encuadrar_escena(
                self.vista_avl_comparacion, self.escena_avl_comparacion
            ),
        )
        QTimer.singleShot(
            0,
            lambda: self._encuadrar_escena(
                self.vista_bst_comparacion, self.escena_bst_comparacion
            ),
        )

    def _obtener_bst_comparativo(self):
        claves_avl = [
            evento.calcular_clave() for evento in self.sistema.avl.in_order()
        ]
        if self.bst_comparativo is not None:
            claves_bst = [
                evento.calcular_clave()
                for evento in self.bst_comparativo.in_order()
            ]
            if claves_bst == claves_avl:
                return self.bst_comparativo

        bst = BST()
        for evento in self.sistema.avl.in_order():
            bst.insert(evento.copia())
        self.bst_comparativo = bst
        return bst

    @staticmethod
    def _encuadrar_escena(vista, escena):
        rectangulo = escena.itemsBoundingRect().adjusted(-30, -25, 30, 35)
        if rectangulo.isEmpty():
            rectangulo = escena.sceneRect()
        if rectangulo.isEmpty():
            return
        vista.resetTransform()
        vista.fitInView(rectangulo, Qt.AspectRatioMode.KeepAspectRatio)

    def _dibujar_arbol_comparativo(self, escena, raiz, nombre_arbol):
        escena.clear()
        if raiz is None:
            texto = escena.addText(f"There are no nodes in the {nombre_arbol}")
            texto.setDefaultTextColor(QColor("#52616f"))
            texto.setPos(20, 20)
            escena.setSceneRect(0, 0, 500, 120)
            return

        nodos = []

        def contar(nodo):
            if nodo is None:
                return 0
            return 1 + contar(nodo.left) + contar(nodo.right)

        cantidad = contar(raiz)
        ancho_total = max(900.0, 145.0 * cantidad)
        posiciones = {}
        separacion_y = 105.0

        def asignar_posiciones(nodo, nivel, minimo, maximo):
            if nodo is None:
                return
            x = (minimo + maximo) / 2.0
            y = 55.0 + nivel * separacion_y
            posiciones[id(nodo)] = (x, y)
            nodos.append(nodo)
            asignar_posiciones(nodo.left, nivel + 1, minimo, x)
            asignar_posiciones(nodo.right, nivel + 1, x, maximo)

        asignar_posiciones(raiz, 0, 80.0, ancho_total - 80.0)
        enlace = QPen(QColor("#8aa0b8"), 2)
        for nodo in nodos:
            x, y = posiciones[id(nodo)]
            for hijo in (nodo.left, nodo.right):
                if hijo is None:
                    continue
                hijo_x, hijo_y = posiciones[id(hijo)]
                enlace_curvo = QPainterPath()
                enlace_curvo.moveTo(x, y + 30)
                enlace_curvo.cubicTo(
                    x, y + 55, hijo_x, hijo_y - 55, hijo_x, hijo_y - 30
                )
                escena.addPath(enlace_curvo, enlace)

        if nombre_arbol == "AVL":
            fondo, borde = QColor("#dcecf8"), QColor("#1967a8")
        else:
            fondo, borde = QColor("#fff1cf"), QColor("#aa6d00")
        for nodo in nodos:
            x, y = posiciones[id(nodo)]
            escena.addRect(
                x - 62, y - 30, 124, 60,
                QPen(borde, 2), QBrush(fondo),
            )
            etiqueta = (
                f"ID {nodo.event.id_evento}\n"
                f"K={nodo.event.calcular_clave()}\n"
                f"h={nodo.height}  fb={nodo.balance_factor}"
            )
            texto = escena.addText(etiqueta)
            texto.setDefaultTextColor(QColor("#172b4d"))
            fuente = texto.font()
            fuente.setPointSize(8)
            texto.setFont(fuente)
            rectangulo = texto.boundingRect()
            texto.setPos(x - rectangulo.width() / 2, y - rectangulo.height() / 2)
        rectangulo = escena.itemsBoundingRect().adjusted(-40, -35, 40, 50)
        escena.setSceneRect(rectangulo)
        # Fit the complete tree inside its view.
        vista = (
            self.vista_avl_comparacion
            if nombre_arbol == "AVL"
            else self.vista_bst_comparacion
        )
        vista.resetTransform()
        vista.fitInView(rectangulo, Qt.AspectRatioMode.KeepAspectRatio)

    def _actualizar_tabla_historico(self):
        eventos = sorted(
            self.sistema._historicos.values(), key=lambda evento: evento.id_evento
        )
        self.tabla_historico.setRowCount(len(eventos))
        for fila, evento in enumerate(eventos):
            valores = [
                evento.id_evento,
                f"{evento.magnitud:.1f}",
                f"P{evento.prioridad}",
                evento.revision,
                DialogoCorregirEvento._estado_en_ingles(evento.estado),
                evento.fecha_hora.strftime("%Y-%m-%d %H:%M:%S"),
            ]
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                item.setForeground(QBrush(QColor("#172b4d")))
                if columna == 0:
                    item.setData(Qt.ItemDataRole.UserRole, evento.id_evento)
                self.tabla_historico.setItem(fila, columna, item)
        self._actualizar_detalle_historico()

    def _actualizar_estado_archivo(self):
        try:
            resultado = previsualizar_archivo(self.sistema)
        except Exception as error:
            self._archivo_previsualizado = None
            self.boton_archivar_rama.setEnabled(False)
            self.etiqueta_previsualizacion_archivo.setText(
                f"Could not check the archive: {self._traducir_mensaje(str(error))}"
            )
            return

        self._archivo_previsualizado = resultado
        self.boton_archivar_rama.setEnabled(resultado["elegible"])
        if resultado["elegible"]:
            self.etiqueta_previsualizacion_archivo.setText(
                f"Branch is ready to archive\n\n"
                f"Root: SIS-{resultado['raiz'].id_evento:06d}\n"
                f"Depth: {resultado['profundidad']}\n"
                f"Events: {resultado['cantidad']}\n"
                f"IDs: {', '.join(map(str, sorted(resultado['ids'])))}"
            )
            return

        eventos = list(self.sistema._eventos_activos.values())
        prioridad_baja = [evento for evento in eventos if evento.prioridad == 1]
        antiguos = [
            evento for evento in prioridad_baja
            if self.sistema.reloj.antiguedad_horas(evento.fecha_hora)
            > self.sistema.parametros.t
        ]
        self.etiqueta_previsualizacion_archivo.setText(
            "There is no eligible branch to archive.\n\n"
            f"Active events: {len(eventos)}\n"
            f"Low priority: {len(prioridad_baja)}\n"
            f"Low priority older than T: {len(antiguos)}\n"
            f"Current T: {self.sistema.parametros.t:.1f} hours"
        )

    def _actualizar_detalle_historico(self):
        fila = self.tabla_historico.currentRow()
        if fila < 0:
            self.texto_detalle_historico.setPlainText(
                "Select an archived event to view its details."
            )
            return
        item = self.tabla_historico.item(fila, 0)
        if item is None:
            return
        event_id = item.data(Qt.ItemDataRole.UserRole)
        evento = self.sistema._historicos.get(event_id)
        if evento is None:
            return
        referencia = evento.referencia if evento.referencia is not None else "None"
        texto = (
            f"ID: {evento.id_evento}\n"
            f"Key: {evento.calcular_clave()}\n"
            f"Magnitude: {evento.magnitud:.1f}\n"
            f"Depth: {evento.profundidad:.1f} km\n"
            f"Epicenter: ({evento.x:.1f}, {evento.y:.1f})\n"
            f"Date (UTC): {evento.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Revision: {evento.revision}\n"
            f"Status: {DialogoCorregirEvento._estado_en_ingles(evento.estado)}\n"
            f"Stations: {', '.join(sorted(evento.estaciones)) or '-'}\n"
            f"Reference: {referencia}\n"
            f"Referenced by: {', '.join(map(str, sorted(evento.referenciado_por))) or '-'}"
        )
        self.texto_detalle_historico.setPlainText(texto)

    def previsualizar_archivo_historico(self):
        self._actualizar_estado_archivo()

    def archivar_rama_historico(self):
        resultado = previsualizar_archivo(self.sistema)
        if not resultado["elegible"]:
            self.previsualizar_archivo_historico()
            return
        respuesta = QMessageBox.question(
            self,
            "Archive branch",
            f"{resultado['cantidad']} events will be archived: "
            f"{', '.join(map(str, sorted(resultado['ids'])))}.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        try:
            resultado = archivar_rama(self.sistema)
        except ValueError as error:
            self._mostrar_error(str(error))
            return
        self._archivo_previsualizado = None
        self.boton_archivar_rama.setEnabled(False)
        mensaje = f"Archived branch rooted at event {resultado['raiz'].id_evento}."
        self.etiqueta_previsualizacion_archivo.setText(mensaje)
        self.statusBar().showMessage(mensaje, 5000)
        self.actualizar_vistas()

    def _actualizar_grafico_arbol(self):
        self.escena_arbol.clear()
        raiz = self.sistema.avl.root
        if raiz is None:
            texto = self.escena_arbol.addText("There are no nodes in the AVL yet")
            texto.setDefaultTextColor(QColor("#52616f"))
            texto.setPos(20, 20)
            self.escena_arbol.setSceneRect(0, 0, 500, 120)
            return

        cantidad = self.sistema.avl.size()
        ancho_total = max(1200.0, 150.0 * cantidad)
        margen_x = 70.0
        separacion_y = 110.0
        radio = 30.0

        posiciones = {}

        def asignar_posiciones(nodo, nivel, x_min, x_max):
            if nodo is None:
                return
            x = (x_min + x_max) / 2.0
            y = 70.0 + nivel * separacion_y
            posiciones[id(nodo)] = (x, y)
            asignar_posiciones(nodo.left, nivel + 1, x_min, x)
            asignar_posiciones(nodo.right, nivel + 1, x, x_max)

        asignar_posiciones(raiz, 0, margen_x, ancho_total - margen_x)

        colores_prioridad = {
            3: ("#fdecea", "#c0392b"),
            2: ("#fef5e7", "#b9770e"),
            1: ("#eafaf1", "#1e8449"),
        }

        enlace_pen = QPen(QColor("#8aa0b8"), 2)
        enlace_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        def dibujar_enlaces(nodo):
            if nodo is None:
                return
            x, y = posiciones[id(nodo)]
            for hijo in (nodo.left, nodo.right):
                if hijo is not None:
                    hx, hy = posiciones[id(hijo)]
                    path = QPainterPath()
                    path.moveTo(x, y + radio - 4)
                    path.cubicTo(
                        x, y + separacion_y * 0.6,
                        hx, hy - separacion_y * 0.6,
                        hx, hy - radio + 4,
                    )
                    self.escena_arbol.addPath(path, enlace_pen)
            dibujar_enlaces(nodo.left)
            dibujar_enlaces(nodo.right)

        dibujar_enlaces(raiz)

        def dibujar_nodos(nodo):
            if nodo is None:
                return

            x, y = posiciones[id(nodo)]
    
            if self.sistema.en_modo_estres():
                fondo, borde = "#c3c3c3", "#ae6c65"
            else:
                fondo, borde = colores_prioridad.get(
                    nodo.event.prioridad, ("#dcecf8", "#1967a8")
                )

            self.escena_arbol.addEllipse(
                x - radio, y - radio,
                radio * 2, radio * 2,
                QPen(QColor(borde), 2),
                QBrush(QColor(fondo)),
            )

            etiqueta = f"ID {nodo.event.id_evento}\nP={nodo.event.prioridad}"
            texto = self.escena_arbol.addText(etiqueta)
            texto.setDefaultTextColor(QColor("#172b4d"))
            fuente = texto.font()
            fuente.setPointSize(9)
            texto.setFont(fuente)
            rect_texto = texto.boundingRect()
            texto.setPos(
                x - rect_texto.width() / 2,
                y - rect_texto.height() / 2,
            )

            dibujar_nodos(nodo.left)
            dibujar_nodos(nodo.right)

        dibujar_nodos(raiz)

        rectangulo = self.escena_arbol.itemsBoundingRect().adjusted(
            -60, -40, 60, 120
        )
        self.escena_arbol.setSceneRect(rectangulo)

    def _reset_vista_arbol(self):
        self.vista_arbol.resetTransform()
        rect = self.escena_arbol.itemsBoundingRect().adjusted(
            -40, -30, 40, 30
        )
        if rect.isEmpty():
            rect = self.escena_arbol.sceneRect()
        self.vista_arbol.fitInView(
            rect, Qt.AspectRatioMode.KeepAspectRatio
        )

    def _actualizar_botones_evento(self):
        hay_seleccion = self._id_seleccionado() is not None
        self.boton_corregir.setEnabled(hay_seleccion)
        self.boton_revisar.setEnabled(hay_seleccion)
        self.boton_eliminar.setEnabled(hay_seleccion)

    def _id_seleccionado(self):
        fila = self.tabla_eventos.currentRow()
        if fila < 0:
            return None
        item = self.tabla_eventos.item(fila, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _mostrar_resultados(self, resultados):
        decisions = {
            "rechazado": "rejected",
            "reactivado": "reactivated",
            "archivado_ignorado": "archive ignored",
            "creado": "created",
            "corregido": "updated",
            "confirmado": "confirmed",
            "conflicto": "conflict",
            "antiguo": "outdated",
        }
        lineas = []
        for indice, resultado in enumerate(resultados, start=1):
            evento = resultado.get("evento")
            evento_texto = f"Event: {evento.id_evento}" if evento else "Event: -"
            rotaciones = resultado.get("rotaciones", []) or ["none"]
            lineas.append(
                f"Step {indice}: {decisions.get(resultado['decision'], resultado['decision'])}\n"
                f"{self._traducir_mensaje(resultado['mensaje'])}\n"
                f"{evento_texto}\nRotations: {', '.join(rotaciones)}"
            )
        self.texto_resultado.setPlainText("\n\n".join(lineas))
        self.statusBar().showMessage("Report processing complete", 4000)

    # =========================================================
    # PERSISTENT VERSIONS
    # =========================================================

    def guardar_version(self):
        nombre = self.campo_nombre_version.text()
        try:
            version = self.gestor_versiones.guardar(nombre, self.sistema)
        except ErrorVersionesPersistentes as error:
            self._mostrar_error(str(error))
            return
        except ValueError as error:
            self._mostrar_error(str(error))
            return

        self.campo_nombre_version.clear()
        self.actualizar_vistas()
        self.statusBar().showMessage(
            f"Version '{version['name']}' saved", 5000
        )

    def restaurar_version(self):
        nombre = self._version_seleccionada()
        if nombre is None:
            return
        respuesta = QMessageBox.question(
            self,
            "Restore version",
            f"The current state will be replaced with version '{nombre}'.\n"
            "You can undo this restore.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        estado_antes = self.sistema._snapshot()
        try:
            nuevo_sistema = self.gestor_versiones.restaurar(
                nombre, sistema_actual=self.sistema
            )
        except ErrorVersionesPersistentes as error:
            self._mostrar_error(str(error))
            return

        nuevo_sistema.historial.registro_accion(
            Accion(f"restaurar_version {nombre}", estado_antes)
        )
        self.sistema = nuevo_sistema
        self.bst_comparativo = None
        self.actualizar_vistas()
        self.statusBar().showMessage(
            f"Version '{nombre}' restored", 5000
        )

    def eliminar_version(self):
        nombre = self._version_seleccionada()
        if nombre is None:
            return
        respuesta = QMessageBox.question(
            self,
            "Delete version",
            f"Version '{nombre}' will be deleted permanently.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        try:
            self.gestor_versiones.eliminar(nombre)
        except ErrorVersionesPersistentes as error:
            self._mostrar_error(str(error))
            return
        self.actualizar_vistas()
        self.statusBar().showMessage(
            f"Version '{nombre}' deleted", 5000
        )
        
    # =========================================================
    # PERSISTENCIA: guardar y cargar JSON
    # =========================================================

    @staticmethod
    def _data_dir():
        raiz = Path(__file__).resolve().parent.parent.parent
        carpeta = raiz / "data"
        carpeta.mkdir(exist_ok=True)
        return carpeta

    def _seleccionar_archivo_json(self, titulo):
        ruta, _ = QFileDialog.getOpenFileName(
            self,
            titulo,
            str(self._data_dir()),
            "JSON files (*.json *.JSON);;All files (*)",
        )
        return ruta


    def guardar_json(self):
        ruta_sugerida = str(self._data_dir() / "sismolab_estado.json")
        ruta, _ = QFileDialog.getSaveFileName(
            self,
            "Save system state",
            ruta_sugerida,
            "JSON files (*.json)",
        )
        if not ruta:
            return

        try:
            destino = JsonSaver.guardar(self.sistema, ruta)
            self.statusBar().showMessage(
                f"Guardado en: {destino}", 6000
            )
            QMessageBox.information(
                self, "Save complete",
                f"State saved to:\n{destino}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Save error",
                f"Could not save the file:\n{self._traducir_mensaje(str(e))}",
            )

    def cargar_json_topologia(self):
        ruta = self._seleccionar_archivo_json("Load topology from JSON")
        if not ruta:
            return

        try:
            nuevo_sistema = JsonLoader.cargar_topologia(
                ruta, sistema_actual=self.sistema
            )
        except ErrorJsonPersistencia as e:
            QMessageBox.critical(
                self, "Invalid JSON",
                f"Could not load the file:\n\n{self._traducir_mensaje(str(e))}\n\n"
                f"The current system was not changed.",
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self, "Unexpected error",
                f"An error occurred while loading:\n{self._traducir_mensaje(str(e))}\n\n"
                f"The current system was not changed.",
            )
            return

        self.sistema = nuevo_sistema
        self.bst_comparativo = None
        self.actualizar_vistas()
        self.statusBar().showMessage(
            f"Topology loaded from: {ruta}", 6000
        )
        QMessageBox.information(
            self, "Load complete",
            f"Scenario restored from:\n{ruta}\n\n"
            f"Active events: {self.sistema.avl.size()}\n"
            f"AVL height: {self.sistema.avl.height()}\n"
            f"Stress mode: {'on' if self.sistema.en_modo_estres() else 'off'}",
        )

    def cargar_json_inserciones(self):
        ruta = self._seleccionar_archivo_json(
            "Load by insertion sequence from JSON"
        )
        if not ruta:
            return

        try:
            sistema_nuevo, bst = JsonLoader.cargar_por_inserciones(ruta)
        except ErrorJsonPersistencia as e:
            QMessageBox.critical(
                self, "Invalid JSON",
                f"Could not load the file:\n\n{e}\n\n"
                f"The current system was not changed.",
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self, "Unexpected error",
                f"An error occurred while loading:\n{self._traducir_mensaje(str(e))}",
            )
            return

        # Keep the BST built by the insertion loader for the comparison view.
        self.bst_comparativo = bst
        self.sistema = sistema_nuevo
        self.actualizar_vistas()

        inorden_avl = [e.id_evento for e in sistema_nuevo.avl.in_order()]
        inorden_bst = [e.id_evento for e in bst.in_order()]

        mensaje = (
            f"File: {ruta}\n\n"
            f"=== AVL (balanced) ===\n"
            f"  Height:  {sistema_nuevo.avl.height()}\n"
            f"  Nodes:   {sistema_nuevo.avl.size()}\n"
            f"  Leaves:   {sistema_nuevo.avl.number_of_leaves()}\n"
            f"  Root:    {sistema_nuevo.avl.root.event.id_evento if sistema_nuevo.avl.root else '-'}\n\n"
            f"=== BST (unbalanced) ===\n"
            f"  Height:  {bst.height()}\n"
            f"  Nodes:   {bst.size()}\n"
            f"  Leaves:   {bst.number_of_leaves()}\n"
            f"  Root:    {bst.root.event.id_evento if bst.root else '-'}\n\n"
            f"AVL in-order == BST in-order: "
            f"{'YES' if inorden_avl == inorden_bst else 'NO'}"
        )

        QMessageBox.information(self, "AVL vs BST comparison", mensaje)
        self.statusBar().showMessage(
            f"Insertion sequence loaded from: {ruta}. "
            f"Open the 'AVL vs BST' tab to view the trees.", 8000
        )
    
    def _mostrar_acceso_costoso(self):
        eventos = self.sistema.eventos_con_acceso_costoso()
        if not eventos:
            QMessageBox.information(
                self, "Costly searches",
                "There are no high-priority events with costly searches."
            )
            return
        lineas = []
        for item in eventos:
            evento = item["evento"]
            lineas.append(
                f"ID {evento.id_evento} | P{evento.prioridad} | "
            f"M{evento.magnitud:.1f} | Depth {item['profundidad']} | "
            f"L={item['limite']} | visited {item['nodos_visitados']}"
            )
        QMessageBox.information(
            self, "Events with costly searches",
            "\n".join(lineas)
        )

    def _mostrar_error(self, mensaje):
        QMessageBox.warning(self, "Invalid input", self._traducir_mensaje(mensaje))

    @staticmethod
    def _traducir_mensaje(mensaje):
        words = {
            "el": "the", "la": "the", "los": "the", "las": "the",
            "un": "a", "una": "a", "de": "of", "del": "of the",
            "en": "in", "con": "with", "por": "by", "para": "for",
            "y": "and", "o": "or", "no": "not", "evento": "event",
            "eventos": "events", "estacion": "station", "identificador": "identifier",
            "revision": "revision", "magnitud": "magnitude", "profundidad": "depth",
            "fecha": "date", "zona": "zone", "zonas": "zones", "valor": "value",
            "valores": "values", "nombre": "name", "estado": "status",
            "referencia": "reference", "activo": "active", "activos": "active",
            "historical": "historical", "eliminado": "deleted", "deleted": "deleted",
            "archivo": "archive", "rama": "branch", "arbol": "tree", "json": "JSON",
            "invalido": "invalid", "invalida": "invalid", "obligatorio": "required",
            "obligatoria": "required", "vacio": "empty", "vacia": "empty",
            "falta": "missing", "faltan": "missing", "debe": "must", "puede": "can",
            "ser": "be", "mayor": "greater", "menor": "less", "maximo": "maximum",
            "minimo": "minimum", "positivo": "positive", "positiva": "positive",
            "numero": "number", "entero": "integer", "texto": "text",
            "duplicado": "duplicated", "duplicada": "duplicated", "existe": "exists",
            "inesperado": "unexpected", "error": "error", "cargar": "load",
            "carga": "load", "guardar": "save", "modificado": "changed",
            "modificada": "changed", "actual": "current", "sistema": "system",
            "compatible": "compatible", "campo": "field", "campos": "fields",
            "esquema": "schema", "version": "version", "altura": "height",
            "factor": "factor", "raiz": "root", "nodo": "node", "nodos": "nodes",
            "padre": "parent", "ciclo": "cycle", "estructura": "structure",
            "requerido": "required", "requerida": "required", "estaciones": "stations",
            "admite": "allows", "decimal": "decimal", "decimales": "decimals",
            "hora": "time", "reloj": "clock", "posterior": "later", "anterior": "earlier",
            "selected": "selected", "seleccionada": "selected", "archivado": "archived",
            "reportes": "reports", "reporte": "report", "pendiente": "pending",
            "reactivado": "reactivated", "reactivada": "reactivated",
            "corregido": "updated", "corregida": "updated", "confirmado": "confirmed",
            "confirmada": "confirmed", "rechazado": "rejected", "rechazada": "rejected",
            "descartado": "discarded", "descartada": "discarded", "desde": "from",
            "misma": "same", "mismo": "same", "datos": "data", "distinto": "different",
            "distintos": "different", "menor": "less", "que": "than", "una": "a",
            "por": "by", "con": "with", "mas": "more", "fue": "was",
            "distintos": "different", "distintas": "different", "misma": "same", "mismo": "same",
            "limite": "limit", "limites": "limits", "poblada": "populated",
            "coordenada": "coordinate", "coordenadas": "coordinates", "encontrado": "found",
            "encontrada": "found", "correcto": "correct", "valido": "valid", "valida": "valid",
            "esperado": "expected", "esperada": "expected", "almacenado": "stored",
            "almacenada": "stored", "fuera": "outside", "topologia": "topology",
            "mas": "more", "menos": "less", "conservar": "keep", "contiene": "contains",
            "requiere": "requires", "deben": "must", "tener": "have", "entre": "between",
            "linea": "line", "mensaje": "message", "procesado": "processed", "cola": "queue",
        }
        normalized = unicodedata.normalize("NFD", str(mensaje))
        normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")

        def replace_word(match):
            word = match.group(0)
            translated = words.get(word.lower(), word)
            return translated.capitalize() if word[:1].isupper() else translated

        return re.sub(r"[A-Za-z]+", replace_word, normalized)


def ejecutar_aplicacion():
    """Starts the desktop application."""
    app = QApplication.instance() or QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    return app.exec()
