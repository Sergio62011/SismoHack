from pathlib import Path
import sys
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
            self.boton_procesar_todos.setText("Procesar toda la cola")
            self.statusBar().showMessage("Cola vacía", 3000)
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
                f"Reloj saltó a {fecha.strftime('%Y-%m-%d %H:%M:%S')}",
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
        pestanas.addTab(self._crear_resumen(), "Resumen")
        pestanas.addTab(self._crear_eventos(), "Eventos")
        pestanas.addTab(self._crear_reportes(), "Reportes")
        pestanas.addTab(self._crear_mapa(), "Mapa y zonas")
        pestanas.addTab(self._crear_comparacion(), "AVL vs BST")
        pestanas.addTab(self._crear_historico(), "Histórico")
        pestanas.addTab(self._crear_consultas(), "Consultas")
        pestanas.addTab(self._crear_versiones(), "Versiones")
        pestanas.addTab(self._crear_auditoria(), "Auditoría")
        layout.addWidget(pestanas, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Sistema listo")
        self.statusBar().setStyleSheet(
            "QStatusBar { background: #e8eef4; color: #172b4d; }"
        )

        self.etiqueta_modo = QLabel("Modo: normal")
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
        subtitulo = QLabel("Observatorio sismico")
        subtitulo.setStyleSheet("color: #52616f;")
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        layout.addLayout(textos)
        layout.addStretch()

        self.boton_guardar = QPushButton("Guardar JSON")
        self.boton_guardar.clicked.connect(self.guardar_json)
        layout.addWidget(self.boton_guardar)

        self.boton_cargar_topologia = QPushButton("Cargar topología")
        self.boton_cargar_topologia.clicked.connect(self.cargar_json_topologia)
        layout.addWidget(self.boton_cargar_topologia)

        self.boton_cargar_inserciones = QPushButton("Cargar inserciones")
        self.boton_cargar_inserciones.clicked.connect(self.cargar_json_inserciones)
        layout.addWidget(self.boton_cargar_inserciones)

        self.boton_estres = QPushButton("Modo estres")
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

        self.boton_deshacer = QPushButton("Deshacer")
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

        self.boton_saltar = QPushButton("Saltar a esta hora")
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
        metricas = QGroupBox("Estado del escenario")
        rejilla = QGridLayout(metricas)
        self.etiquetas_resumen = {}
        datos = [
            ("Eventos activos", "eventos"),
            ("Altura AVL", "altura"),
            ("Hojas AVL", "hojas"),
            ("Reportes en cola", "cola"),
            ("Correcciones aceptadas", "correcciones"),
            ("Conflictos", "conflictos"),
            ("Confirmaciones", "confirmaciones"),
            ("Creados por reporte", "creados"),
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

        grupo_arbol = QGroupBox("Vista grafica del AVL")
        arbol_layout = QVBoxLayout(grupo_arbol)
        ayuda = QLabel(
            "Cada nodo muestra: ID y prioridad. "
            "Arrastra con el mouse para desplazarte. Ctrl + rueda para zoom."
        )
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color: #52616f;")
        arbol_layout.addWidget(ayuda)

        barra_arbol = QHBoxLayout()
        boton_zoom_in = QPushButton("Zoom +")
        boton_zoom_out = QPushButton("Zoom -")
        boton_reset = QPushButton("Reset vista")
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
        boton_costo = QPushButton("Ver acceso costoso")
        boton_costo.clicked.connect(self._mostrar_acceso_costoso)
        barra_arbol.addWidget(boton_costo)
        boton_verificar = QPushButton("Verificar estructura")
        boton_verificar.clicked.connect(self.verificar_estructura)
        barra_arbol.addWidget(boton_verificar)
        barra_arbol.addStretch()
        arbol_layout.addLayout(barra_arbol)

        self.escena_arbol = QGraphicsScene(self)
        self.vista_arbol = VistaArbolConZoom(self.escena_arbol)
        arbol_layout.addWidget(self.vista_arbol)
        layout.addWidget(grupo_arbol, 1)

        grupo_orden = QGroupBox("Orden inorder")
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
        formulario = QGroupBox("Crear evento")
        formulario_layout = QVBoxLayout(formulario)
        self.campos_evento = self._crear_formulario(formulario_layout)
        boton_crear = QPushButton("Crear evento")
        boton_crear.clicked.connect(self.crear_evento)
        formulario_layout.addWidget(boton_crear)
        formulario_layout.addStretch()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        grupo_tabla = QGroupBox("Eventos activos")
        tabla_layout = QVBoxLayout(grupo_tabla)
        self.tabla_eventos = self._crear_tabla(["ID", "Magnitud", "Prof.", "Prioridad", "Revision", "Estado", "Zona", "Costo"]
        )
        self.tabla_eventos.itemSelectionChanged.connect(self._actualizar_botones_evento)
        tabla_layout.addWidget(self.tabla_eventos)
        panel_layout.addWidget(grupo_tabla, 1)
        acciones = QHBoxLayout()
        self.boton_revisar = QPushButton("Marcar como revisado")
        self.boton_revisar.clicked.connect(self.marcar_revisado)
        self.boton_eliminar = QPushButton("Eliminar evento")
        self.boton_eliminar.setStyleSheet("background: #ae3e3e;")
        self.boton_eliminar.clicked.connect(self.eliminar_evento)
        acciones.addWidget(self.boton_revisar)
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
        formulario = QGroupBox("Nuevo reporte de estacion")
        formulario_layout = QVBoxLayout(formulario)
        self.campos_reporte = self._crear_formulario(formulario_layout, True)
        boton_encolar = QPushButton("Agregar a la cola")
        boton_encolar.clicked.connect(self.encolar_reporte)
        formulario_layout.addWidget(boton_encolar)
        formulario_layout.addStretch()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        grupo_cola = QGroupBox("Cola FIFO de reportes")
        cola_layout = QVBoxLayout(grupo_cola)
        self.tabla_reportes = self._crear_tabla(
            ["ID", "Magnitud", "Revision", "Estacion", "Fecha UTC"]
        )
        cola_layout.addWidget(self.tabla_reportes)
        acciones = QHBoxLayout()
        boton_uno = QPushButton("Procesar siguiente")
        boton_uno.clicked.connect(self.procesar_siguiente_reporte)
        self.boton_procesar_todos = QPushButton("Procesar toda la cola")
        self.boton_procesar_todos.clicked.connect(self.procesar_todos_los_reportes)
        acciones.addWidget(boton_uno)
        acciones.addWidget(self.boton_procesar_todos)
        acciones.addStretch()
        cola_layout.addLayout(acciones)
        panel_layout.addWidget(grupo_cola, 1)

        grupo_resultado = QGroupBox("Resultado del procesamiento")
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
        formulario = QGroupBox("Agregar zona")
        formulario_layout = QVBoxLayout(formulario)
        datos = QFormLayout()
        self.nombre_zona = QLineEdit()
        self.nombre_zona.setPlaceholderText("Ej. Ciudad Norte")
        self.x_min_zona = self._campo_decimal(0, 1000)
        self.y_min_zona = self._campo_decimal(0, 1000)
        self.x_max_zona = self._campo_decimal(0, 1000)
        self.y_max_zona = self._campo_decimal(0, 1000)
        self.zona_poblada = QCheckBox("Zona poblada")
        datos.addRow("Nombre", self.nombre_zona)
        datos.addRow("X minima", self.x_min_zona)
        datos.addRow("Y minima", self.y_min_zona)
        datos.addRow("X maxima", self.x_max_zona)
        datos.addRow("Y maxima", self.y_max_zona)
        datos.addRow("Tipo", self.zona_poblada)
        formulario_layout.addLayout(datos)
        boton_agregar = QPushButton("Agregar zona")
        boton_agregar.clicked.connect(self.agregar_zona)
        formulario_layout.addWidget(boton_agregar)
        leyenda = QLabel("P: poblada   N: no poblada   E: evento")
        leyenda.setWordWrap(True)
        leyenda.setStyleSheet("color: #52616f;")
        formulario_layout.addWidget(leyenda)
        formulario_layout.addStretch()

        grupo_mapa = QGroupBox("Mapa sismico")
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
            "Comparación AVL vs BST. El AVL se muestra tal como está en "
            "memoria. El BST se construye con la misma secuencia de "
            "inserciones cuando se carga un JSON por inserciones; en caso "
            "contrario, se reconstruye insertando los eventos activos en "
            "orden ascendente de K."
        )

        explicacion.setStyleSheet("color: #52616f;")
        explicacion.setWordWrap(True)
        layout.addWidget(explicacion)

        barra_botones = QHBoxLayout()
        boton_cargar = QPushButton("Cargar JSON por inserciones")
        boton_cargar.clicked.connect(self.cargar_json_inserciones)
        barra_botones.addWidget(boton_cargar)
        barra_botones.addStretch()
        layout.addLayout(barra_botones)

        metricas = QGroupBox("Métricas estructurales")
        rejilla = QGridLayout(metricas)
        self.etiquetas_comparacion = {}
        datos = [
            ("AVL altura", "avl_altura"),
            ("AVL hojas", "avl_hojas"),
            ("AVL raíz", "avl_raiz"),
            ("AVL nodos", "avl_nodos"),
            ("BST altura", "bst_altura"),
            ("BST hojas", "bst_hojas"),
            ("BST raíz", "bst_raiz"),
            ("BST nodos", "bst_nodos"),
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
        grupo_avl = QGroupBox("AVL temporal")
        avl_layout = QVBoxLayout(grupo_avl)
        self.escena_avl_comparacion = QGraphicsScene(self)
        self.vista_avl_comparacion = VistaArbolConZoom(
            self.escena_avl_comparacion
        )
        avl_layout.addWidget(self.vista_avl_comparacion)

        grupo_bst = QGroupBox("BST sin balanceo")
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

        archivo = QGroupBox("Archivo de rama")
        archivo_layout = QVBoxLayout(archivo)
        ayuda = QLabel(
            "El sistema archiva la mayor rama elegible: eventos de prioridad "
            "baja con antigüedad superior al límite T."
        )
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color: #52616f;")
        archivo_layout.addWidget(ayuda)
        self.etiqueta_previsualizacion_archivo = QLabel(
            "Aún no se ha evaluado una rama."
        )
        self.etiqueta_previsualizacion_archivo.setWordWrap(True)
        self.etiqueta_previsualizacion_archivo.setStyleSheet(
            "background: white; color: #172b4d; border: 1px solid #d8e0e8; "
            "padding: 8px;"
        )
        archivo_layout.addWidget(self.etiqueta_previsualizacion_archivo)
        boton_previsualizar = QPushButton("Previsualizar archivo")
        boton_previsualizar.clicked.connect(self.previsualizar_archivo_historico)
        self.boton_archivar_rama = QPushButton("Archivar rama")
        self.boton_archivar_rama.clicked.connect(self.archivar_rama_historico)
        self.boton_archivar_rama.setEnabled(False)
        archivo_layout.addWidget(boton_previsualizar)
        archivo_layout.addWidget(self.boton_archivar_rama)
        archivo_layout.addStretch()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        grupo_tabla = QGroupBox("Eventos archivados")
        tabla_layout = QVBoxLayout(grupo_tabla)
        self.tabla_historico = self._crear_tabla(
            ["ID", "Magnitud", "Prioridad", "Revision", "Estado", "Fecha UTC"]
        )
        self.tabla_historico.itemSelectionChanged.connect(
            self._actualizar_detalle_historico
        )
        tabla_layout.addWidget(self.tabla_historico)
        panel_layout.addWidget(grupo_tabla, 1)

        grupo_detalle = QGroupBox("Detalle del evento archivado")
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

        parametros = QGroupBox("Parámetros del escenario")
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

        boton_parametros = QPushButton("Aplicar parámetros")
        boton_parametros.clicked.connect(self.aplicar_parametros)
        parametros_layout.addWidget(boton_parametros)
        layout.addWidget(parametros)

        consultas = QSplitter(Qt.Orientation.Horizontal)

        izquierda = QWidget()
        izquierda_layout = QVBoxLayout(izquierda)

        grupo_k = QGroupBox("Primeros k pendientes — K descendente")
        grupo_k_layout = QVBoxLayout(grupo_k)
        fila_k = QHBoxLayout()
        self.campo_k_consulta = QSpinBox()
        self.campo_k_consulta.setRange(1, 999999)
        self.campo_k_consulta.setValue(5)
        boton_k = QPushButton("Consultar")
        boton_k.clicked.connect(self.consultar_primeros_k)
        fila_k.addWidget(QLabel("k:"))
        fila_k.addWidget(self.campo_k_consulta)
        fila_k.addWidget(boton_k)
        grupo_k_layout.addLayout(fila_k)
        self.texto_consulta_k = QTextEdit()
        self.texto_consulta_k.setReadOnly(True)
        grupo_k_layout.addWidget(self.texto_consulta_k)
        izquierda_layout.addWidget(grupo_k, 1)

        grupo_m = QGroupBox("Eventos por intervalo de magnitud")
        grupo_m_layout = QVBoxLayout(grupo_m)
        fila_m = QHBoxLayout()
        self.campo_m_min = self._campo_decimal(-2, 10)
        self.campo_m_max = self._campo_decimal(-2, 10)
        self.campo_m_min.setValue(-2.0)
        self.campo_m_max.setValue(10.0)
        boton_m = QPushButton("Consultar")
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

        grupo_pf = QGroupBox("Profundidad y rango de fechas")
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
        form_pf.addRow("Profundidad máx. (km)", self.campo_profundidad_consulta)
        form_pf.addRow("Desde UTC", self.campo_fecha_inicio_consulta)
        form_pf.addRow("Hasta UTC", self.campo_fecha_fin_consulta)
        grupo_pf_layout.addLayout(form_pf)
        boton_pf = QPushButton("Consultar")
        boton_pf.clicked.connect(self.consultar_profundidad_fecha)
        grupo_pf_layout.addWidget(boton_pf)
        self.texto_consulta_pf = QTextEdit()
        self.texto_consulta_pf.setReadOnly(True)
        grupo_pf_layout.addWidget(self.texto_consulta_pf)
        derecha_layout.addWidget(grupo_pf, 1)

        grupo_a = QGroupBox("Asociaciones")
        grupo_a_layout = QVBoxLayout(grupo_a)
        fila_a = QHBoxLayout()
        self.campo_id_asociaciones = QSpinBox()
        self.campo_id_asociaciones.setRange(1, 999999)
        boton_a = QPushButton("Consultar asociaciones")
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
            mensaje = "Parámetros actualizados" if cambio else "Sin cambios en los parámetros"
            self.statusBar().showMessage(mensaje, 4000)
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))

    @staticmethod
    def _texto_eventos_consulta(eventos):
        if not eventos:
            return "Sin resultados."
        return "\n".join(
            f"SIS-{evento.id_evento:06d} | K={evento.calcular_clave()} | "
            f"M={evento.magnitud:.1f} | H={evento.profundidad:.1f} | "
            f"{evento.estado}"
            for evento in eventos
        )

    def consultar_primeros_k(self):
        try:
            resultado = primeros_k_pendientes(
                self.sistema, self.campo_k_consulta.value()
            )
            self.texto_consulta_k.setPlainText(
                f"Nodos AVL examinados: {resultado['nodos_examinados']}\n\n"
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
                f"Nodos AVL examinados: {resultado['nodos_examinados']}\n\n"
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
                f"Nodos AVL examinados: {resultado['nodos_examinados']}\n\n"
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
                f"Evento: SIS-{evento.id_evento:06d} ({resultado['estado']})",
                f"Nodos AVL examinados: {resultado['nodos_examinados']}",
                "",
                "Candidatos:",
            ]
            if resultado["candidatos"]:
                lineas.extend(
                    f"- SIS-{item['evento'].id_evento:06d} | "
                    f"M={item['evento'].magnitud:.1f} | {item['estado']}"
                    for item in resultado["candidatos"]
                )
            else:
                lineas.append("- Ninguno")

            lineas.append("")
            if referencia is None:
                lineas.append("Referencia elegida: ninguna")
            else:
                estado_ref = (
                    "activo"
                    if referencia.id_evento in self.sistema._eventos_activos
                    else "archivado"
                )
                lineas.append(
                    f"Referencia elegida: SIS-{referencia.id_evento:06d} "
                    f"({estado_ref})"
                )

            lineas.append("")
            lineas.append("Eventos que lo utilizan como referencia:")
            if resultado["referenciados_por"]:
                lineas.extend(
                    f"- SIS-{item['evento'].id_evento:06d} | {item['estado']}"
                    for item in resultado["referenciados_por"]
                )
            else:
                lineas.append("- Ninguno")

            self.texto_asociaciones.setPlainText("\n".join(lineas))
        except ValueError as error:
            self._mostrar_error(str(error))

    def _crear_versiones(self):
        pagina = QWidget()
        division = QSplitter(Qt.Orientation.Horizontal)

        guardar = QGroupBox("Guardar versión")
        guardar_layout = QVBoxLayout(guardar)
        ayuda = QLabel(
            "Una versión conserva todo el estado operativo, incluida la "
            "topología AVL, histórico, cola, reloj, parámetros y métricas."
        )
        ayuda.setWordWrap(True)
        ayuda.setStyleSheet("color: #52616f;")
        guardar_layout.addWidget(ayuda)

        form = QFormLayout()
        self.campo_nombre_version = QLineEdit()
        self.campo_nombre_version.setPlaceholderText("Ej. Antes de la ráfaga")
        form.addRow("Nombre", self.campo_nombre_version)
        guardar_layout.addLayout(form)
        boton_guardar_version = QPushButton("Guardar versión")
        boton_guardar_version.clicked.connect(self.guardar_version)
        guardar_layout.addWidget(boton_guardar_version)
        ruta = QLabel(f"Carpeta: {self.gestor_versiones.directorio}")
        ruta.setWordWrap(True)
        ruta.setStyleSheet("color: #52616f;")
        guardar_layout.addWidget(ruta)
        guardar_layout.addStretch()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        listado = QGroupBox("Versiones guardadas")
        listado_layout = QVBoxLayout(listado)
        self.tabla_versiones = self._crear_tabla(
            ["Nombre", "Fecha UTC", "Activos", "Históricos", "Altura", "Modo"]
        )
        self.tabla_versiones.itemSelectionChanged.connect(
            self._actualizar_botones_versiones
        )
        listado_layout.addWidget(self.tabla_versiones)
        acciones = QHBoxLayout()
        self.boton_restaurar_version = QPushButton("Restaurar versión")
        self.boton_restaurar_version.clicked.connect(self.restaurar_version)
        self.boton_eliminar_version = QPushButton("Eliminar versión")
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
        boton_verificar = QPushButton("Verificar estructura")
        boton_verificar.clicked.connect(self.verificar_estructura)
        barra.addWidget(boton_verificar)

        self.etiqueta_auditoria = QLabel("Sin verificar")
        self.etiqueta_auditoria.setStyleSheet(
            "background: #e8eef4; color: #52616f; padding: 9px 14px; "
            "border-radius: 4px; font-weight: 600; font-size: 13px;"
        )
        barra.addWidget(self.etiqueta_auditoria)
        barra.addStretch()
        layout.addLayout(barra)

        # === Errores ===
        grupo_errores = QGroupBox("Errores encontrados")
        errores_layout = QVBoxLayout(grupo_errores)
        self.texto_errores = QTextEdit()
        self.texto_errores.setReadOnly(True)
        self.texto_errores.setMinimumHeight(100)
        self.texto_errores.setMaximumHeight(150)
        errores_layout.addWidget(self.texto_errores)
        layout.addWidget(grupo_errores)

        # === Indicadores ===
        grupo_indicadores = QGroupBox("Indicadores")
        indicadores_layout = QGridLayout(grupo_indicadores)
        indicadores_layout.setSpacing(8)
        indicadores_layout.setContentsMargins(10, 16, 10, 10)

        self.etiquetas_auditoria = {}
        campos = [
            ("activos", "Activos", 0, 0),
            ("historicos", "Históricos", 0, 1),
            ("eliminados", "Eliminados", 0, 2),
            ("altura", "Altura AVL", 0, 3),
            ("hojas", "Hojas", 0, 4),

            ("rotaciones_realizadas", "Rotaciones", 1, 0),
            ("casos_ll", "LL", 1, 1),
            ("casos_rr", "RR", 1, 2),
            ("casos_lr", "LR", 1, 3),
            ("casos_rl", "RL", 1, 4),

            ("giros_simples_izquierda", "Giros izq.", 2, 0),
            ("giros_simples_derecha", "Giros der.", 2, 1),
            ("correcciones_aceptadas", "Correcciones", 2, 2),
            ("reportes_descartados", "Descartados", 2, 3),
            ("conflictos", "Conflictos", 2, 4),

            ("confirmaciones", "Confirm.", 3, 0),
            ("creados_por_reporte", "Creados", 3, 1),
            ("reactivados", "Reactivados", 3, 2),
            ("archivos_masivos", "Arch. masivos", 3, 3),
            ("eventos_archivados", "Archivados", 3, 4),

            ("por_prioridad_1", "P1", 4, 0),
            ("por_prioridad_2", "P2", 4, 1),
            ("por_prioridad_3", "P3", 4, 2),
            ("pendientes", "Pendientes", 4, 3),
            ("con_acceso_costoso", "Costoso", 4, 4),
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
        grupo_recorridos = QGroupBox("Recorridos")
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
            self.etiqueta_auditoria.setText("Estructura válida")
            self.etiqueta_auditoria.setStyleSheet(
                "background: #d4edda; color: #155d4a; padding: 7px 12px; "
                "border-radius: 4px; font-weight: 600;"
            )
            self.texto_errores.setPlainText(
                "No se encontraron inconsistencias."
            )
        else:
            n = len(reporte["errores"])
            self.etiqueta_auditoria.setText(f"{n} errores encontrados")
            self.etiqueta_auditoria.setStyleSheet(
                "background: #fdecea; color: #c0392b; padding: 7px 12px; "
                "border-radius: 4px; font-weight: 600;"
            )
            self.texto_errores.setPlainText(
                "\n".join(f"- {e}" for e in reporte["errores"])
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
            f"Inorden:     {ind['inorden']}\n"
            f"Preorden:    {ind['preorden']}\n"
            f"Postorden:   {ind['postorden']}\n"
            f"Por niveles: {ind['por_niveles']}\n"
            f"Nodos por nivel: {ind['nodos_por_nivel']}"
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
        campos["estacion"].setPlaceholderText("Ej. ST-01")
        form.addRow("ID", campos["id"])
        form.addRow("Magnitud", campos["magnitud"])
        form.addRow("Profundidad (km)", campos["profundidad"])
        form.addRow("Coordenada X", campos["x"])
        form.addRow("Coordenada Y", campos["y"])
        form.addRow("Fecha UTC", campos["fecha"])
        if incluir_revision:
            campos["revision"] = QSpinBox()
            campos["revision"].setRange(1, 999999)
            form.addRow("Revision", campos["revision"])
        form.addRow("Estacion", campos["estacion"])
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
            self.statusBar().showMessage(f"Evento {evento.id_evento} creado", 4000)
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))

    def marcar_revisado(self):
        event_id = self._id_seleccionado()
        if event_id is None:
            return
        try:
            self.sistema.marcar_revisado(event_id)
            self.statusBar().showMessage(f"Evento {event_id} marcado como revisado", 4000)
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))

    def deshacer(self):
        if self.timer_procesamiento.isActive():
            self.timer_procesamiento.stop()
            self.boton_procesar_todos.setText("Procesar toda la cola")
        descripcion = self.sistema.descripcion_ultima_accion()
        if descripcion is None:
            self.statusBar().showMessage("No hay acciones para deshacer", 4000)
            return
        if not self.sistema.deshacer():
            self.statusBar().showMessage("No se pudo deshacer", 4000)
            return
        self.statusBar().showMessage(f"Deshecho: {descripcion}", 4000)
        self.actualizar_vistas()

    def _switch_modo_estres(self, activo):
        try:
            if activo:
                self.sistema.activar_modo_estres()
                self.statusBar().showMessage("Modo estrés activado", 4000)
            else:
                pausado = False
                if self.timer_procesamiento.isActive():
                    self.timer_procesamiento.stop()
                    self.boton_procesar_todos.setText("Procesar toda la cola")
                    pausado = True

                costo = self.sistema.desactivar_modo_estres()
                prefijo = "Procesamiento pausado. " if pausado else ""
                self.statusBar().showMessage(
                    f"{prefijo}Balance recuperado: Altura de "
                    f"{costo['altura_antes']} a {costo['altura_despues']}, "
                    f"{costo['giros']} giros, "
                    f"{costo['nodos_visitados']} nodos visitados, "
                    f"{costo['pasadas']} pasadas",
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
            self.boton_estres.setText("Modo estres: ACTIVO")
        else:
            self.boton_estres.setText("Modo estres")
        self.boton_estres.blockSignals(False)

    def _actualizar_indicador_modo(self):
        if self.sistema.en_modo_estres():
            self.etiqueta_modo.setText("Modo: ESTRÉS")
            self.etiqueta_modo.setStyleSheet(
                "color: #c0392b; font-weight: 600; padding-right: 10px;"
            )
        else:
            self.etiqueta_modo.setText("Modo: normal")
            self.etiqueta_modo.setStyleSheet(
                "color: #52616f; padding-right: 10px;"
            )

    def eliminar_evento(self):
        event_id = self._id_seleccionado()
        if event_id is None:
            return
        respuesta = QMessageBox.question(
            self, "Eliminar evento",
            f"El evento {event_id} no podra reactivarse. Deseas eliminarlo?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        try:
            self.sistema.eliminar_evento(event_id)
            self.statusBar().showMessage(f"Evento {event_id} eliminado", 4000)
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))

    def encolar_reporte(self):
        try:
            datos = self._leer_datos(self.campos_reporte)
            reporte = Reporte(revision=self.campos_reporte["revision"].value(), **datos)
            self.sistema.encolar_reporte(reporte)
            self.statusBar().showMessage("Reporte agregado a la cola", 4000)
            self.actualizar_vistas()
        except ValueError as error:
            self._mostrar_error(str(error))

    def procesar_siguiente_reporte(self):
        self._mostrar_resultados([self.sistema.procesar_siguiente_reporte()])
        self.actualizar_vistas()

    def procesar_todos_los_reportes(self):
        if self.timer_procesamiento.isActive():
            self.timer_procesamiento.stop()
            self.boton_procesar_todos.setText("Procesar toda la cola")
            self.statusBar().showMessage("Procesamiento pausado", 3000)
            return
        if not self.sistema.hay_reportes_pendientes():
            self.statusBar().showMessage("No hay reportes pendientes", 3000)
            return
        self.timer_procesamiento.start()
        self.boton_procesar_todos.setText("Pausar procesamiento")
        self.statusBar().showMessage("Procesando cola...", 3000)

    def agregar_zona(self):
        nombre = self.nombre_zona.text().strip()
        if not nombre:
            self._mostrar_error("El nombre de la zona es obligatorio")
            return
        if (self.x_min_zona.value() > self.x_max_zona.value()
                or self.y_min_zona.value() > self.y_max_zona.value()):
            self._mostrar_error(
                "Los valores minimos no pueden ser mayores que los maximos"
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
                f"Zona '{nombre}' agregada. "
                f"{afectados} eventos cambiaron de prioridad.",
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
            self.boton_deshacer.setToolTip(f"Deshacer: {descripcion}")
        else:
            self.boton_deshacer.setToolTip("No hay acciones para deshacer")

    def _actualizar_tabla_versiones(self):
        try:
            versiones = self.gestor_versiones.listar()
        except ErrorVersionesPersistentes as error:
            self.tabla_versiones.setRowCount(0)
            self.statusBar().showMessage(f"Catálogo de versiones inválido: {error}", 8000)
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
                "Estrés" if version["stress_mode"] else "Normal",
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
            "Reloj UTC: " + instante.strftime("%Y-%m-%d %H:%M:%S")
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
            self.texto_inorden.setPlainText("Aun no hay eventos en el AVL.")
            return
        lineas = [
            f"ID {evento.id_evento} | clave {evento.calcular_clave()} | {evento.estado}"
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
                evento.revision, evento.estado,
                "Poblada" if evento.en_zona_poblada else "No poblada",
                "Sí" if evento.acceso_costoso else "No",
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
            texto = escena.addText(f"No hay nodos en el {nombre_arbol}")
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
                evento.estado,
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
                f"No se pudo evaluar el archivo: {error}"
            )
            return

        self._archivo_previsualizado = resultado
        self.boton_archivar_rama.setEnabled(resultado["elegible"])
        if resultado["elegible"]:
            self.etiqueta_previsualizacion_archivo.setText(
                f"Rama lista para archivar\n\n"
                f"Raíz: SIS-{resultado['raiz'].id_evento:06d}\n"
                f"Profundidad: {resultado['profundidad']}\n"
                f"Eventos: {resultado['cantidad']}\n"
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
            "No hay una rama elegible para archivar.\n\n"
            f"Eventos activos: {len(eventos)}\n"
            f"Prioridad baja: {len(prioridad_baja)}\n"
            f"Bajos con antigüedad mayor que T: {len(antiguos)}\n"
            f"T actual: {self.sistema.parametros.t:.1f} horas"
        )

    def _actualizar_detalle_historico(self):
        fila = self.tabla_historico.currentRow()
        if fila < 0:
            self.texto_detalle_historico.setPlainText(
                "Selecciona un evento archivado para ver sus datos."
            )
            return
        item = self.tabla_historico.item(fila, 0)
        if item is None:
            return
        event_id = item.data(Qt.ItemDataRole.UserRole)
        evento = self.sistema._historicos.get(event_id)
        if evento is None:
            return
        referencia = evento.referencia if evento.referencia is not None else "Sin referencia"
        texto = (
            f"ID: {evento.id_evento}\n"
            f"Clave: {evento.calcular_clave()}\n"
            f"Magnitud: {evento.magnitud:.1f}\n"
            f"Profundidad: {evento.profundidad:.1f} km\n"
            f"Epicentro: ({evento.x:.1f}, {evento.y:.1f})\n"
            f"Fecha UTC: {evento.fecha_hora.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Revisión: {evento.revision}\n"
            f"Estado: {evento.estado}\n"
            f"Estaciones: {', '.join(sorted(evento.estaciones)) or '-'}\n"
            f"Referencia: {referencia}\n"
            f"Referenciado por: {', '.join(map(str, sorted(evento.referenciado_por))) or '-'}"
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
            "Archivar rama",
            f"Se archivarán {resultado['cantidad']} eventos: "
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
        self.etiqueta_previsualizacion_archivo.setText(resultado["mensaje"])
        self.statusBar().showMessage(resultado["mensaje"], 5000)
        self.actualizar_vistas()

    def _actualizar_grafico_arbol(self):
        self.escena_arbol.clear()
        raiz = self.sistema.avl.root
        if raiz is None:
            texto = self.escena_arbol.addText("Aun no hay nodos en el AVL")
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
        self.boton_revisar.setEnabled(hay_seleccion)
        self.boton_eliminar.setEnabled(hay_seleccion)

    def _id_seleccionado(self):
        fila = self.tabla_eventos.currentRow()
        if fila < 0:
            return None
        item = self.tabla_eventos.item(fila, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _mostrar_resultados(self, resultados):
        lineas = []
        for indice, resultado in enumerate(resultados, start=1):
            evento = resultado.get("evento")
            evento_texto = f"Evento: {evento.id_evento}" if evento else "Evento: -"
            rotaciones = resultado.get("rotaciones", []) or ["ninguna"]
            lineas.append(
                f"Paso {indice}: {resultado['decision']}\n{resultado['mensaje']}\n"
                f"{evento_texto}\nRotaciones: {', '.join(rotaciones)}"
            )
        self.texto_resultado.setPlainText("\n\n".join(lineas))
        self.statusBar().showMessage("Procesamiento de reportes terminado", 4000)

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
            f"Versión '{version['name']}' guardada", 5000
        )

    def restaurar_version(self):
        nombre = self._version_seleccionada()
        if nombre is None:
            return
        respuesta = QMessageBox.question(
            self,
            "Restaurar versión",
            f"Se reemplazará el estado actual por la versión '{nombre}'.\n"
            "Podrás deshacer esta restauración.",
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
            f"Versión '{nombre}' restaurada", 5000
        )

    def eliminar_version(self):
        nombre = self._version_seleccionada()
        if nombre is None:
            return
        respuesta = QMessageBox.question(
            self,
            "Eliminar versión",
            f"La versión '{nombre}' se eliminará permanentemente.",
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
            f"Versión '{nombre}' eliminada", 5000
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
            "Archivos JSON (*.json *.JSON);;Todos los archivos (*)",
        )
        return ruta


    def guardar_json(self):
        ruta_sugerida = str(self._data_dir() / "sismolab_estado.json")
        ruta, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar estado del sistema",
            ruta_sugerida,
            "Archivos JSON (*.json)",
        )
        if not ruta:
            return

        try:
            destino = JsonSaver.guardar(self.sistema, ruta)
            self.statusBar().showMessage(
                f"Guardado en: {destino}", 6000
            )
            QMessageBox.information(
                self, "Guardado exitoso",
                f"Estado guardado en:\n{destino}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error al guardar",
                f"No se pudo guardar el archivo:\n{e}",
            )

    def cargar_json_topologia(self):
        ruta = self._seleccionar_archivo_json("Cargar topología desde JSON")
        if not ruta:
            return

        try:
            nuevo_sistema = JsonLoader.cargar_topologia(
                ruta, sistema_actual=self.sistema
            )
        except ErrorJsonPersistencia as e:
            QMessageBox.critical(
                self, "JSON inválido",
                f"El archivo no se pudo cargar:\n\n{e}\n\n"
                f"El sistema actual no fue modificado.",
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self, "Error inesperado",
                f"Ocurrió un error al cargar:\n{e}\n\n"
                f"El sistema actual no fue modificado.",
            )
            return

        self.sistema = nuevo_sistema
        self.bst_comparativo = None
        self.actualizar_vistas()
        self.statusBar().showMessage(
            f"Topología cargada desde: {ruta}", 6000
        )
        QMessageBox.information(
            self, "Carga exitosa",
            f"Se restauró el escenario desde:\n{ruta}\n\n"
            f"Eventos activos: {self.sistema.avl.size()}\n"
            f"Altura del AVL: {self.sistema.avl.height()}\n"
            f"Modo estrés: {'activo' if self.sistema.en_modo_estres() else 'inactivo'}",
        )

    def cargar_json_inserciones(self):
        ruta = self._seleccionar_archivo_json(
            "Cargar por inserciones desde JSON"
        )
        if not ruta:
            return

        try:
            sistema_nuevo, bst = JsonLoader.cargar_por_inserciones(ruta)
        except ErrorJsonPersistencia as e:
            QMessageBox.critical(
                self, "JSON inválido",
                f"El archivo no se pudo cargar:\n\n{e}\n\n"
                f"El sistema actual no fue modificado.",
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self, "Error inesperado",
                f"Ocurrió un error al cargar:\n{e}",
            )
            return

        # Keep the BST built by the insertion loader for the comparison view.
        self.bst_comparativo = bst
        self.sistema = sistema_nuevo
        self.actualizar_vistas()

        inorden_avl = [e.id_evento for e in sistema_nuevo.avl.in_order()]
        inorden_bst = [e.id_evento for e in bst.in_order()]

        mensaje = (
            f"Archivo: {ruta}\n\n"
            f"=== AVL (balanceado) ===\n"
            f"  Altura:  {sistema_nuevo.avl.height()}\n"
            f"  Nodos:   {sistema_nuevo.avl.size()}\n"
            f"  Hojas:   {sistema_nuevo.avl.number_of_leaves()}\n"
            f"  Raíz:    {sistema_nuevo.avl.root.event.id_evento if sistema_nuevo.avl.root else '-'}\n\n"
            f"=== BST (sin balanceo) ===\n"
            f"  Altura:  {bst.height()}\n"
            f"  Nodos:   {bst.size()}\n"
            f"  Hojas:   {bst.number_of_leaves()}\n"
            f"  Raíz:    {bst.root.event.id_evento if bst.root else '-'}\n\n"
            f"Inorden AVL == Inorden BST: "
            f"{'SÍ' if inorden_avl == inorden_bst else 'NO'}"
        )

        QMessageBox.information(self, "Comparación AVL vs BST", mensaje)
        self.statusBar().showMessage(
            f"Inserciones cargadas desde: {ruta}. "
            f"Ve al tab 'AVL vs BST' para ver los árboles.", 8000
        )
    
    def _mostrar_acceso_costoso(self):
        eventos = self.sistema.eventos_con_acceso_costoso()
        if not eventos:
            QMessageBox.information(
                self, "Acceso costoso",
                "No hay eventos de prioridad alta con acceso costoso."
            )
            return
        lineas = []
        for item in eventos:
            evento = item["evento"]
            lineas.append(
                f"ID {evento.id_evento} | P{evento.prioridad} | "
                f"M{evento.magnitud:.1f} | profundidad {item['profundidad']} | "
                f"L={item['limite']} | visitados {item['nodos_visitados']}"
            )
        QMessageBox.information(
            self, "Eventos con acceso costoso",
            "\n".join(lineas)
        )

    def _mostrar_error(self, mensaje):
        QMessageBox.warning(self, "Dato no valido", mensaje)


def ejecutar_aplicacion():
    """Starts the desktop application."""
    app = QApplication.instance() or QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    return app.exec()
