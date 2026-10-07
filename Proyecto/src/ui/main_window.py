# Módulo main window: contiene la lógica relacionada con main window.
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

from models.map import Zone
from models.report import Report
from services.seismic_system import SeismicSystem
from services.history import Action
from services.archive import archive_branch, preview_archive
from services.queries import (
    first_k_pending,
    events_by_magnitude,
    events_by_depth_and_date,
    event_associations,
)
from persistence.json_loader import JsonLoader, JsonPersistenceError
from persistence.json_saver import JsonSaver
from persistence.versions import (
    PersistentVersionsError,
    VersionManager,
)
from structure.bst import BST
from services.audit import verify_structure


# Representa TreeViewWithZoom y agrupa sus datos y operaciones.
class TreeViewWithZoom(QGraphicsView):

    # Define init.
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
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

    # Gestiona wheelEvent.
    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)


# Representa MainWindow y agrupa sus datos y operaciones.
class MainWindow(QMainWindow):
    """Desktop view that uses the existing SismoLab service."""

    # Define init.
    def __init__(self):
        super().__init__()
        self.system = SeismicSystem()
        self.version_manager = VersionManager(
            self._data_dir() / "versions"
        )
        self.comparison_bst = None
        self._populating_table = False
        self._editable_columns = {1, 2, 3, 4}  # Magnitude, Depth, X, Y
        self._build_window()
        self._create_clock_timer()
        self._create_processing_timer()
        self.update_views()

    # Gestiona create clock timer.
    def _create_clock_timer(self):
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._clock_tick)
        self.clock_timer.start()

    # Gestiona clock tick.
    def _clock_tick(self):
        self.system.clock.advance(1)
        self._update_clock()

    # Gestiona create processing timer.
    def _create_processing_timer(self):
        self.processing_timer = QTimer(self)
        self.processing_timer.setInterval(800)
        self.processing_timer.timeout.connect(self._process_one_step)

    # Gestiona process one step.
    def _process_one_step(self):
        if not self.system.has_pending_reports():
            self.processing_timer.stop()
            self.process_all_button.setText("Process full queue")
            self.statusBar().showMessage("Queue empty", 3000)
            return
        result = self.system.process_next_report()
        self._show_results([result])
        self.update_views()

    # Gestiona jump clock.
    def jump_clock(self):
        text = self.jump_field.dateTime().toString(
            "yyyy-MM-dd HH:mm:ss"
        )
        date = datetime.strptime(
            text, "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
        try:
            self.system.jump_clock(date)
            self.statusBar().showMessage(
                f"Clock jumped to {date.strftime('%Y-%m-%d %H:%M:%S')}",
                4000,
            )
            self.update_views()
        except ValueError as error:
            self._show_error(str(error))

    # Gestiona build window.
    def _build_window(self):
        self.setWindowTitle("SismoLab AVL")
        self.resize(1220, 780)
        self.setMinimumSize(980, 640)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(self._build_header())

        tabs = QTabWidget()
        tabs.addTab(self._build_summary(), "Summary")
        tabs.addTab(self._build_events(), "Events")
        tabs.addTab(self._build_reports(), "Reports")
        tabs.addTab(self._build_map(), "Map & zones")
        tabs.addTab(self._build_comparison(), "AVL vs BST")
        tabs.addTab(self._build_history(), "History")
        tabs.addTab(self._build_queries(), "Queries")
        tabs.addTab(self._build_versions(), "Versions")
        tabs.addTab(self._build_audit(), "Audit")
        layout.addWidget(tabs, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("System ready")
        self.statusBar().setStyleSheet(
            "QStatusBar { background: #e8eef4; color: #172b4d; }"
        )

        self.mode_label = QLabel("Mode: normal")
        self.mode_label.setStyleSheet(
            "color: #52616f; padding-right: 10px;"
        )
        self.statusBar().addPermanentWidget(self.mode_label)

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

    # Gestiona build header.
    def _build_header(self):
        container = QFrame()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        texts = QVBoxLayout()
        texts.setSpacing(0)
        title = QLabel("SismoLab AVL")
        title.setStyleSheet(
            "font-size: 24px; font-weight: 700; color: #17324d;"
        )
        subtitle = QLabel("Seismic observatory")
        subtitle.setStyleSheet("color: #52616f;")
        texts.addWidget(title)
        texts.addWidget(subtitle)
        layout.addLayout(texts)
        layout.addStretch()

        self.save_button = QPushButton("Save JSON")
        self.save_button.clicked.connect(self.save_json)
        layout.addWidget(self.save_button)

        self.load_topology_button = QPushButton("Load topology")
        self.load_topology_button.clicked.connect(self.load_json_topology)
        layout.addWidget(self.load_topology_button)

        self.load_insertions_button = QPushButton("Load insertions")
        self.load_insertions_button.clicked.connect(self.load_json_insertions)
        layout.addWidget(self.load_insertions_button)

        self.stress_button = QPushButton("Stress mode")
        self.stress_button.setCheckable(True)
        self.stress_button.toggled.connect(self._switch_stress_mode)
        self.stress_button.setStyleSheet(
            "QPushButton {"
            "   background: #1967a8; color: white;"
            "   border: 0; border-radius: 4px;"
            "   padding: 7px 11px;"
            "}"
            "QPushButton:checked {"
            "   background: #c0392b;"
            "}"
        )
        layout.addWidget(self.stress_button)

        self.undo_button = QPushButton("Undo")
        self.undo_button.clicked.connect(self.undo)
        self.undo_button.setEnabled(False)
        layout.addWidget(self.undo_button)

        self.jump_field = QDateTimeEdit()
        self.jump_field.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.jump_field.setCalendarPopup(True)
        self.jump_field.setDateTime(self._qdatetime_from_clock())
        self.jump_field.setStyleSheet(
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
        layout.addWidget(self.jump_field)

        self.jump_button = QPushButton("Jump to this time")
        self.jump_button.clicked.connect(self.jump_clock)
        layout.addWidget(self.jump_button)

        self.clock_label = QLabel()
        self.clock_label.setStyleSheet(
            "background: #e1f1ed; color: #155d4a; padding: 7px 10px; "
            "border-radius: 4px; font-weight: 600;"
        )
        layout.addWidget(self.clock_label)
        return container

    # Gestiona build summary.
    def _build_summary(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        metrics = QGroupBox("Scenario status")
        grid = QGridLayout(metrics)
        self.summary_labels = {}
        data = [
            ("Active events", "events"),
            ("AVL height", "height"),
            ("AVL leaves", "leaves"),
            ("Reports in queue", "queue"),
            ("Accepted corrections", "corrections"),
            ("Conflicts", "conflicts"),
            ("Confirmations", "confirmations"),
            ("Created by report", "created"),
        ]
        for index, (text, key) in enumerate(data):
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background: white; border: 1px solid #d8e0e8; "
                "border-radius: 5px; }"
            )
            card_layout = QVBoxLayout(card)
            name = QLabel(text)
            name.setStyleSheet("color: #52616f;")
            value = QLabel("0")
            value.setStyleSheet(
                "font-size: 22px; font-weight: 700; color: #17324d;"
            )
            card_layout.addWidget(name)
            card_layout.addWidget(value)
            self.summary_labels[key] = value
            grid.addWidget(card, index // 4, index % 4)
        layout.addWidget(metrics)

        tree_group = QGroupBox("AVL graphical view")
        tree_layout = QVBoxLayout(tree_group)
        help_text = QLabel(
            "Each node shows: ID and priority. "
            "Drag with the mouse to scroll. Ctrl + wheel to zoom."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #52616f;")
        tree_layout.addWidget(help_text)

        tree_bar = QHBoxLayout()
        zoom_in = QPushButton("Zoom +")
        zoom_out = QPushButton("Zoom -")
        reset = QPushButton("Reset view")
        zoom_in.clicked.connect(
            lambda: self.tree_view.scale(1.2, 1.2)
        )
        zoom_out.clicked.connect(
            lambda: self.tree_view.scale(1 / 1.2, 1 / 1.2)
        )
        reset.clicked.connect(self._reset_tree_view)
        tree_bar.addWidget(zoom_in)
        tree_bar.addWidget(zoom_out)
        tree_bar.addWidget(reset)
        cost_button = QPushButton("View expensive access")
        cost_button.clicked.connect(self._show_expensive_access)
        tree_bar.addWidget(cost_button)
        verify_button = QPushButton("Verify structure")
        verify_button.clicked.connect(self.verify_structure)
        tree_bar.addWidget(verify_button)
        tree_bar.addStretch()
        tree_layout.addLayout(tree_bar)

        self.tree_scene = QGraphicsScene(self)
        self.tree_view = TreeViewWithZoom(self.tree_scene)
        tree_layout.addWidget(self.tree_view)
        layout.addWidget(tree_group, 1)

        order_group = QGroupBox("In-order traversal")
        order_layout = QVBoxLayout(order_group)
        self.inorder_text = QTextEdit()
        self.inorder_text.setReadOnly(True)
        self.inorder_text.setMaximumHeight(90)
        order_layout.addWidget(self.inorder_text)
        layout.addWidget(order_group)
        return page

    # Gestiona build events.
    def _build_events(self):
        page = QWidget()
        splitter = QSplitter(Qt.Orientation.Horizontal)

        form = QGroupBox("Create event")
        form_layout = QVBoxLayout(form)
        self.event_fields = self._build_form(form_layout)
        create_button = QPushButton("Create event")
        create_button.clicked.connect(self.create_event)
        form_layout.addWidget(create_button)
        form_layout.addStretch()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)

        table_group = QGroupBox(
            "Active events — double-click Magnitude / Depth / X / Y to correct"
        )
        table_layout = QVBoxLayout(table_group)
        self.events_table = self._build_table(
            ["ID", "Magnitude", "Depth", "X", "Y",
             "Priority", "Revision", "State", "Zone", "Cost"]
        )
        self.events_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self._populating_table = False
        self.events_table.itemChanged.connect(self._on_event_cell_changed)
        self.events_table.itemSelectionChanged.connect(self._update_event_buttons)
        table_layout.addWidget(self.events_table)
        panel_layout.addWidget(table_group, 1)

        actions = QHBoxLayout()

        self.review_button = QPushButton("Mark as reviewed")
        self.review_button.clicked.connect(self.mark_reviewed)
        self.review_button.setEnabled(False)
        actions.addWidget(self.review_button)

        self.remove_button = QPushButton("Remove event")
        self.remove_button.setStyleSheet("background: #ae3e3e;")
        self.remove_button.clicked.connect(self.remove_event)
        self.remove_button.setEnabled(False)
        actions.addWidget(self.remove_button)

        actions.addStretch()
        panel_layout.addLayout(actions)

        splitter.addWidget(form)
        splitter.addWidget(panel)
        splitter.setSizes([330, 780])

        layout = QVBoxLayout(page)
        layout.addWidget(splitter)
        return page

    # Gestiona build reports.
    def _build_reports(self):
        page = QWidget()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        form = QGroupBox("New station report")
        form_layout = QVBoxLayout(form)
        self.report_fields = self._build_form(form_layout, True)
        enqueue_button = QPushButton("Add to queue")
        enqueue_button.clicked.connect(self.enqueue_report)
        form_layout.addWidget(enqueue_button)
        form_layout.addStretch()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        queue_group = QGroupBox("FIFO report queue")
        queue_layout = QVBoxLayout(queue_group)
        self.reports_table = self._build_table(
            ["ID", "Magnitude", "Revision", "Station", "Datetime UTC"]
        )
        queue_layout.addWidget(self.reports_table)
        actions = QHBoxLayout()
        one_button = QPushButton("Process next")
        one_button.clicked.connect(self.process_next_report)
        self.process_all_button = QPushButton("Process full queue")
        self.process_all_button.clicked.connect(self.process_all_reports)
        actions.addWidget(one_button)
        actions.addWidget(self.process_all_button)
        actions.addStretch()
        queue_layout.addLayout(actions)
        panel_layout.addWidget(queue_group, 1)

        result_group = QGroupBox("Processing result")
        result_layout = QVBoxLayout(result_group)
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(125)
        result_layout.addWidget(self.result_text)
        panel_layout.addWidget(result_group)
        splitter.addWidget(form)
        splitter.addWidget(panel)
        splitter.setSizes([330, 780])
        layout = QVBoxLayout(page)
        layout.addWidget(splitter)
        return page

    # Gestiona build map.
    def _build_map(self):
        page = QWidget()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        form = QGroupBox("Add zone")
        form_layout = QVBoxLayout(form)
        data = QFormLayout()
        self.zone_name = QLineEdit()
        self.zone_name.setPlaceholderText("E.g. North City")
        self.zone_x_min = self._decimal_field(0, 1000)
        self.zone_y_min = self._decimal_field(0, 1000)
        self.zone_x_max = self._decimal_field(0, 1000)
        self.zone_y_max = self._decimal_field(0, 1000)
        self.zone_populated = QCheckBox("Populated zone")
        data.addRow("Name", self.zone_name)
        data.addRow("Min X", self.zone_x_min)
        data.addRow("Min Y", self.zone_y_min)
        data.addRow("Max X", self.zone_x_max)
        data.addRow("Max Y", self.zone_y_max)
        data.addRow("Type", self.zone_populated)
        form_layout.addLayout(data)
        add_button = QPushButton("Add zone")
        add_button.clicked.connect(self.add_zone)
        form_layout.addWidget(add_button)
        legend = QLabel("P: populated   N: not populated   E: event")
        legend.setWordWrap(True)
        legend.setStyleSheet("color: #52616f;")
        form_layout.addWidget(legend)
        form_layout.addStretch()

        map_group = QGroupBox("Seismic map")
        map_layout = QVBoxLayout(map_group)
        self.map_table = QTableWidget()
        self.map_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.map_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.map_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.map_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        map_layout.addWidget(self.map_table)
        splitter.addWidget(form)
        splitter.addWidget(map_group)
        splitter.setSizes([330, 780])
        layout = QVBoxLayout(page)
        layout.addWidget(splitter)
        return page

    # Gestiona build comparison.
    def _build_comparison(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        explanation = QLabel(
            "Comparison AVL vs BST. The AVL is shown as it is in "
            "memory. The BST is built with the same insertion sequence "
            "when a JSON is loaded by insertions; otherwise, it is "
            "rebuilt by inserting the active events in ascending K order."
        )
        explanation.setStyleSheet("color: #52616f;")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        button_bar = QHBoxLayout()
        load_button = QPushButton("Load JSON by insertions")
        load_button.clicked.connect(self.load_json_insertions)
        button_bar.addWidget(load_button)
        button_bar.addStretch()
        layout.addLayout(button_bar)

        metrics = QGroupBox("Structural metrics")
        grid = QGridLayout(metrics)
        self.comparison_labels = {}
        data = [
            ("AVL height", "avl_height"),
            ("AVL leaves", "avl_leaves"),
            ("AVL root", "avl_root"),
            ("AVL nodes", "avl_nodes"),
            ("BST height", "bst_height"),
            ("BST leaves", "bst_leaves"),
            ("BST root", "bst_root"),
            ("BST nodes", "bst_nodes"),
        ]
        for index, (text, key) in enumerate(data):
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background: white; border: 1px solid #d8e0e8; "
                "border-radius: 5px; }"
            )
            card_layout = QVBoxLayout(card)
            name = QLabel(text)
            name.setStyleSheet("color: #52616f;")
            value = QLabel("-")
            value.setStyleSheet(
                "font-size: 18px; font-weight: 700; color: #17324d;"
            )
            card_layout.addWidget(name)
            card_layout.addWidget(value)
            self.comparison_labels[key] = value
            grid.addWidget(card, index // 4, index % 4)
        layout.addWidget(metrics)

        trees = QSplitter(Qt.Orientation.Horizontal)
        avl_group = QGroupBox("Temporary AVL")
        avl_layout = QVBoxLayout(avl_group)
        self.comparison_avl_scene = QGraphicsScene(self)
        self.comparison_avl_view = TreeViewWithZoom(
            self.comparison_avl_scene
        )
        avl_layout.addWidget(self.comparison_avl_view)

        bst_group = QGroupBox("Unbalanced BST")
        bst_layout = QVBoxLayout(bst_group)
        self.comparison_bst_scene = QGraphicsScene(self)
        self.comparison_bst_view = TreeViewWithZoom(
            self.comparison_bst_scene
        )
        bst_layout.addWidget(self.comparison_bst_view)

        trees.addWidget(avl_group)
        trees.addWidget(bst_group)
        trees.setSizes([600, 600])
        layout.addWidget(trees, 1)
        return page

    # Gestiona build history.
    def _build_history(self):
        page = QWidget()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._previewed_archive = None

        archive_group = QGroupBox("Branch archive")
        archive_layout = QVBoxLayout(archive_group)
        help_text = QLabel(
            "The system archives the largest eligible branch: low-priority "
            "events with age greater than limit T."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #52616f;")
        archive_layout.addWidget(help_text)
        self.archive_preview_label = QLabel(
            "No branch has been evaluated yet."
        )
        self.archive_preview_label.setWordWrap(True)
        self.archive_preview_label.setStyleSheet(
            "background: white; color: #172b4d; border: 1px solid #d8e0e8; "
            "padding: 8px;"
        )
        archive_layout.addWidget(self.archive_preview_label)
        preview_button = QPushButton("Preview archive")
        preview_button.clicked.connect(self.preview_archive_history)
        self.archive_branch_button = QPushButton("Archive branch")
        self.archive_branch_button.clicked.connect(self.archive_branch_history)
        self.archive_branch_button.setEnabled(False)
        archive_layout.addWidget(preview_button)
        archive_layout.addWidget(self.archive_branch_button)
        archive_layout.addStretch()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        table_group = QGroupBox("Archived events")
        table_layout = QVBoxLayout(table_group)
        self.history_table = self._build_table(
            ["ID", "Magnitude", "Priority", "Revision", "State", "Datetime UTC"]
        )
        self.history_table.itemSelectionChanged.connect(
            self._update_history_detail
        )
        table_layout.addWidget(self.history_table)
        panel_layout.addWidget(table_group, 1)

        detail_group = QGroupBox("Archived event detail")
        detail_layout = QVBoxLayout(detail_group)
        self.history_detail_text = QTextEdit()
        self.history_detail_text.setReadOnly(True)
        self.history_detail_text.setMinimumHeight(150)
        detail_layout.addWidget(self.history_detail_text)
        panel_layout.addWidget(detail_group)

        splitter.addWidget(archive_group)
        splitter.addWidget(panel)
        splitter.setSizes([330, 780])
        layout = QVBoxLayout(page)
        layout.addWidget(splitter)
        return page

    # Gestiona build queries.
    def _build_queries(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        params = QGroupBox("Scenario parameters")
        params_layout = QHBoxLayout(params)

        self.w_field = QDoubleSpinBox()
        self.w_field.setRange(0.1, 100000.0)
        self.w_field.setDecimals(1)
        self.w_field.setValue(self.system.parameters.w)

        self.r_field = QDoubleSpinBox()
        self.r_field.setRange(0.1, 100000.0)
        self.r_field.setDecimals(1)
        self.r_field.setValue(self.system.parameters.r)

        self.l_field = QSpinBox()
        self.l_field.setRange(0, 999999)
        self.l_field.setValue(self.system.parameters.l)

        self.t_field = QDoubleSpinBox()
        self.t_field.setRange(0.1, 100000.0)
        self.t_field.setDecimals(1)
        self.t_field.setValue(self.system.parameters.t)

        params_layout.addWidget(QLabel("W (h)"))
        params_layout.addWidget(self.w_field)
        params_layout.addWidget(QLabel("R (km)"))
        params_layout.addWidget(self.r_field)
        params_layout.addWidget(QLabel("L"))
        params_layout.addWidget(self.l_field)
        params_layout.addWidget(QLabel("T (h)"))
        params_layout.addWidget(self.t_field)

        apply_button = QPushButton("Apply parameters")
        apply_button.clicked.connect(self.apply_parameters)
        params_layout.addWidget(apply_button)
        layout.addWidget(params)

        queries = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)

        k_group = QGroupBox("First k pending — descending K")
        k_layout = QVBoxLayout(k_group)
        k_row = QHBoxLayout()
        self.k_query_field = QSpinBox()
        self.k_query_field.setRange(1, 999999)
        self.k_query_field.setValue(5)
        k_button = QPushButton("Query")
        k_button.clicked.connect(self.query_first_k)
        k_row.addWidget(QLabel("k:"))
        k_row.addWidget(self.k_query_field)
        k_row.addWidget(k_button)
        k_layout.addLayout(k_row)
        self.k_query_text = QTextEdit()
        self.k_query_text.setReadOnly(True)
        k_layout.addWidget(self.k_query_text)
        left_layout.addWidget(k_group, 1)

        m_group = QGroupBox("Events by magnitude range")
        m_layout = QVBoxLayout(m_group)
        m_row = QHBoxLayout()
        self.m_min_field = self._decimal_field(-2, 10)
        self.m_max_field = self._decimal_field(-2, 10)
        self.m_min_field.setValue(-2.0)
        self.m_max_field.setValue(10.0)
        m_button = QPushButton("Query")
        m_button.clicked.connect(self.query_magnitude)
        m_row.addWidget(QLabel("Min:"))
        m_row.addWidget(self.m_min_field)
        m_row.addWidget(QLabel("Max:"))
        m_row.addWidget(self.m_max_field)
        m_row.addWidget(m_button)
        m_layout.addLayout(m_row)
        self.m_query_text = QTextEdit()
        self.m_query_text.setReadOnly(True)
        m_layout.addWidget(self.m_query_text)
        left_layout.addWidget(m_group, 1)

        queries.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)

        pf_group = QGroupBox("Depth and date range")
        pf_layout = QVBoxLayout(pf_group)
        pf_form = QFormLayout()
        self.depth_query_field = self._decimal_field(0, 700)
        self.depth_query_field.setValue(700.0)
        self.start_date_query = QDateTimeEdit()
        self.end_date_query = QDateTimeEdit()
        for field in (self.start_date_query, self.end_date_query):
            field.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            field.setCalendarPopup(True)
            field.setDateTime(self._qdatetime_from_clock())
        pf_form.addRow("Max depth (km)", self.depth_query_field)
        pf_form.addRow("From UTC", self.start_date_query)
        pf_form.addRow("To UTC", self.end_date_query)
        pf_layout.addLayout(pf_form)
        pf_button = QPushButton("Query")
        pf_button.clicked.connect(self.query_depth_date)
        pf_layout.addWidget(pf_button)
        self.pf_query_text = QTextEdit()
        self.pf_query_text.setReadOnly(True)
        pf_layout.addWidget(self.pf_query_text)
        right_layout.addWidget(pf_group, 1)

        a_group = QGroupBox("Associations")
        a_layout = QVBoxLayout(a_group)
        a_row = QHBoxLayout()
        self.assoc_id_field = QSpinBox()
        self.assoc_id_field.setRange(1, 999999)
        a_button = QPushButton("Query associations")
        a_button.clicked.connect(self.query_associations)
        a_row.addWidget(QLabel("ID:"))
        a_row.addWidget(self.assoc_id_field)
        a_row.addWidget(a_button)
        a_layout.addLayout(a_row)
        self.associations_text = QTextEdit()
        self.associations_text.setReadOnly(True)
        a_layout.addWidget(self.associations_text)
        right_layout.addWidget(a_group, 1)

        queries.addWidget(right)
        queries.setSizes([600, 600])
        layout.addWidget(queries, 1)
        return page

    # Gestiona apply parameters.
    def apply_parameters(self):
        try:
            changed = self.system.update_parameters(
                w=self.w_field.value(),
                r=self.r_field.value(),
                l=self.l_field.value(),
                t=self.t_field.value(),
            )
            message = (
                "Parameters updated" if changed
                else "No parameter changes"
            )
            self.statusBar().showMessage(message, 4000)
            self.update_views()
        except ValueError as error:
            self._show_error(str(error))

    @staticmethod
    # Gestiona events text.
    def _events_text(events):
        if not events:
            return "No results."
        return "\n".join(
            f"SIS-{event.event_id:06d} | K={event.calculate_key()} | "
            f"M={event.magnitude:.1f} | H={event.depth:.1f} | "
            f"{event.state}"
            for event in events
        )

    # Gestiona query first k.
    def query_first_k(self):
        try:
            result = first_k_pending(
                self.system, self.k_query_field.value()
            )
            self.k_query_text.setPlainText(
                f"AVL nodes examined: {result['nodes_examined']}\n\n"
                + self._events_text(result["events"])
            )
        except ValueError as error:
            self._show_error(str(error))

    # Gestiona query magnitude.
    def query_magnitude(self):
        try:
            result = events_by_magnitude(
                self.system,
                self.m_min_field.value(),
                self.m_max_field.value(),
            )
            self.m_query_text.setPlainText(
                f"AVL nodes examined: {result['nodes_examined']}\n\n"
                + self._events_text(result["events"])
            )
        except ValueError as error:
            self._show_error(str(error))

    # Gestiona query depth date.
    def query_depth_date(self):
        try:
            start = self._read_date(self.start_date_query)
            end = self._read_date(self.end_date_query)
            result = events_by_depth_and_date(
                self.system,
                self.depth_query_field.value(),
                start,
                end,
            )
            self.pf_query_text.setPlainText(
                f"AVL nodes examined: {result['nodes_examined']}\n\n"
                + self._events_text(result["events"])
            )
        except ValueError as error:
            self._show_error(str(error))

    # Gestiona query associations.
    def query_associations(self):
        try:
            result = event_associations(
                self.system, self.assoc_id_field.value()
            )
            event = result["event"]
            reference = result["reference"]
            lines = [
                f"Event: SIS-{event.event_id:06d} ({result['state']})",
                f"AVL nodes examined: {result['nodes_examined']}",
                "",
                "Candidates:",
            ]
            if result["candidates"]:
                lines.extend(
                    f"- SIS-{item['event'].event_id:06d} | "
                    f"M={item['event'].magnitude:.1f} | {item['state']}"
                    for item in result["candidates"]
                )
            else:
                lines.append("- None")

            lines.append("")
            if reference is None:
                lines.append("Chosen reference: none")
            else:
                ref_state = (
                    "active"
                    if reference.event_id in self.system._active_events
                    else "archived"
                )
                lines.append(
                    f"Chosen reference: SIS-{reference.event_id:06d} "
                    f"({ref_state})"
                )

            lines.append("")
            lines.append("Events that use it as reference:")
            if result["referenced_by"]:
                lines.extend(
                    f"- SIS-{item['event'].event_id:06d} | {item['state']}"
                    for item in result["referenced_by"]
                )
            else:
                lines.append("- None")

            self.associations_text.setPlainText("\n".join(lines))
        except ValueError as error:
            self._show_error(str(error))

    # Gestiona build versions.
    def _build_versions(self):
        page = QWidget()
        splitter = QSplitter(Qt.Orientation.Horizontal)

        save_group = QGroupBox("Save version")
        save_layout = QVBoxLayout(save_group)
        help_text = QLabel(
            "A version preserves the entire operational state, including "
            "the AVL topology, history, queue, clock, parameters and metrics."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #52616f;")
        save_layout.addWidget(help_text)

        form = QFormLayout()
        self.version_name_field = QLineEdit()
        self.version_name_field.setPlaceholderText("E.g. Before the burst")
        form.addRow("Name", self.version_name_field)
        save_layout.addLayout(form)
        save_version_button = QPushButton("Save version")
        save_version_button.clicked.connect(self.save_version)
        save_layout.addWidget(save_version_button)
        path_label = QLabel(f"Folder: {self.version_manager.directory}")
        path_label.setWordWrap(True)
        path_label.setStyleSheet("color: #52616f;")
        save_layout.addWidget(path_label)
        save_layout.addStretch()

        panel = QWidget()
        panel_layout = QVBoxLayout(panel)
        list_group = QGroupBox("Saved versions")
        list_layout = QVBoxLayout(list_group)
        self.versions_table = self._build_table(
            ["Name", "Datetime UTC", "Active", "Historical", "Height", "Mode"]
        )
        self.versions_table.itemSelectionChanged.connect(
            self._update_version_buttons
        )
        list_layout.addWidget(self.versions_table)
        actions = QHBoxLayout()
        self.restore_version_button = QPushButton("Restore version")
        self.restore_version_button.clicked.connect(self.restore_version)
        self.delete_version_button = QPushButton("Delete version")
        self.delete_version_button.setStyleSheet("background: #ae3e3e;")
        self.delete_version_button.clicked.connect(self.delete_version)
        actions.addWidget(self.restore_version_button)
        actions.addWidget(self.delete_version_button)
        actions.addStretch()
        list_layout.addLayout(actions)
        panel_layout.addWidget(list_group, 1)

        splitter.addWidget(save_group)
        splitter.addWidget(panel)
        splitter.setSizes([330, 780])
        layout = QVBoxLayout(page)
        layout.addWidget(splitter)
        return page

    # Gestiona build audit.
    def _build_audit(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        bar = QHBoxLayout()
        verify_button = QPushButton("Verify structure")
        verify_button.clicked.connect(self.verify_structure)
        bar.addWidget(verify_button)

        self.audit_label = QLabel("Not verified")
        self.audit_label.setStyleSheet(
            "background: #e8eef4; color: #52616f; padding: 9px 14px; "
            "border-radius: 4px; font-weight: 600; font-size: 13px;"
        )
        bar.addWidget(self.audit_label)
        bar.addStretch()
        layout.addLayout(bar)

        errors_group = QGroupBox("Errors found")
        errors_layout = QVBoxLayout(errors_group)
        self.errors_text = QTextEdit()
        self.errors_text.setReadOnly(True)
        self.errors_text.setMinimumHeight(100)
        self.errors_text.setMaximumHeight(150)
        errors_layout.addWidget(self.errors_text)
        layout.addWidget(errors_group)

        indicators_group = QGroupBox("Indicators")
        indicators_layout = QGridLayout(indicators_group)
        indicators_layout.setSpacing(8)
        indicators_layout.setContentsMargins(10, 16, 10, 10)

        self.audit_labels = {}
        fields = [
            ("active", "Active", 0, 0),
            ("historical", "Historical", 0, 1),
            ("removed", "Removed", 0, 2),
            ("height", "AVL height", 0, 3),
            ("leaves", "Leaves", 0, 4),

            ("rotations_performed", "Rotations", 1, 0),
            ("ll_cases", "LL", 1, 1),
            ("rr_cases", "RR", 1, 2),
            ("lr_cases", "LR", 1, 3),
            ("rl_cases", "RL", 1, 4),

            ("single_left_rotations", "Left turns", 2, 0),
            ("single_right_rotations", "Right turns", 2, 1),
            ("accepted_corrections", "Corrections", 2, 2),
            ("discarded_reports", "Discarded", 2, 3),
            ("conflicts", "Conflicts", 2, 4),

            ("confirmations", "Confirm.", 3, 0),
            ("created_by_report", "Created", 3, 1),
            ("reactivated", "Reactivated", 3, 2),
            ("massive_archives", "Mass arch.", 3, 3),
            ("archived_events", "Archived", 3, 4),

            ("by_priority_1", "P1", 4, 0),
            ("by_priority_2", "P2", 4, 1),
            ("by_priority_3", "P3", 4, 2),
            ("pending", "Pending", 4, 3),
            ("with_expensive_access", "Expensive", 4, 4),
        ]

        for key, label, row, column in fields:
            container = QFrame()
            container.setFixedHeight(60)
            container.setMinimumWidth(130)
            container.setStyleSheet(
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
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(10, 6, 10, 6)
            container_layout.setSpacing(2)

            name = QLabel(label)
            name.setStyleSheet(
                "color: #52616f; font-size: 11px; border: 0; "
                "background: transparent;"
            )

            value = QLabel("0")
            value.setStyleSheet(
                "font-size: 18px; font-weight: 700; color: #17324d; "
                "border: 0; background: transparent;"
            )

            container_layout.addWidget(name)
            container_layout.addWidget(value)
            self.audit_labels[key] = value
            indicators_layout.addWidget(
                container, row, column,
                Qt.AlignmentFlag.AlignTop
            )

        for column in range(5):
            indicators_layout.setColumnStretch(column, 1)

        layout.addWidget(indicators_group)

        traversals_group = QGroupBox("Traversals")
        traversals_layout = QVBoxLayout(traversals_group)
        self.traversals_text = QTextEdit()
        self.traversals_text.setReadOnly(True)
        self.traversals_text.setMinimumHeight(110)
        traversals_layout.addWidget(self.traversals_text)
        layout.addWidget(traversals_group)

        self._update_audit()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setStyleSheet(
            "QScrollArea { border: 0; background: transparent; }"
        )
        return scroll

    # Gestiona verify structure.
    def verify_structure(self):
        report = verify_structure(self.system)

        if report["ok"]:
            self.audit_label.setText("Valid structure")
            self.audit_label.setStyleSheet(
                "background: #d4edda; color: #155d4a; padding: 7px 12px; "
                "border-radius: 4px; font-weight: 600;"
            )
            self.errors_text.setPlainText(
                "No inconsistencies found."
            )
        else:
            n = len(report["errors"])
            self.audit_label.setText(f"{n} errors found")
            self.audit_label.setStyleSheet(
                "background: #fdecea; color: #c0392b; padding: 7px 12px; "
                "border-radius: 4px; font-weight: 600;"
            )
            self.errors_text.setPlainText(
                "\n".join(f"- {e}" for e in report["errors"])
            )

        self._paint_indicators(report["indicators"])

    # Gestiona paint indicators.
    def _paint_indicators(self, ind):
        values = {
            "active": ind["active"],
            "historical": ind["historical"],
            "removed": ind["removed"],
            "height": ind["height"],
            "leaves": ind["leaves"],
            "rotations_performed": ind["rotations_performed"],
            "ll_cases": ind["ll_cases"],
            "rr_cases": ind["rr_cases"],
            "lr_cases": ind["lr_cases"],
            "rl_cases": ind["rl_cases"],
            "single_left_rotations": ind["single_left_rotations"],
            "single_right_rotations": ind["single_right_rotations"],
            "accepted_corrections": ind["accepted_corrections"],
            "discarded_reports": ind["discarded_reports"],
            "conflicts": ind["conflicts"],
            "confirmations": ind["confirmations"],
            "created_by_report": ind["created_by_report"],
            "reactivated": ind["reactivated"],
            "massive_archives": ind["massive_archives"],
            "archived_events": ind["archived_events"],
            "by_priority_1": ind["by_priority"].get(1, 0),
            "by_priority_2": ind["by_priority"].get(2, 0),
            "by_priority_3": ind["by_priority"].get(3, 0),
            "pending": ind["pending"],
            "with_expensive_access": ind["with_expensive_access"],
        }
        for key, value in values.items():
            self.audit_labels[key].setText(str(value))

        self.traversals_text.setPlainText(
            f"In-order:      {ind['in_order']}\n"
            f"Pre-order:     {ind['pre_order']}\n"
            f"Post-order:    {ind['post_order']}\n"
            f"Breadth-first: {ind['breadth_first']}\n"
            f"Nodes per level: {ind['nodes_per_level']}"
        )

    # Gestiona update audit.
    def _update_audit(self):
        report = verify_structure(self.system)
        self._paint_indicators(report["indicators"])

    # Gestiona build form.
    def _build_form(self, layout, include_revision=False):
        form = QFormLayout()
        fields = {
            "id": QSpinBox(),
            "magnitude": self._decimal_field(-2, 10),
            "depth": self._decimal_field(0, 700),
            "x": self._decimal_field(0, 1000),
            "y": self._decimal_field(0, 1000),
            "datetime": QDateTimeEdit(),
            "station": QLineEdit(),
        }
        fields["id"].setRange(1, 999999)
        fields["magnitude"].setValue(5.0)
        fields["depth"].setValue(20.0)
        fields["x"].setValue(100.0)
        fields["y"].setValue(100.0)
        fields["datetime"].setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        fields["datetime"].setCalendarPopup(True)
        fields["datetime"].setDateTime(self._qdatetime_from_clock())
        fields["station"].setPlaceholderText("E.g. ST-01")
        form.addRow("ID", fields["id"])
        form.addRow("Magnitude", fields["magnitude"])
        form.addRow("Depth (km)", fields["depth"])
        form.addRow("Coordinate X", fields["x"])
        form.addRow("Coordinate Y", fields["y"])
        form.addRow("Datetime UTC", fields["datetime"])
        if include_revision:
            fields["revision"] = QSpinBox()
            fields["revision"].setRange(1, 999999)
            form.addRow("Revision", fields["revision"])
        form.addRow("Station", fields["station"])
        layout.addLayout(form)
        return fields

    @staticmethod
    # Gestiona decimal field.
    def _decimal_field(minimum, maximum):
        field = QDoubleSpinBox()
        field.setRange(minimum, maximum)
        field.setDecimals(1)
        field.setSingleStep(0.1)
        return field

    @staticmethod
    # Gestiona build table.
    def _build_table(headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setStyleSheet(
            "QTableWidget { color: #172b4d; background: white; }"
            "QTableWidget::item { color: #172b4d; }"
        )
        return table

    # Gestiona qdatetime from clock.
    def _qdatetime_from_clock(self):
        return QDateTime.fromString(
            self.system.clock.instant.strftime("%Y-%m-%d %H:%M:%S"),
            "yyyy-MM-dd HH:mm:ss",
        )

    @staticmethod
    # Gestiona read date.
    def _read_date(field):
        text = field.dateTime().toString("yyyy-MM-dd HH:mm:ss")
        return datetime.strptime(
            text, "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)

    # Gestiona read data.
    def _read_data(self, fields):
        return {
            "event_id": fields["id"].value(),
            "magnitude": fields["magnitude"].value(),
            "depth": fields["depth"].value(),
            "x": fields["x"].value(),
            "y": fields["y"].value(),
            "datetime": self._read_date(fields["datetime"]),
            "station": fields["station"].text().strip(),
        }

    # Gestiona create event.
    def create_event(self):
        try:
            data = self._read_data(self.event_fields)
            event = self.system.create_event(
                data["event_id"],
                data["magnitude"],
                data["depth"],
                data["x"],
                data["y"],
                data["datetime"],
                data["station"],
            )
            self.statusBar().showMessage(
                f"Event {event.event_id} created", 4000
            )
            self.update_views()
        except ValueError as error:
            self._show_error(str(error))

    # Gestiona on event cell changed.
    def _on_event_cell_changed(self, item):
        """Called when the user edits a cell in the events table."""
        if self._populating_table:
            return
        column = item.column()
        if column not in self._editable_columns:
            return

        row = item.row()
        id_item = self.events_table.item(row, 0)
        if id_item is None:
            return
        event_id = id_item.data(Qt.ItemDataRole.UserRole)
        event = self.system.find_by_id(event_id)
        if event is None:
            self.update_views()
            return

        try:
            raw = item.text().strip().replace(",", ".")
            value = round(float(raw), 1)
        except ValueError:
            QMessageBox.warning(
                self, "Invalid value",
                f"'{item.text()}' is not a valid number."
            )
            self.update_views()
            return

        new_magnitude = event.magnitude
        new_depth = event.depth
        new_x = event.x
        new_y = event.y

        if column == 1:
            new_magnitude = value
        elif column == 2:
            new_depth = value
        elif column == 3:
            new_x = value
        elif column == 4:
            new_y = value

        try:
            self.system.correct_event(
                event_id,
                magnitude=new_magnitude,
                depth=new_depth,
                x=new_x,
                y=new_y,
                datetime_value=event.datetime,
            )
            self.statusBar().showMessage(
                f"Event {event_id} corrected "
                f"(revision {self.system.find_by_id(event_id).revision})",
                5000,
            )
        except Exception as error:
            import traceback
            traceback.print_exc()
            QMessageBox.warning(
                self, "Could not correct event",
                f"{type(error).__name__}: {error}"
            )
        finally:
            self.update_views()

    # Gestiona mark reviewed.
    def mark_reviewed(self):
        event_id = self._selected_id()
        if event_id is None:
            return
        try:
            self.system.mark_reviewed(event_id)
            self.statusBar().showMessage(
                f"Event {event_id} marked as reviewed", 4000
            )
            self.update_views()
        except ValueError as error:
            self._show_error(str(error))

    # Gestiona undo.
    def undo(self):
        if self.processing_timer.isActive():
            self.processing_timer.stop()
            self.process_all_button.setText("Process full queue")
        description = self.system.last_action_description()
        if description is None:
            self.statusBar().showMessage(
                "No actions to undo", 4000
            )
            return
        if not self.system.undo():
            self.statusBar().showMessage("Could not undo", 4000)
            return
        self.statusBar().showMessage(f"Undone: {description}", 4000)
        self.update_views()

    # Gestiona switch stress mode.
    def _switch_stress_mode(self, active):
        try:
            if active:
                self.system.enable_stress_mode()
                self.statusBar().showMessage(
                    "Stress mode enabled", 4000
                )
            else:
                paused = False
                if self.processing_timer.isActive():
                    self.processing_timer.stop()
                    self.process_all_button.setText("Process full queue")
                    paused = True

                cost = self.system.disable_stress_mode()
                prefix = "Processing paused. " if paused else ""
                self.statusBar().showMessage(
                    f"{prefix}Balance recovered: height from "
                    f"{cost['height_before']} to {cost['height_after']}, "
                    f"{cost['turns']} turns, "
                    f"{cost['nodes_visited']} nodes visited, "
                    f"{cost['passes']} passes",
                    10000,
                )
            self.update_views()
        except ValueError as error:
            self._show_error(str(error))
            self._update_stress_button()

    # Gestiona update stress button.
    def _update_stress_button(self):
        in_stress = self.system.is_in_stress_mode()
        self.stress_button.blockSignals(True)
        self.stress_button.setChecked(in_stress)
        if in_stress:
            self.stress_button.setText("Stress mode: ACTIVE")
        else:
            self.stress_button.setText("Stress mode")
        self.stress_button.blockSignals(False)

    # Gestiona update mode indicator.
    def _update_mode_indicator(self):
        if self.system.is_in_stress_mode():
            self.mode_label.setText("Mode: STRESS")
            self.mode_label.setStyleSheet(
                "color: #c0392b; font-weight: 600; padding-right: 10px;"
            )
        else:
            self.mode_label.setText("Mode: normal")
            self.mode_label.setStyleSheet(
                "color: #52616f; padding-right: 10px;"
            )

    # Gestiona remove event.
    def remove_event(self):
        event_id = self._selected_id()
        if event_id is None:
            return
        answer = QMessageBox.question(
            self, "Remove event",
            f"Event {event_id} cannot be reactivated. Remove it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.system.remove_event(event_id)
            self.statusBar().showMessage(
                f"Event {event_id} removed", 4000
            )
            self.update_views()
        except ValueError as error:
            self._show_error(str(error))

    # Gestiona enqueue report.
    def enqueue_report(self):
        try:
            data = self._read_data(self.report_fields)
            report = Report(
                revision=self.report_fields["revision"].value(),
                **data
            )
            self.system.enqueue_report(report)
            self.statusBar().showMessage(
                "Report added to queue", 4000
            )
            self.update_views()
        except ValueError as error:
            self._show_error(str(error))

    # Gestiona process next report.
    def process_next_report(self):
        self._show_results([self.system.process_next_report()])
        self.update_views()

    # Gestiona process all reports.
    def process_all_reports(self):
        if self.processing_timer.isActive():
            self.processing_timer.stop()
            self.process_all_button.setText("Process full queue")
            self.statusBar().showMessage(
                "Processing paused", 3000
            )
            return
        if not self.system.has_pending_reports():
            self.statusBar().showMessage(
                "No pending reports", 3000
            )
            return
        self.processing_timer.start()
        self.process_all_button.setText("Pause processing")
        self.statusBar().showMessage("Processing queue...", 3000)

    # Gestiona add zone.
    def add_zone(self):
        name = self.zone_name.text().strip()
        if not name:
            self._show_error("The zone name is required")
            return
        if (self.zone_x_min.value() > self.zone_x_max.value()
                or self.zone_y_min.value() > self.zone_y_max.value()):
            self._show_error(
                "Minimum values cannot be greater than maximums"
            )
            return
        zone = Zone(
            name,
            self.zone_x_min.value(), self.zone_y_min.value(),
            self.zone_x_max.value(), self.zone_y_max.value(),
            self.zone_populated.isChecked(),
        )
        try:
            affected = self.system.add_zone(zone)
            self.statusBar().showMessage(
                f"Zone '{name}' added. "
                f"{affected} events changed priority.",
                5000,
            )
            self.update_views()
        except ValueError as error:
            self._show_error(str(error))

    # Gestiona update views.
    def update_views(self):
        self._update_clock()
        self._update_summary()
        self._update_events_table()
        self._update_reports_table()
        self._update_map()
        self._update_comparison()
        self._update_history_table()
        self._update_archive_status()
        self._update_event_buttons()
        self._update_undo_button()
        self._update_stress_button()
        self._update_mode_indicator()
        self._update_versions_table()
        self._update_audit()

    # Gestiona update undo button.
    def _update_undo_button(self):
        can_undo = self.system.can_undo()
        self.undo_button.setEnabled(can_undo)
        if can_undo:
            description = self.system.last_action_description()
            self.undo_button.setToolTip(f"Undo: {description}")
        else:
            self.undo_button.setToolTip("No actions to undo")

    # Gestiona update versions table.
    def _update_versions_table(self):
        try:
            versions = self.version_manager.list()
        except PersistentVersionsError as error:
            self.versions_table.setRowCount(0)
            self.statusBar().showMessage(
                f"Invalid version catalog: {error}", 8000
            )
            self._update_version_buttons()
            return

        self.versions_table.setRowCount(len(versions))
        for row, version in enumerate(versions):
            values = [
                version["name"],
                version["created_at"].replace("T", " ").replace("Z", ""),
                version["active_events"],
                version["historical_events"],
                version["avl_height"],
                "Stress" if version["stress_mode"] else "Normal",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setForeground(QBrush(QColor("#172b4d")))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, version["name"])
                self.versions_table.setItem(row, column, item)
        self._update_version_buttons()

    # Gestiona update version buttons.
    def _update_version_buttons(self):
        selected = self._selected_version() is not None
        self.restore_version_button.setEnabled(selected)
        self.delete_version_button.setEnabled(selected)

    # Gestiona selected version.
    def _selected_version(self):
        row = self.versions_table.currentRow()
        if row < 0:
            return None
        item = self.versions_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # Gestiona update clock.
    def _update_clock(self):
        instant = self.system.clock.instant
        self.clock_label.setText(
            "UTC clock: " + instant.strftime("%Y-%m-%d %H:%M:%S")
        )
        if not self.jump_field.hasFocus():
            self.jump_field.setDateTime(self._qdatetime_from_clock())

    # Gestiona update summary.
    def _update_summary(self):
        metrics = self.system.metrics
        values = {
            "events": self.system.avl.size(),
            "height": self.system.avl.height(),
            "leaves": self.system.avl.number_of_leaves(),
            "queue": self.system.pending_report_count(),
            "corrections": metrics["accepted_corrections"],
            "conflicts": metrics["conflicts"],
            "confirmations": metrics["confirmations"],
            "created": metrics["created_by_report"],
        }
        for key, value in values.items():
            self.summary_labels[key].setText(str(value))
        events = self.system.avl.in_order()
        self._update_tree_graphic()
        if not events:
            self.inorder_text.setPlainText(
                "No events in the AVL yet."
            )
            return
        lines = [
            f"ID {event.event_id} | key {event.calculate_key()} | {event.state}"
            for event in events
        ]
        self.inorder_text.setPlainText("\n".join(lines))

    # Gestiona update events table.
    def _update_events_table(self):
        self._populating_table = True
        try:
            events = self.system.avl.in_order()
            self.events_table.setRowCount(len(events))
            for row, event in enumerate(events):
                values = [
                    event.event_id,
                    f"{event.magnitude:.1f}",
                    f"{event.depth:.1f}",
                    f"{event.x:.1f}",
                    f"{event.y:.1f}",
                    f"P{event.priority}",
                    event.revision,
                    event.state,
                    "Populated" if event.in_populated_zone else "Not populated",
                    "Yes" if event.expensive_access else "No",
                ]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    item.setForeground(QBrush(QColor("#172b4d")))

                    if column == 0:
                        item.setData(Qt.ItemDataRole.UserRole, event.event_id)

                    if column in self._editable_columns:
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                    if column == 9 and event.expensive_access:
                        item.setForeground(QBrush(QColor("#c0392b")))

                    self.events_table.setItem(row, column, item)
        finally:
            self._populating_table = False

    # Gestiona update reports table.
    def _update_reports_table(self):
        reports = list(self.system.report_queue)
        self.reports_table.setRowCount(len(reports))
        for row, report in enumerate(reports):
            values = [
                report.event_id, f"{float(report.magnitude):.1f}",
                report.revision, report.station,
                report.datetime.strftime("%Y-%m-%d %H:%M"),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setForeground(QBrush(QColor("#172b4d")))
                self.reports_table.setItem(row, column, item)

    # Gestiona update map.
    def _update_map(self):
        matrix = self.system.map.matrix_with_events(
            self.system.avl.in_order()
        )
        rows = self.system.map.rows
        columns = self.system.map.columns
        self.map_table.setRowCount(rows)
        self.map_table.setColumnCount(columns)
        colors = {
            ".": QColor("#ffffff"), "P": QColor("#bfe3d5"),
            "N": QColor("#e8d9a8"), "E": QColor("#e56a5d"),
        }
        for row in range(rows):
            for column in range(columns):
                symbol = matrix[row][column]
                item = QTableWidgetItem(symbol)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setForeground(QBrush(QColor("#172b4d")))
                item.setBackground(colors[symbol])
                self.map_table.setItem(row, column, item)
        self.map_table.setHorizontalHeaderLabels(
            [str(i) for i in range(columns)]
        )
        self.map_table.setVerticalHeaderLabels(
            [str(i) for i in range(rows)]
        )

    # Gestiona update comparison.
    def _update_comparison(self):
        avl = self.system.avl
        bst = self._get_comparison_bst()

        values = {
            "avl_height": avl.height(),
            "avl_leaves": avl.number_of_leaves(),
            "avl_root": avl.root.event.event_id if avl.root else "-",
            "avl_nodes": avl.size(),
            "bst_height": bst.height(),
            "bst_leaves": bst.number_of_leaves(),
            "bst_root": bst.root.event.event_id if bst.root else "-",
            "bst_nodes": bst.size(),
        }
        for key, value in values.items():
            self.comparison_labels[key].setText(str(value))
        self._draw_comparison_tree(
            self.comparison_avl_scene, avl.root, "AVL"
        )
        self._draw_comparison_tree(
            self.comparison_bst_scene, bst.root, "BST"
        )
        QTimer.singleShot(
            0,
            lambda: self._fit_scene(
                self.comparison_avl_view, self.comparison_avl_scene
            ),
        )
        QTimer.singleShot(
            0,
            lambda: self._fit_scene(
                self.comparison_bst_view, self.comparison_bst_scene
            ),
        )

    # Gestiona get comparison bst.
    def _get_comparison_bst(self):
        avl_keys = [
            event.calculate_key() for event in self.system.avl.in_order()
        ]
        if self.comparison_bst is not None:
            bst_keys = [
                event.calculate_key()
                for event in self.comparison_bst.in_order()
            ]
            if bst_keys == avl_keys:
                return self.comparison_bst

        bst = BST()
        for event in self.system.avl.in_order():
            bst.insert(event.copy())
        self.comparison_bst = bst
        return bst

    @staticmethod
    # Gestiona fit scene.
    def _fit_scene(view, scene):
        rectangle = scene.itemsBoundingRect().adjusted(-30, -25, 30, 35)
        if rectangle.isEmpty():
            rectangle = scene.sceneRect()
        if rectangle.isEmpty():
            return
        view.resetTransform()
        view.fitInView(rectangle, Qt.AspectRatioMode.KeepAspectRatio)

    # Gestiona draw comparison tree.
    def _draw_comparison_tree(self, scene, root, tree_name):
        scene.clear()
        if root is None:
            text = scene.addText(f"No nodes in the {tree_name}")
            text.setDefaultTextColor(QColor("#52616f"))
            text.setPos(20, 20)
            scene.setSceneRect(0, 0, 500, 120)
            return

        nodes = []

        # Gestiona count.
        def count(node):
            if node is None:
                return 0
            return 1 + count(node.left) + count(node.right)

        total = count(root)
        total_width = max(900.0, 145.0 * total)
        positions = {}
        y_spacing = 105.0

        # Gestiona assign positions.
        def assign_positions(node, level, minimum, maximum):
            if node is None:
                return
            x = (minimum + maximum) / 2.0
            y = 55.0 + level * y_spacing
            positions[id(node)] = (x, y)
            nodes.append(node)
            assign_positions(node.left, level + 1, minimum, x)
            assign_positions(node.right, level + 1, x, maximum)

        assign_positions(root, 0, 80.0, total_width - 80.0)
        link_pen = QPen(QColor("#8aa0b8"), 2)
        for node in nodes:
            x, y = positions[id(node)]
            for child in (node.left, node.right):
                if child is None:
                    continue
                child_x, child_y = positions[id(child)]
                curved_link = QPainterPath()
                curved_link.moveTo(x, y + 30)
                curved_link.cubicTo(
                    x, y + 55, child_x, child_y - 55, child_x, child_y - 30
                )
                scene.addPath(curved_link, link_pen)

        if tree_name == "AVL":
            background, border = QColor("#dcecf8"), QColor("#1967a8")
        else:
            background, border = QColor("#fff1cf"), QColor("#aa6d00")
        for node in nodes:
            x, y = positions[id(node)]
            scene.addRect(
                x - 62, y - 30, 124, 60,
                QPen(border, 2), QBrush(background),
            )
            label = (
                f"ID {node.event.event_id}\n"
                f"K={node.event.calculate_key()}\n"
                f"h={node.height}  bf={node.balance_factor}"
            )
            text = scene.addText(label)
            text.setDefaultTextColor(QColor("#172b4d"))
            font = text.font()
            font.setPointSize(8)
            text.setFont(font)
            rectangle = text.boundingRect()
            text.setPos(
                x - rectangle.width() / 2,
                y - rectangle.height() / 2,
            )
        rectangle = scene.itemsBoundingRect().adjusted(-40, -35, 40, 50)
        scene.setSceneRect(rectangle)
        view = (
            self.comparison_avl_view
            if tree_name == "AVL"
            else self.comparison_bst_view
        )
        view.resetTransform()
        view.fitInView(rectangle, Qt.AspectRatioMode.KeepAspectRatio)

    # Gestiona update history table.
    def _update_history_table(self):
        events = sorted(
            self.system._historical_events.values(),
            key=lambda event: event.event_id
        )
        self.history_table.setRowCount(len(events))
        for row, event in enumerate(events):
            values = [
                event.event_id,
                f"{event.magnitude:.1f}",
                f"P{event.priority}",
                event.revision,
                event.state,
                event.datetime.strftime("%Y-%m-%d %H:%M:%S"),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setForeground(QBrush(QColor("#172b4d")))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, event.event_id)
                self.history_table.setItem(row, column, item)
        self._update_history_detail()

    # Gestiona update archive status.
    def _update_archive_status(self):
        try:
            result = preview_archive(self.system)
        except Exception as error:
            self._previewed_archive = None
            self.archive_branch_button.setEnabled(False)
            self.archive_preview_label.setText(
                f"Could not evaluate the archive: {error}"
            )
            return

        self._previewed_archive = result
        self.archive_branch_button.setEnabled(result["eligible"])
        if result["eligible"]:
            self.archive_preview_label.setText(
                f"Branch ready to archive\n\n"
                f"Root: SIS-{result['root'].event_id:06d}\n"
                f"Depth: {result['depth']}\n"
                f"Events: {result['count']}\n"
                f"IDs: {', '.join(map(str, sorted(result['ids'])))}"
            )
            return

        events = list(self.system._active_events.values())
        low_priority = [event for event in events if event.priority == 1]
        old = [
            event for event in low_priority
            if self.system.clock.age_in_hours(event.datetime)
            > self.system.parameters.t
        ]
        self.archive_preview_label.setText(
            "No branch eligible to archive.\n\n"
            f"Active events: {len(events)}\n"
            f"Low priority: {len(low_priority)}\n"
            f"Low with age greater than T: {len(old)}\n"
            f"Current T: {self.system.parameters.t:.1f} hours"
        )

    # Gestiona update history detail.
    def _update_history_detail(self):
        row = self.history_table.currentRow()
        if row < 0:
            self.history_detail_text.setPlainText(
                "Select an archived event to see its data."
            )
            return
        item = self.history_table.item(row, 0)
        if item is None:
            return
        event_id = item.data(Qt.ItemDataRole.UserRole)
        event = self.system._historical_events.get(event_id)
        if event is None:
            return
        reference = (
            event.reference
            if event.reference is not None
            else "No reference"
        )
        text = (
            f"ID: {event.event_id}\n"
            f"Key: {event.calculate_key()}\n"
            f"Magnitude: {event.magnitude:.1f}\n"
            f"Depth: {event.depth:.1f} km\n"
            f"Epicenter: ({event.x:.1f}, {event.y:.1f})\n"
            f"Datetime UTC: {event.datetime.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Revision: {event.revision}\n"
            f"State: {event.state}\n"
            f"Stations: {', '.join(sorted(event.stations)) or '-'}\n"
            f"Reference: {reference}\n"
            f"Referenced by: "
            f"{', '.join(map(str, sorted(event.referenced_by))) or '-'}"
        )
        self.history_detail_text.setPlainText(text)

    # Gestiona preview archive history.
    def preview_archive_history(self):
        self._update_archive_status()

    # Gestiona archive branch history.
    def archive_branch_history(self):
        result = preview_archive(self.system)
        if not result["eligible"]:
            self.preview_archive_history()
            return
        answer = QMessageBox.question(
            self,
            "Archive branch",
            f"{result['count']} events will be archived: "
            f"{', '.join(map(str, sorted(result['ids'])))}.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            result = archive_branch(self.system)
        except ValueError as error:
            self._show_error(str(error))
            return
        self._previewed_archive = None
        self.archive_branch_button.setEnabled(False)
        self.archive_preview_label.setText(result["message"])
        self.statusBar().showMessage(result["message"], 5000)
        self.update_views()

    # Gestiona update tree graphic.
    def _update_tree_graphic(self):
        self.tree_scene.clear()
        root = self.system.avl.root
        if root is None:
            text = self.tree_scene.addText("No nodes in the AVL yet")
            text.setDefaultTextColor(QColor("#52616f"))
            text.setPos(20, 20)
            self.tree_scene.setSceneRect(0, 0, 500, 120)
            return

        total = self.system.avl.size()
        total_width = max(1200.0, 150.0 * total)
        margin_x = 70.0
        y_spacing = 110.0
        radius = 30.0

        positions = {}

        # Gestiona assign positions.
        def assign_positions(node, level, x_min, x_max):
            if node is None:
                return
            x = (x_min + x_max) / 2.0
            y = 70.0 + level * y_spacing
            positions[id(node)] = (x, y)
            assign_positions(node.left, level + 1, x_min, x)
            assign_positions(node.right, level + 1, x, x_max)

        assign_positions(root, 0, margin_x, total_width - margin_x)

        priority_colors = {
            3: ("#fdecea", "#c0392b"),
            2: ("#fef5e7", "#b9770e"),
            1: ("#eafaf1", "#1e8449"),
        }

        link_pen = QPen(QColor("#8aa0b8"), 2)
        link_pen.setCapStyle(Qt.PenCapStyle.RoundCap)

        # Gestiona draw links.
        def draw_links(node):
            if node is None:
                return
            x, y = positions[id(node)]
            for child in (node.left, node.right):
                if child is not None:
                    cx, cy = positions[id(child)]
                    path = QPainterPath()
                    path.moveTo(x, y + radius - 4)
                    path.cubicTo(
                        x, y + y_spacing * 0.6,
                        cx, cy - y_spacing * 0.6,
                        cx, cy - radius + 4,
                    )
                    self.tree_scene.addPath(path, link_pen)
            draw_links(node.left)
            draw_links(node.right)

        draw_links(root)

        # Gestiona draw nodes.
        def draw_nodes(node):
            if node is None:
                return

            x, y = positions[id(node)]

            if self.system.is_in_stress_mode():
                background, border = "#c3c3c3", "#ae6c65"
            else:
                background, border = priority_colors.get(
                    node.event.priority, ("#dcecf8", "#1967a8")
                )

            self.tree_scene.addEllipse(
                x - radius, y - radius,
                radius * 2, radius * 2,
                QPen(QColor(border), 2),
                QBrush(QColor(background)),
            )

            label = (
                f"ID {node.event.event_id}\nP={node.event.priority}"
            )
            text = self.tree_scene.addText(label)
            text.setDefaultTextColor(QColor("#172b4d"))
            font = text.font()
            font.setPointSize(9)
            text.setFont(font)
            text_rect = text.boundingRect()
            text.setPos(
                x - text_rect.width() / 2,
                y - text_rect.height() / 2,
            )

            draw_nodes(node.left)
            draw_nodes(node.right)

        draw_nodes(root)

        rectangle = self.tree_scene.itemsBoundingRect().adjusted(
            -60, -40, 60, 120
        )
        self.tree_scene.setSceneRect(rectangle)

    # Gestiona reset tree view.
    def _reset_tree_view(self):
        self.tree_view.resetTransform()
        rect = self.tree_scene.itemsBoundingRect().adjusted(
            -40, -30, 40, 30
        )
        if rect.isEmpty():
            rect = self.tree_scene.sceneRect()
        self.tree_view.fitInView(
            rect, Qt.AspectRatioMode.KeepAspectRatio
        )

    # Gestiona update event buttons.
    def _update_event_buttons(self):
        has_selection = self._selected_id() is not None
        self.review_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)

    # Gestiona selected id.
    def _selected_id(self):
        row = self.events_table.currentRow()
        if row < 0:
            return None
        item = self.events_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # Gestiona show results.
    def _show_results(self, results):
        lines = []
        for index, result in enumerate(results, start=1):
            event = result.get("event")
            event_text = (
                f"Event: {event.event_id}" if event else "Event: -"
            )
            rotations = result.get("rotations", []) or ["none"]
            lines.append(
                f"Step {index}: {result['decision']}\n"
                f"{result['message']}\n"
                f"{event_text}\n"
                f"Rotations: {', '.join(rotations)}"
            )
        self.result_text.setPlainText("\n\n".join(lines))
        self.statusBar().showMessage(
            "Report processing finished", 4000
        )

    # =========================================================
    # PERSISTENT VERSIONS
    # =========================================================

    # Gestiona save version.
    def save_version(self):
        name = self.version_name_field.text()
        try:
            version = self.version_manager.save(name, self.system)
        except PersistentVersionsError as error:
            self._show_error(str(error))
            return
        except ValueError as error:
            self._show_error(str(error))
            return

        self.version_name_field.clear()
        self.update_views()
        self.statusBar().showMessage(
            f"Version '{version['name']}' saved", 5000
        )

    # Gestiona restore version.
    def restore_version(self):
        name = self._selected_version()
        if name is None:
            return
        answer = QMessageBox.question(
            self,
            "Restore version",
            f"The current state will be replaced by version '{name}'.\n"
            "You will be able to undo this restoration.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        previous_state = self.system._snapshot()
        try:
            new_system = self.version_manager.restore(
                name, current_system=self.system
            )
        except PersistentVersionsError as error:
            self._show_error(str(error))
            return

        new_system.history.record_action(
            Action(f"restore_version {name}", previous_state)
        )
        self.system = new_system
        self.comparison_bst = None
        self.update_views()
        self.statusBar().showMessage(
            f"Version '{name}' restored", 5000
        )

    # Gestiona delete version.
    def delete_version(self):
        name = self._selected_version()
        if name is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete version",
            f"Version '{name}' will be permanently deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.version_manager.delete(name)
        except PersistentVersionsError as error:
            self._show_error(str(error))
            return
        self.update_views()
        self.statusBar().showMessage(
            f"Version '{name}' deleted", 5000
        )

    # =========================================================
    # PERSISTENCE: save and load JSON
    # =========================================================

    @staticmethod
    # Gestiona data dir.
    def _data_dir():
        root = Path(__file__).resolve().parent.parent.parent
        folder = root / "data"
        folder.mkdir(exist_ok=True)
        return folder

    # Gestiona select json file.
    def _select_json_file(self, title):
        path, _ = QFileDialog.getOpenFileName(
            self,
            title,
            str(self._data_dir()),
            "JSON files (*.json *.JSON);;All files (*)",
        )
        return path

    # Gestiona save json.
    def save_json(self):
        suggested = str(self._data_dir() / "sismolab_state.json")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save system state",
            suggested,
            "JSON files (*.json)",
        )
        if not path:
            return

        try:
            destination = JsonSaver.save(self.system, path)
            self.statusBar().showMessage(
                f"Saved to: {destination}", 6000
            )
            QMessageBox.information(
                self, "Save successful",
                f"State saved to:\n{destination}",
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Save error",
                f"Could not save the file:\n{e}",
            )

    # Gestiona load json topology.
    def load_json_topology(self):
        path = self._select_json_file("Load topology from JSON")
        if not path:
            return

        try:
            new_system = JsonLoader.load_topology(
                path, current_system=self.system
            )
        except JsonPersistenceError as e:
            QMessageBox.critical(
                self, "Invalid JSON",
                f"The file could not be loaded:\n\n{e}\n\n"
                f"The current system was not modified.",
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self, "Unexpected error",
                f"An error occurred while loading:\n{e}\n\n"
                f"The current system was not modified.",
            )
            return

        self.system = new_system
        self.comparison_bst = None
        self.update_views()
        self.statusBar().showMessage(
            f"Topology loaded from: {path}", 6000
        )
        QMessageBox.information(
            self, "Load successful",
            f"The scenario was restored from:\n{path}\n\n"
            f"Active events: {self.system.avl.size()}\n"
            f"AVL height: {self.system.avl.height()}\n"
            f"Stress mode: "
            f"{'active' if self.system.is_in_stress_mode() else 'inactive'}",
        )

    # Gestiona load json insertions.
    def load_json_insertions(self):
        path = self._select_json_file(
            "Load by insertions from JSON"
        )
        if not path:
            return

        try:
            new_system, bst = JsonLoader.load_by_insertions(path)
        except JsonPersistenceError as e:
            QMessageBox.critical(
                self, "Invalid JSON",
                f"The file could not be loaded:\n\n{e}\n\n"
                f"The current system was not modified.",
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self, "Unexpected error",
                f"An error occurred while loading:\n{e}",
            )
            return

        self.comparison_bst = bst
        self.system = new_system
        self.update_views()

        avl_inorder = [e.event_id for e in new_system.avl.in_order()]
        bst_inorder = [e.event_id for e in bst.in_order()]

        message = (
            f"File: {path}\n\n"
            f"=== AVL (balanced) ===\n"
            f"  Height:  {new_system.avl.height()}\n"
            f"  Nodes:   {new_system.avl.size()}\n"
            f"  Leaves:  {new_system.avl.number_of_leaves()}\n"
            f"  Root:    "
            f"{new_system.avl.root.event.event_id if new_system.avl.root else '-'}\n\n"
            f"=== BST (unbalanced) ===\n"
            f"  Height:  {bst.height()}\n"
            f"  Nodes:   {bst.size()}\n"
            f"  Leaves:  {bst.number_of_leaves()}\n"
            f"  Root:    {bst.root.event.event_id if bst.root else '-'}\n\n"
            f"AVL in-order == BST in-order: "
            f"{'YES' if avl_inorder == bst_inorder else 'NO'}"
        )

        QMessageBox.information(self, "AVL vs BST comparison", message)
        self.statusBar().showMessage(
            f"Insertions loaded from: {path}. "
            f"Go to the 'AVL vs BST' tab to see the trees.", 8000
        )

    # Gestiona show expensive access.
    def _show_expensive_access(self):
        events = self.system.events_with_expensive_access()
        if not events:
            QMessageBox.information(
                self, "Expensive access",
                "There are no high-priority events with expensive access."
            )
            return
        lines = []
        for item in events:
            event = item["event"]
            lines.append(
                f"ID {event.event_id} | P{event.priority} | "
                f"M{event.magnitude:.1f} | depth {item['depth']} | "
                f"L={item['limit']} | visited {item['nodes_visited']}"
            )
        QMessageBox.information(
            self, "Events with expensive access",
            "\n".join(lines)
        )

    # Gestiona show error.
    def _show_error(self, message):
        QMessageBox.warning(self, "Invalid data", message)


# Gestiona excepthook.
def _excepthook(exc_type, exc_value, exc_tb):
    """Prints unhandled exceptions instead of letting Qt abort silently."""
    import traceback
    traceback.print_exception(exc_type, exc_value, exc_tb)


# Gestiona run application.
def run_application():
    """Starts the desktop application."""
    sys.excepthook = _excepthook
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()