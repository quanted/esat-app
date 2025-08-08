import time
import logging
import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox, QFormLayout, QLineEdit, QComboBox,
                               QPushButton, QTableWidget, QProgressBar, QLabel, QSizePolicy, QHeaderView,
                               QTableWidgetItem, QMessageBox, QApplication)
from PySide6.QtGui import QIntValidator, QDoubleValidator

from src.widgets.dataset_selection_widget import DatasetSelectionWidget
from src.widgets.hoverable_table import HoverableTableWidget, BestRowDelegate
from src.utils import InfoDialog

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class BatchRunTab(QWidget):
    all_models_completed = Signal()

    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller
        self._active_row_animations = []
        self.model_progress_widgets = {}
        self._progress_update_counter = {}
        self._last_update_time = {}
        self._batch_completed = False

        self.dataset_selection_widget = DatasetSelectionWidget(controller=self.controller)

        self._setup_ui()
        self.run_button.clicked.connect(self._on_run_batch_model)

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)

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
        seed = np.random.randint(0, 999999)
        self.random_seed_edit = QLineEdit()
        self.random_seed_edit.setValidator(QIntValidator(0, 999999))
        self.random_seed_edit.setPlaceholderText(str(seed))
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
        left_layout.addWidget(self.run_button)
        left_layout.addStretch()

        # --- Right: Model Details ---
        right_panel = QGroupBox("Model Details")
        right_layout = QVBoxLayout(right_panel)
        self.basemodel_progress_table = HoverableTableWidget()
        self.basemodel_progress_table.setSortingEnabled(True)
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
        self.overall_progress_bar.setVisible(False)
        right_layout.addWidget(self.overall_progress_bar)
        main_layout.addWidget(left_panel, stretch=0)
        main_layout.addWidget(right_panel, stretch=2)

    def _on_run_batch_model(self):
        self.basemodel_progress_table.clearSelection()
        self.basemodel_progress_table._selected_row = -1

        self.info_dialog = InfoDialog("Setting up batch model runs...", self)
        self.info_dialog.show()
        QApplication.processEvents()
        self._set_cancel_button()

        logger.info("Starting batch model run")
        self.basemodel_progress_table.setUpdatesEnabled(False)
        self._batch_completed = False

        num_models_text = self.num_models_edit.text()
        num_models = int(num_models_text) if num_models_text.isdigit() else None
        num_factors_text = self.num_factors_edit.text()
        num_factors = int(num_factors_text) if num_factors_text.isdigit() else None
        random_seed_text = self.random_seed_edit.text()
        random_seed = int(random_seed_text) if random_seed_text.isdigit() else None
        algorithm = self.algorithm_combo.currentText()
        max_iterations = self.max_iterations_edit.text()
        try:
            max_iterations = int(max_iterations) if max_iterations.isdigit() else None
        except ValueError:
            max_iterations = None
        loss_delta_text = self.loss_delta_edit.text()
        try:
            loss_delta = float(loss_delta_text)
        except ValueError:
            loss_delta = None
        iterations_text = self.iterations_edit.text()
        iterations = int(iterations_text) if iterations_text.isdigit() else None

        self.basemodel_progress_table.setRowCount(0)
        self.model_progress_widgets.clear()
        for model_i in range(1, (num_models or 0)+1):
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
                    text-align: right;
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
            converged_label.setFlags(label.flags() & ~Qt.ItemIsEditable)
            self.basemodel_progress_table.setItem(row, 0, label)
            self.basemodel_progress_table.setCellWidget(row, 1, progress_widget)
            self.basemodel_progress_table.setItem(row, 2, qtrue_item)
            self.basemodel_progress_table.setItem(row, 3, qrobust_item)
            self.basemodel_progress_table.setItem(row, 4, mse_item)
            self.basemodel_progress_table.setItem(row, 5, converged_label)
            self.model_progress_widgets[model_i] = (progress_bar, row, converged_label)

        self.overall_progress_bar.setFixedHeight(20)
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
                background-color: #2196F3;
                border-radius: 0px;
            }
        """)
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

        # Get selected dataset
        dataset = self.dataset_selection_widget.selected_dataset
        if dataset is None:
            QMessageBox.warning(self, "No Dataset Found",
                                "Please load and select a dataset before running a batch model.")
            return

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

        # Connect the finished signal to the main controller's method
        self.controller.main_controller.batchsa_finished.connect(lambda: self.controller.main_controller.run_batch_analysis(dataset))

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

        if hasattr(self, "info_dialog"):
            self.info_dialog.close()
            del self.info_dialog

        model_i = progress_data["model_i"]
        i = progress_data["i"]
        max_iter = progress_data["max_iter"]
        qtrue = progress_data["qtrue"]
        qrobust = progress_data["qrobust"]
        mse = progress_data["mse"]

        now = time.monotonic()
        min_interval = 1 / 60

        if model_i not in self._last_update_time:
            self._last_update_time[model_i] = 0

        elapsed = now - self._last_update_time[model_i]
        update_now = (elapsed > min_interval) or (i == max_iter) or progress_data.get("completed", False)

        if not update_now:
            pass

        self._last_update_time[model_i] = now

        progress_bar, row, converged_label = self.model_progress_widgets[model_i]
        progress_bar.setValue(i)

        self.basemodel_progress_table.item(row, 2).setText(f"{qtrue:.4f}")
        self.basemodel_progress_table.item(row, 3).setText(f"{qrobust:.4f}")
        self.basemodel_progress_table.item(row, 4).setText(f"{mse:.4f}")

        if i >= max_iter or progress_data.get("completed", False):
            converged = i < max_iter
            converged_label.setText("Yes" if converged else "No")
            self.basemodel_progress_table.mark_row_completed(row)

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
            QApplication.processEvents()  # Flush event queue before final update
            self.all_models_completed.emit()

    def batch_model_finish(self):
        logger.info("Batch model run completed, processing results...")
        QApplication.processEvents()  # Flush event queue
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
        dataset = self.dataset_selection_widget.selected_dataset
        self.parent._model_table_data[dataset] = table_data

        if best_row >= 0:
            self.parent.model_dropdown.clear()
            self.parent.model_dropdown.addItems([f"Model {row[0]}" for row in table_data])
            self.parent.model_dropdown.setEnabled(True)
        else:
            self.parent.model_dropdown.clear()
            self.parent.model_dropdown.setEnabled(False)

        self.basemodel_progress_table.rowClicked.connect(self.on_row_clicked)
        self.parent.model_dropdown.currentIndexChanged.connect(self.parent.on_model_changed)

        self.controller.main_controller.batchanalysis_finished.connect(self.parent._update_batchanalysis_tab)
        self._restore_run_button()

    def completed_batch_table(self, table_data, best_row=-1):
        logger.info("Updating completed batch table with results...")
        logger.info(f"Best model: {best_row+1} with Q(True) value: {table_data[best_row][2] if best_row >= 0 else 'N/A'}")

        self.overall_progress_bar.setVisible(False)
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
                    font.setBold(True)
                item.setFont(font)
                self.basemodel_progress_table.setItem(i, col, item)

        self.basemodel_progress_table._selected_row = best_row

        # 3. Set custom delegate to draw border around best row
        delegate = BestRowDelegate(best_row, self.basemodel_progress_table)
        self.basemodel_progress_table.setItemDelegate(delegate)
        self.basemodel_progress_table._hovered_row = -1
        self.basemodel_progress_table.viewport().update()
        self.basemodel_progress_table.setMouseTracking(True)
        self.basemodel_progress_table.rowClicked.connect(self.on_row_clicked)
        self.basemodel_progress_table.rowDoubleClicked.connect(self.on_row_doubleclicked)

        # Highligh best row
        if best_row >= 0:
            self.on_row_clicked(best_row)
            self.basemodel_progress_table.setCurrentCell(best_row, 0)
            self.basemodel_progress_table.setFocus()

    def on_row_clicked(self, row):
        if row >= 0:
            self.parent.model_dropdown.setCurrentIndex(row)

    def on_row_doubleclicked(self, row):
        print(f"Row {row} double-clicked")

    def _set_cancel_button(self):
        self.run_button.setText("Cancel")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                font-size: 13px;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #B71C1C;
                box-shadow: 0 0 6px #FFCDD2;
            }
        """)
        self.run_button.clicked.disconnect()
        self.run_button.clicked.connect(self._restore_run_button)

    def _restore_run_button(self):
        self.run_button.setText("Run")
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
        self.run_button.clicked.disconnect()
        self.run_button.clicked.connect(self._on_run_batch_model)
