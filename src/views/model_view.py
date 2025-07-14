import re
import time
import logging
from PySide6.QtWidgets import (QWidget, QTabWidget, QVBoxLayout, QLabel, QHBoxLayout, QSizePolicy, QFormLayout,
                               QComboBox, QPushButton, QGroupBox, QLineEdit, QMessageBox, QTextEdit, QProgressBar,
                               QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, QStyledItemDelegate, QAbstractItemView)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QByteArray, QEasingCurve, QTimer
from PySide6.QtGui import QIntValidator, QDoubleValidator, QColor, QBrush, QPen, QPainter

from src.widgets.dataset_selection_widget import DatasetSelectionWidget

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class ModelView(QWidget):
    all_models_completed = Signal()

    def __init__(self, parent=None, controller=None, webviews=None):
        super().__init__(parent)
        self.controller = controller
        self.webviews = webviews if webviews is not None else []
        self.model_progress_widgets = {}  # model_i: (progress_bar, label)
        self._progress_update_counter = {}
        self._last_update_time = {}
        self._batch_completed = False

        self._setup_ui()

        # Connect to DataManager's data_loaded signal if available
        if self.controller and hasattr(self.controller, "data_manager"):
            data_manager = self.controller.data_manager
            if hasattr(data_manager, "data_loaded"):
                data_manager.data_loaded.connect(self.on_data_loaded)

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Left: Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.South)  # Tabs at the bottom
        self._setup_tabs()
        main_layout.addWidget(self.tabs, stretch=3)

        # --- Right: Controls section ---
        right_panel = QWidget()
        right_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        right_panel.setFixedWidth(220)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setAlignment(Qt.AlignTop)

        # Add DatasetSelectionWidget
        self.dataset_selection_widget = DatasetSelectionWidget(controller=self.controller)
        right_layout.addWidget(self.dataset_selection_widget)

        main_layout.addWidget(right_panel, stretch=0, alignment=Qt.AlignTop)


    def _setup_tabs(self):
        self.base_models_tab = QWidget()
        self.base_models_tab.setLayout(QVBoxLayout())
        self.base_models_tab.layout().addWidget(QLabel("Base Models Content"))

        self.batch_analysis_tab = QWidget()
        self.batch_analysis_tab.setLayout(QVBoxLayout())
        self.batch_analysis_tab.layout().addWidget(QLabel("Batch Analysis Content"))

        self.model_analysis_tab = QWidget()
        self.model_analysis_tab.setLayout(QVBoxLayout())
        self.model_analysis_tab.layout().addWidget(QLabel("Model Analysis Content"))

        self.factor_analysis_tab = QWidget()
        self.factor_analysis_tab.setLayout(QVBoxLayout())
        self.factor_analysis_tab.layout().addWidget(QLabel("Factor Analysis Content"))

        self.tabs.addTab(self._setup_basemodel_tab(), "Base Models")
        self.tabs.addTab(self._setup_batchanalysis_tab(), "Batch Analysis")
        self.tabs.addTab(self._setup_modelanalysis_tab(), "Model Analysis")
        self.tabs.addTab(self._setup_factoranalysis_tab(), "Factor Analysis")

    def _on_run_batch_model(self):
        logger.info("Starting batch model run")
        self.basemodel_progress_table.setUpdatesEnabled(False)
        self._batch_completed = False

        # Get and validate Number of Models
        num_models_text = self.num_models_edit.text()
        num_models = int(num_models_text) if num_models_text.isdigit() else None

        # Get and validate Number of Factors
        num_factors_text = self.num_factors_edit.text()
        num_factors = int(num_factors_text) if num_factors_text.isdigit() else None

        # Get and validate Random Seed (optional)
        random_seed_text = self.random_seed_edit.text()
        random_seed = int(random_seed_text) if random_seed_text.isdigit() else None

        # Algorithm selection
        algorithm = self.algorithm_combo.currentText()

        max_iterations = self.max_iterations_edit.text()
        try:
            max_iterations = int(max_iterations) if max_iterations.isdigit() else None
        except ValueError:
            max_iterations = None

        # Loss Delta
        loss_delta_text = self.loss_delta_edit.text()
        try:
            loss_delta = float(loss_delta_text)
        except ValueError:
            loss_delta = None

        # Iterations
        iterations_text = self.iterations_edit.text()
        iterations = int(iterations_text) if iterations_text.isdigit() else None

        # Clear previous progress
        self.basemodel_progress_table.setRowCount(0)
        self.model_progress_widgets.clear()

        # Pre-populate table with empty/default rows
        for model_i in range(1, num_models+1):
            row = self.basemodel_progress_table.rowCount()
            self.basemodel_progress_table.insertRow(row)

            label = QTableWidgetItem(f"Model {model_i}")
            label.setTextAlignment(Qt.AlignCenter)
            label.setFlags(label.flags() & ~Qt.ItemIsEditable)

            progress_bar = QProgressBar()
            progress_bar.setStyleSheet("""
                QProgressBar {
                    min-height: 10px;
                    max-height: 10px;
                    font-size: 12px;
                    text-align: right;  /* Aligns the % text to the right */
                }
                QProgressBar::chunk {
                    background-color: #2196F3;
                }
            """)
            progress_bar.setMaximum(max_iterations if max_iterations else 1)
            progress_bar.setValue(0)

            progress_widget = QWidget()
            progress_layout = QHBoxLayout(progress_widget)
            progress_layout.setContentsMargins(0, 0, 0, 0)
            progress_layout.setAlignment(Qt.AlignVCenter)
            progress_layout.addWidget(progress_bar)

            qtrue_item = QTableWidgetItem("0.0000")
            qtrue_item.setFlags(qtrue_item.flags() & ~Qt.ItemIsEditable)
            qrobust_item = QTableWidgetItem("0.0000")
            qrobust_item.setFlags(qrobust_item.flags() & ~Qt.ItemIsEditable)
            mse_item = QTableWidgetItem("0.0000")
            mse_item.setFlags(mse_item.flags() & ~Qt.ItemIsEditable)
            for item in (qtrue_item, qrobust_item, mse_item):
                item.setTextAlignment(Qt.AlignCenter)

            converged_label = QTableWidgetItem()
            converged_label.setTextAlignment(Qt.AlignCenter)
            converged_label.setFlags(item.flags() & ~Qt.ItemIsEditable)

            self.basemodel_progress_table.setItem(row, 0, label)
            self.basemodel_progress_table.setCellWidget(row, 1, progress_widget)
            self.basemodel_progress_table.setItem(row, 2, qtrue_item)
            self.basemodel_progress_table.setItem(row, 3, qrobust_item)
            self.basemodel_progress_table.setItem(row, 4, mse_item)
            self.basemodel_progress_table.setItem(row, 5, converged_label)

            self.model_progress_widgets[model_i] = (progress_bar, row, converged_label)

        # Initialize overall progress bar
        # Set a fixed height (e.g., 32 pixels)
        self.overall_progress_bar.setFixedHeight(20)

        # Or use a stylesheet for more customization
        self.overall_progress_bar.setStyleSheet("""
            QProgressBar {
                min-height: 20px;
                max-height: 20px;
                font-size: 14px;
                color: black;
                text-align: center;
                background-color: #f0f0f0;
                border-radius: 0px;
            }
            QProgressBar::chunk {
                background-color: #2196F3;  /* Blue */
                border-radius: 0px;
            }
        """)
        self.selected_model_label.setVisible(False)
        self.overall_progress_bar.setVisible(True)
        self.overall_progress_bar.setMinimum(0)
        self.overall_progress_bar.setMaximum(100)
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setFormat("Overall Progress: 0%")
        self.overall_progress_bar.style().unpolish(self.overall_progress_bar)
        self.overall_progress_bar.style().polish(self.overall_progress_bar)
        self.overall_progress_bar.update()

        missing = []
        if not num_models_text:
            missing.append("Number of Models")
        if not num_factors_text:
            missing.append("Number of Factors")

        if missing:
            QMessageBox.warning(self, "Missing Input", f"Please fill in: {', '.join(missing)}")
            return
        logger.info(f"Running batch model with: {num_models} models, {num_factors} factors")

        # Get selected dataset
        dataset = self.dataset_selection_widget.selected_dataset
        if dataset is None:
            QMessageBox.warning(self, "No Dataset Found", "Please load and select a dataset before running a batch model.")
            return

        # Prepare parameters as needed
        params = {
            "models": num_models,
            "factors": num_factors,
            "seed": random_seed,
            "method": algorithm.lower(),
            "max_iter": max_iterations,
            "converge_delta": loss_delta,
            "converge_n": iterations,
            'init_method': 'col_means',
            'init_norm': False,
            "progress_callback": self.progress_callback
        }

        # Call run_batch on the controller
        batchsa_manager = self.controller.main_controller.run_batch(dataset, **params)
        logger.info(f"BatchSAManager: {batchsa_manager}")
        if batchsa_manager:
            batchsa_manager.progress.connect(self.progress_callback)
        else:
            logger.error("BatchSAManager is None!")

        # Connect the progress signal to the callback
        batchsa_manager.progress.connect(self.progress_callback)
        self.all_models_completed.connect(lambda: QTimer.singleShot(200, self.batch_model_finish))

        self.basemodel_progress_table.setUpdatesEnabled(True)

    def progress_callback(self, progress_data):
        """
        Expects progress_data as a dict:
        {
            "model_i": int,
            "i": int,
            "max_iter": int,
            "qtrue": float,
            "qrobust": float,
            "mse": float,
            "completed": bool
        }
        """
        model_i = progress_data["model_i"]
        i = progress_data["i"]
        max_iter = progress_data["max_iter"]
        qtrue = progress_data["qtrue"]
        qrobust = progress_data["qrobust"]
        mse = progress_data["mse"]

        now = time.monotonic()
        min_interval = 1 / 60  # 50 ms

        if model_i not in self._last_update_time:
            self._last_update_time[model_i] = 0

        elapsed = now - self._last_update_time[model_i]
        update_now = (elapsed > min_interval) or (i == max_iter) or progress_data.get("completed", False)

        if not update_now:
            return

        self._last_update_time[model_i] = now

        progress_bar, row, converged_label = self.model_progress_widgets[model_i]
        progress_bar.setValue(i)

        self.basemodel_progress_table.item(row, 2).setText(f"{qtrue:.4f}")
        self.basemodel_progress_table.item(row, 3).setText(f"{qrobust:.4f}")
        self.basemodel_progress_table.item(row, 4).setText(f"{mse:.4f}")

        # Set converged status when finished
        if i >= max_iter or progress_data.get("completed", False):
            converged = i < max_iter
            converged_label.setText("Yes" if converged else "No")

        # Update the overall progress bar
        completed_models = 0
        total_models = len(self.model_progress_widgets)
        if total_models > 0:
            percent_sum = 0
            for progress_bar, _, converged_label in self.model_progress_widgets.values():
                if converged_label.text():  # Completed
                    completed_models += 1
                    percent_sum += 100
                else:  # Incomplete
                    percent_sum += (progress_bar.value() / progress_bar.maximum()) * 100
            overall_percent = percent_sum / total_models
            self.overall_progress_bar.setValue(int(overall_percent))
            self.overall_progress_bar.setFormat(f"Overall Progress: {int(overall_percent)}%")
        else:
            self.overall_progress_bar.setValue(0)
            self.overall_progress_bar.setFormat("Overall Progress: 0%")

        # Emit signal if all models are complete
        if completed_models == total_models and total_models > 0 and not self._batch_completed:
            self._batch_completed = True
            self.all_models_completed.emit()

    def _setup_basemodel_tab(self):
        self.basemodel_tab = QWidget()
        main_layout = QHBoxLayout(self.basemodel_tab)

        # --- Left: Batch Parameters ---
        left_panel = QGroupBox("Batch Parameters")
        left_panel.setFixedWidth(200)
        left_layout = QVBoxLayout(left_panel)

        form_layout = QFormLayout()

        int_validator = QIntValidator(1, 999999)
        # Number of Models
        self.num_models_edit = QLineEdit("20")
        self.num_models_edit.setValidator(int_validator)
        self.num_models_edit.setPlaceholderText("e.g. 20")
        form_layout.addRow("Number of Models", self.num_models_edit)

        # Number of Factors
        self.num_factors_edit = QLineEdit("6")
        self.num_factors_edit.setValidator(int_validator)
        self.num_factors_edit.setPlaceholderText("e.g. 5")
        form_layout.addRow("Number of Factors", self.num_factors_edit)

        # Optional Random Seed
        self.random_seed_edit = QLineEdit()
        self.random_seed_edit.setValidator(QIntValidator(0, 999999))
        self.random_seed_edit.setPlaceholderText("Optional")
        form_layout.addRow("Random Seed", self.random_seed_edit)

        # Algorithm selection
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["LS-NMF", "WS-NMF"])
        form_layout.addRow("Algorithm", self.algorithm_combo)

        # --- Converge Criteria Group ---
        converge_group = QGroupBox("Converge Criteria")
        converge_layout = QFormLayout(converge_group)

        self.max_iterations_edit = QLineEdit()
        self.max_iterations_edit.setValidator(int_validator)
        self.max_iterations_edit.setText("20000")
        converge_layout.addRow("Max Iterations", self.max_iterations_edit)

        self.loss_delta_edit = QLineEdit()
        self.loss_delta_edit.setValidator(QDoubleValidator(0.0, 1.0, 4))
        self.loss_delta_edit.setText("0.1")
        converge_layout.addRow("Loss Delta", self.loss_delta_edit)

        self.iterations_edit = QLineEdit()
        self.iterations_edit.setValidator(int_validator)
        self.iterations_edit.setText("25")
        converge_layout.addRow("Iterations", self.iterations_edit)

        left_layout.addLayout(form_layout)
        left_layout.addWidget(converge_group)

        # Run button
        self.run_button = QPushButton("Run")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 13px;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #388E3C;
                box-shadow: 0 0 6px #A5D6A7;
            }
        """)
        self.run_button.clicked.connect(self._on_run_batch_model)
        left_layout.addWidget(self.run_button)
        left_layout.addStretch()

        # --- Right: Model Details ---
        right_panel = QGroupBox("Model Details")
        right_layout = QVBoxLayout(right_panel)
        self.basemodel_progress_table = HoverableTableWidget()
        self.basemodel_progress_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.basemodel_progress_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.basemodel_progress_table.setShowGrid(False)
        self.basemodel_progress_table.setStyleSheet("""
            QTableWidget, QHeaderView::section {
                border: none;
            }
            QTableWidget::item {
                border: none;
                font-size: 12px;
            }
        """)
        self.basemodel_progress_table.setColumnCount(6)
        self.basemodel_progress_table.setHorizontalHeaderLabels(["Model", "Progress", "Q(True)", "Q(Robust)", "MSE", "Converged"])
        self.basemodel_progress_table.horizontalHeader().setStretchLastSection(True)
        self.basemodel_progress_table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.basemodel_progress_table, stretch=1)

        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.overall_progress_bar.setValue(0)
        self.overall_progress_bar.setTextVisible(True)
        self.overall_progress_bar.setVisible(False)  # Hide initially
        right_layout.addWidget(self.overall_progress_bar)

        self.selected_model_label = QLabel("")
        self.selected_model_label.setAlignment(Qt.AlignCenter)
        self.selected_model_label.setVisible(False)
        right_layout.addWidget(self.selected_model_label)

        # Add panels to main layout
        main_layout.addWidget(left_panel, stretch=0)
        main_layout.addWidget(right_panel, stretch=2)

        return self.basemodel_tab

    def _setup_batchanalysis_tab(self):
        self.batchanalysis_tab = QWidget()
        self.batchanalysis_layout = QVBoxLayout(self.batchanalysis_tab)
        self.batchanalysis_placeholder = QLabel("No models available")
        self.batchanalysis_layout.addWidget(self.batchanalysis_placeholder)
        return self.batchanalysis_tab

    def _setup_modelanalysis_tab(self):
        self.modelanalysis_tab = QWidget()
        self.modelanalysis_layout = QVBoxLayout(self.modelanalysis_tab)
        self.modelanalysis_placeholder = QLabel("No models available")
        self.modelanalysis_layout.addWidget(self.modelanalysis_placeholder)
        return self.modelanalysis_tab

    def _setup_factoranalysis_tab(self):
        self.factoranalysis_tab = QWidget()
        self.factoranalysis_layout = QVBoxLayout(self.factoranalysis_tab)
        self.factoranalysis_placeholder = QLabel("No models available")
        self.factoranalysis_layout.addWidget(self.factoranalysis_placeholder)
        return self.factoranalysis_tab

    def on_model_loaded(self, data):
        self._update_batchanalysis_tab(data)
        self._update_modelanalysis_tab(data)
        self._update_factoranalysis_tab(data)

    def _update_basemodel_tab(self, data):
        # Update the Base Models tab with new data
        self.basemodel_placeholder.setText(f"Base Models loaded: {len(data)} items")

    def _update_batchanalysis_tab(self, data):
        # Update the Batch Analysis tab with new data
        self.batchanalysis_placeholder.setText(f"Batch Analysis loaded: {len(data)} items")

    def _update_modelanalysis_tab(self, data):
        # Update the Model Analysis tab with new data
        self.modelanalysis_placeholder.setText(f"Model Analysis loaded: {len(data)} items")

    def _update_factoranalysis_tab(self, data):
        # Update the Factor Analysis tab with new data
        self.factoranalysis_placeholder.setText(f"Factor Analysis loaded: {len(data)} items")

    def update_batch_output(self, text):
        # Remove ANSI escape codes
        ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
        clean_text = ansi_escape.sub('', text)
        if '\r' in clean_text:
            last_line = clean_text.split('\r')[-1]
            current = self.basemodel_output.toPlainText().split('\n')
            if current:
                current[-1] = last_line.rstrip('\n')
                self.basemodel_output.setPlainText('\n'.join(current))
            else:
                self.basemodel_output.setPlainText(last_line.rstrip('\n'))
            self.basemodel_output.moveCursor(self.basemodel_output.textCursor().End)
        else:
            self.basemodel_output.append(clean_text.rstrip('\n'))

    def batch_model_finish(self):
        logger.info("Batch model run completed, processing results...")
        # 1. Extract all data as text, converting Progress to "iterations/max_iterations"
        min_qtrue = float('inf')
        best_row = -1
        table_data = []
        max_progress = self.max_iterations_edit.text()
        for model_i, (progress_bar, row, converged_label) in self.model_progress_widgets.items():
            row_data = []
            # Model label
            row_data.append(model_i)
            # Progress as "iterations/max_iterations"
            progress = progress_bar.value()
            row_data.append(f"{progress}/{max_progress}")
            # Q(True), Q(Robust), MSE
            for col in range(2, 5):
                item = self.basemodel_progress_table.item(row, col).text()
                row_data.append(item)
            # Converged
            row_data.append(converged_label.text())
            table_data.append(row_data)
            try:
                qtrue = float(row_data[2])
                if qtrue < min_qtrue:
                    min_qtrue = qtrue
                    best_row = len(table_data) - 1
            except ValueError:
                continue
        QTimer.singleShot(100, lambda: self.completed_batch_table(table_data, best_row))

    def completed_batch_table(self, table_data, best_row=-1):
        logger.info("Updating completed batch table with results...")
        logger.info(f"Best model: {best_row+1} with Q(True) value: {table_data[best_row][2] if best_row >= 0 else 'N/A'}")

        self.overall_progress_bar.setVisible(False)
        self.selected_model_label.setVisible(True)
        if best_row >= 0:
            self.selected_model_label.setText(f"Selected Model: {best_row + 1}")
        else:
            self.selected_model_label.setText("No model selected")

        # 2. Clear and repopulate table with QTableWidgetItems only
        self.basemodel_progress_table.setRowCount(0)
        self.basemodel_progress_table.setHorizontalHeaderLabels([
            "Model", "Iterations", "Q(True)", "Q(Robust)", "MSE", "Converged"
        ])
        for i, row_data in enumerate(table_data):
            self.basemodel_progress_table.insertRow(i)

            for col, value in enumerate(row_data):
                if col == 0:
                    value = f"Model {value}"
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setTextAlignment(Qt.AlignCenter)
                font = item.font()
                if i == best_row:
                    # item.setBackground(QColor("#FFF59D"))
                    font.setBold(True)
                item.setFont(font)
                self.basemodel_progress_table.setItem(i, col, item)

        self.selected_model_label.setVisible(True)
        self.selected_model_label.setText(f"Selected Model: Model {best_row + 1}")
        self.basemodel_progress_table._selected_row = best_row

        # 3. Set custom delegate to draw border around best row
        delegate = BestRowDelegate(best_row, self.basemodel_progress_table)
        self.basemodel_progress_table.setItemDelegate(delegate)
        self.basemodel_progress_table._hovered_row = -1
        self.basemodel_progress_table.viewport().update()
        self.basemodel_progress_table.setMouseTracking(True)
        self.basemodel_progress_table.rowClicked.connect(self.on_row_clicked)

    def on_row_clicked(self, row):
        if row >= 0:
            model_text = self.basemodel_progress_table.item(row, 0).text()
            # Extract just the number
            if model_text.startswith("Model "):
                model_number = model_text.split("Model ")[-1]
            else:
                model_number = model_text
            self.selected_model_label.setText(f"Selected Model: {str(model_number)}")
        else:
            self.selected_model_label.setText("No model selected")


class HoverableTableWidget(QTableWidget):
    rowClicked = Signal(int)
    rowHovered = Signal(int)

    def __init__(self, *args, selection_color="#ADD8E6", **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)
        self._hovered_row = -1
        self._selected_row = -1
        self.hover_color = QColor("#2196F3")  # Light blue for hover
        self.selection_color = QColor(selection_color)
        self.setSelectionMode(QAbstractItemView.NoSelection)  # Disable default selection behavior

    def mouseMoveEvent(self, event):
        index = self.indexAt(event.pos())
        row = index.row()
        if row != self._hovered_row:
            self._hovered_row = row
            self.viewport().update()
            self.rowHovered.emit(row)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hovered_row = -1
        self.viewport().update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        if index.isValid():
            if self._selected_row == index.row():
                self._selected_row = -1  # Deselect if already selected
            else:
                self._selected_row = index.row()
            self.viewport().update()
            self.rowClicked.emit(self._selected_row)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        for row in range(self.rowCount()):
            rect = self.visualItemRect(self.item(row, 0))
            rect.setLeft(0)
            rect.setRight(self.viewport().width())

            for col in range(self.columnCount()):
                item = self.item(row, col)
                if item:
                    font = item.font()
                    if row == self._selected_row:
                        font.setBold(True)
                    else:
                        font.setBold(False)
                    item.setFont(font)

            if row == self._selected_row:
                painter.fillRect(rect, self.selection_color)
            elif row == self._hovered_row:
                for col in range(self.columnCount()):
                    item = self.item(row, col)
                    if item:
                        item.setForeground(QBrush(self.hover_color))
            else:
                for col in range(self.columnCount()):
                    item = self.item(row, col)
                    if item:
                        item.setForeground(QBrush(Qt.white))
        super().paintEvent(event)


class BestRowDelegate(QStyledItemDelegate):
    def __init__(self, best_row, table, border_color="#2196F3", parent=None):
        super().__init__(parent)
        self.best_row = best_row
        self.table = table
        self.border_color = border_color

    def paint(self, painter, option, index):
        # Draw the custom border for the best row
        if index.row() == self.best_row:
            pen = QPen(QColor(self.border_color), 2)
            painter.save()
            painter.setPen(pen)
            rect = option.rect
            painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
            if index.column() == 0:
                painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
            if index.column() == (index.model().columnCount() - 1):
                painter.drawLine(rect.right(), rect.top(), rect.right(), rect.bottom())
            painter.restore()

        # Call the base class's paint method to render the cell content
        super().paint(painter, option, index)