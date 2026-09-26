"""PySide6 interface for the SismoLab AVL project."""

import sys
from datetime import datetime, timezone

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDateTimeEdit,
    QDoubleSpinBox,
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
)

from models.map import Zona
from models.report import Reporte
from services.sistema_sismico import SistemaSismico


class VentanaPrincipal(QMainWindow):
    """Desktop view that uses the existing SismoLab service."""

    def __init__(self):
        super().__init__()
        self.sistema = SistemaSismico()
        self._crear_ventana()
        self.actualizar_vistas()

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
        layout.addWidget(pestanas, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Sistema listo")
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
        titulo.setStyleSheet("font-size: 24px; font-weight: 700; color: #17324d;")
        subtitulo = QLabel("Observatorio sismico")
        subtitulo.setStyleSheet("color: #52616f;")
        textos.addWidget(titulo)
        textos.addWidget(subtitulo)
        layout.addLayout(textos)
        layout.addStretch()
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
            valor.setStyleSheet("font-size: 22px; font-weight: 700; color: #17324d;")
            tarjeta_layout.addWidget(nombre)
            tarjeta_layout.addWidget(valor)
            self.etiquetas_resumen[clave] = valor
            rejilla.addWidget(tarjeta, indice // 4, indice % 4)
        layout.addWidget(metricas)

        grupo_arbol = QGroupBox("Vista grafica del AVL")
        arbol_layout = QVBoxLayout(grupo_arbol)
        ayuda = QLabel("Cada nodo muestra: ID, altura y factor de balance.")
        ayuda.setStyleSheet("color: #52616f;")
        self.escena_arbol = QGraphicsScene(self)
        self.vista_arbol = QGraphicsView(self.escena_arbol)
        self.vista_arbol.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.vista_arbol.setMinimumHeight(290)
        self.vista_arbol.setStyleSheet("background: white; border: 1px solid #d8e0e8;")
        arbol_layout.addWidget(ayuda)
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
        self.tabla_eventos = self._crear_tabla(
            ["ID", "Magnitud", "Prof.", "Prioridad", "Revision", "Estado", "Zona"]
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
        boton_todos = QPushButton("Procesar toda la cola")
        boton_todos.clicked.connect(self.procesar_todos_los_reportes)
        acciones.addWidget(boton_uno)
        acciones.addWidget(boton_todos)
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
        resultados = self.sistema.procesar_continuo()
        if not resultados:
            resultados = [{"decision": "cola_vacia", "mensaje": "No hay reportes pendientes", "rotaciones": []}]
        self._mostrar_resultados(resultados)
        self.actualizar_vistas()

    def agregar_zona(self):
        nombre = self.nombre_zona.text().strip()
        if not nombre:
            self._mostrar_error("El nombre de la zona es obligatorio")
            return
        if self.x_min_zona.value() > self.x_max_zona.value() or self.y_min_zona.value() > self.y_max_zona.value():
            self._mostrar_error("Los valores minimos no pueden ser mayores que los maximos")
            return
        zona = Zona(
            nombre, self.x_min_zona.value(), self.y_min_zona.value(),
            self.x_max_zona.value(), self.y_max_zona.value(),
            self.zona_poblada.isChecked(),
        )
        self.sistema.mapa.agregar_zona(zona)
        eventos = self.sistema.avl.in_order()
        for evento in eventos:
            self.sistema.avl.delete(evento.calcular_clave())
        for evento in eventos:
            self.sistema.mapa.asignar_zona_a_evento(evento)
            self.sistema.avl.insert(evento)
        self.statusBar().showMessage(f"Zona '{nombre}' agregada", 4000)
        self.actualizar_vistas()

    def actualizar_vistas(self):
        self._actualizar_reloj()
        self._actualizar_resumen()
        self._actualizar_tabla_eventos()
        self._actualizar_tabla_reportes()
        self._actualizar_mapa()
        self._actualizar_botones_evento()

    def _actualizar_reloj(self):
        self.etiqueta_reloj.setText(
            "Reloj UTC: " + self.sistema.reloj.instante.strftime("%Y-%m-%d %H:%M:%S")
        )

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
            ]
            for columna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                item.setForeground(QBrush(QColor("#172b4d")))
                if columna == 0:
                    item.setData(Qt.ItemDataRole.UserRole, evento.id_evento)
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

    def _actualizar_grafico_arbol(self):
        self.escena_arbol.clear()
        raiz = self.sistema.avl.root
        if raiz is None:
            texto = self.escena_arbol.addText("Aun no hay nodos en el AVL")
            texto.setDefaultTextColor(QColor("#52616f"))
            texto.setPos(20, 20)
            self.escena_arbol.setSceneRect(0, 0, 500, 120)
            return
        nodos = []
        posiciones = {}
        indice = 0

        def asignar_posiciones(nodo, nivel):
            nonlocal indice
            if nodo is None:
                return
            asignar_posiciones(nodo.left, nivel + 1)
            posiciones[id(nodo)] = (55 + indice * 105, 40 + nivel * 100)
            nodos.append(nodo)
            indice += 1
            asignar_posiciones(nodo.right, nivel + 1)

        asignar_posiciones(raiz, 0)
        enlace = QPen(QColor("#7d98b3"), 2)
        for nodo in nodos:
            x, y = posiciones[id(nodo)]
            for hijo in (nodo.left, nodo.right):
                if hijo is not None:
                    hijo_x, hijo_y = posiciones[id(hijo)]
                    self.escena_arbol.addLine(x, y + 24, hijo_x, hijo_y - 24, enlace)
        for nodo in nodos:
            x, y = posiciones[id(nodo)]
            self.escena_arbol.addEllipse(
                x - 35, y - 25, 70, 50,
                QPen(QColor("#1967a8"), 2), QBrush(QColor("#dcecf8")),
            )
            texto = self.escena_arbol.addText(
                f"ID {nodo.event.id_evento}\nh={nodo.height}  fb={nodo.balance_factor}"
            )
            texto.setDefaultTextColor(QColor("#172b4d"))
            rectangulo = texto.boundingRect()
            texto.setPos(x - rectangulo.width() / 2, y - rectangulo.height() / 2)
        rectangulo = self.escena_arbol.itemsBoundingRect().adjusted(-35, -25, 35, 25)
        self.escena_arbol.setSceneRect(rectangulo)
        self.vista_arbol.fitInView(rectangulo, Qt.AspectRatioMode.KeepAspectRatio)

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

    def _mostrar_error(self, mensaje):
        QMessageBox.warning(self, "Dato no valido", mensaje)


def ejecutar_aplicacion():
    """Starts the desktop application."""
    app = QApplication.instance() or QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    return app.exec()
