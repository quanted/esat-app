import re
import os
import time
import logging

import numpy as np
from PySide6.QtWidgets import (QWidget, QTabWidget, QVBoxLayout, QLabel, QHBoxLayout, QSizePolicy, QFormLayout,
                               QComboBox, QPushButton, QGroupBox, QLineEdit, QMessageBox, QTextEdit, QProgressBar,
                               QStackedLayout, QTableWidget, QTableWidgetItem, QHeaderView, QStyledItemDelegate,
                               QAbstractItemView, QDialog, QApplication)
from PySide6.QtCore import Qt, Signal, QSize, QByteArray, QEasingCurve, QTimer, QObject, Property, QPropertyAnimation, QThread
from PySide6.QtGui import QMovie, QIntValidator, QDoubleValidator, QColor, QBrush, QPen, QPainter

from src.widgets.dataset_selection_widget import DatasetSelectionWidget

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class InfoDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Please wait")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        layout = QVBoxLayout(self)
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        self.setFixedSize(250, 80)


class ModelView(QWidget):
    all_models_completed = Signal()

    def __init__(self, parent=None, controller=None, webviews=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller
        self.webviews = webviews if webviews is not None else []
        self._webview_html_cache = {}  # Store last HTML for each webview

        self._active_row_animations = []
        self.model_progress_widgets = {}  # model_i: (progress_bar, label)
        self._progress_update_counter = {}
        self._last_update_time = {}
        self._batch_completed = False

        self._model_table_data = []

        self.formatted_webviews = {
            'batchloss': self.webviews[0],
            'batchdist': self.webviews[1],
            'batchresiduals': self.webviews[2]
        }

        loader_path = os.path.join("src", "resources", "icons", "loading_spinner.gif")
        self.batchloss_loading, self.batchloss_movie = self._setup_loader(loader_path)
        self.batchdist_loading, self.batchdist_movie = self._setup_loader(loader_path)
        self.batchresiduals_loading, self.batchresiduals_movie = self._setup_loader(loader_path)

        self.batch_plot_stacks = [None, None, None]
        self.batch_loadings = [self.batchloss_loading, self.batchdist_loading, self.batchresiduals_loading]

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

        model_selected_widget = self._create_model_selected_widget()
        right_layout.addWidget(model_selected_widget)
        self.model_dropdown.currentIndexChanged.connect(self.on_dropdown_changed)

        main_layout.addWidget(right_panel, stretch=0, alignment=Qt.AlignTop)

    def _create_model_selected_widget(self):
        group_box = QGroupBox("Model Selection")
        group_box.setStyleSheet("""
            QGroupBox {
                font-size: 12px;
            }
            QLabel, QComboBox {
                font-size: 12px;
            }
        """)
        group_layout = QVBoxLayout(group_box)
        group_layout.setContentsMargins(8, 8, 8, 8)

        self.model_dropdown = QComboBox()
        self.model_dropdown.setEnabled(False)
        group_layout.addWidget(self.model_dropdown)

        self.model_details_layout = QFormLayout()
        self.model_details_labels = {
            "Converged": QLabel("-"),
            "Q(True)": QLabel("-"),
            "Q(Robust)": QLabel("-"),
            "MSE":  QLabel("-")
        }
        for key, label in self.model_details_labels.items():
            self.model_details_layout.addRow(QLabel(f"<b>{key}: </b>"), label)
        group_layout.addLayout(self.model_details_layout)

        return group_box

    def on_dropdown_changed(self, index):
        if index >= 0 and index < len(self._model_table_data):
            self.basemodel_progress_table._selected_row = index
            self.basemodel_progress_table.setCurrentCell(index, 0)
            self.basemodel_progress_table.viewport().update()
            for col in range(self.basemodel_progress_table.columnCount()):
                item = self.basemodel_progress_table.item(index, col)
                if item:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
            for row in range(self.basemodel_progress_table.rowCount()):
                if row != index:
                    for col in range(self.basemodel_progress_table.columnCount()):
                        item = self.basemodel_progress_table.item(row, col)
                        if item:
                            font = item.font()
                            font.setBold(False)
                            item.setFont(font)
            row = self._model_table_data[index]
            self.model_details_labels["Converged"].setText(row[5])
            self.model_details_labels["Q(True)"].setText(row[2])
            self.model_details_labels["Q(Robust)"].setText(row[3])
            self.model_details_labels["MSE"].setText(row[4])
        else:
            for label in self.model_details_labels.values():
                label.setText("-")

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

    def _setup_loader(self, loader_gif_path, loader_size=64):
        """Create a loader QWidget with a centered spinner and full background."""
        container = QWidget()
        container.setStyleSheet("background: #fff;")  # Fill background
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        label = QLabel()
        label.setFixedSize(loader_size, loader_size)
        label.setAlignment(Qt.AlignCenter)
        movie = QMovie(loader_gif_path)
        movie.setScaledSize(QSize(loader_size, loader_size))
        label.setMovie(movie)
        layout.addWidget(label, alignment=Qt.AlignCenter)
        layout.addStretch()
        return container, movie

    def toggle_loader(self, stack: QStackedLayout, movie: QMovie, show: bool):
        """Show or hide the loader in a stacked layout."""
        if show:
            movie.start()
            stack.setCurrentIndex(1)
        else:
            movie.stop()
            stack.setCurrentIndex(0)

    def make_plot_container(self, view, loader):
        container = QWidget()
        container.setStyleSheet("background: #fff;")
        container.setMinimumSize(200, 200)

        stack = QStackedLayout()
        stack.addWidget(view)
        stack.addWidget(loader)
        container.setLayout(stack)
        return None, container, stack

    def _on_run_batch_model(self):

        self.info_dialog = InfoDialog("Setting up batch model runs...", self)
        self.info_dialog.show()
        QApplication.processEvents()
        self._set_cancel_button()

        logger.info("Starting batch model run")
        # Update status bar
        self.parent.statusBar().showMessage("Preparing batch model run...", 3000)
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
        # self.selected_model_label.setVisible(False)
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
        self.parent.statusBar().showMessage(f"Running batch model with: {num_models} models, {num_factors} factors", 3000)

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

        # Connect the finished signal to the main controller's method
        self.controller.main_controller.batchsa_finished.connect(lambda: self.controller.main_controller.run_batch_analysis(dataset))

        if hasattr(self, "info_dialog"):
            self.info_dialog.close()
            del self.info_dialog

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
        min_interval = 1 / 240

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

        if i >= max_iter or progress_data.get("completed", False):
            converged = i < max_iter
            converged_label.setText("Yes" if converged else "No")
            color = "#43A047" if converged else "#E53935"  # Green for success, red for failure
            self.basemodel_progress_table.mark_row_completed(row)
            for col in range(self.basemodel_progress_table.columnCount()):
                item = self.basemodel_progress_table.item(row, col)
                if item:
                    item.setBackground(QColor(color))

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

    def set_webview_html(self, view_name, html):
        """Set HTML and cache it for the given webview name."""
        if view_name in self.formatted_webviews.keys():
            self.formatted_webviews[view_name].setHtml(html)
            self._webview_html_cache[view_name] = html

    def reattach_webviews(self):
        """
        Reattach shared webviews with cached HTML, ensuring correct layout and sizing.
        """

        for idx, view_name in enumerate(['batchloss', 'batchdist', 'batchresiduals']):
            stack = self.batch_plot_stacks[idx]
            webview = self.formatted_webviews[view_name]

            # Detach webview from any previous parent
            webview.setParent(None)
            webview.setMinimumSize(200, 200)
            webview.setMaximumSize(16777215, 16777215)
            webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

            # Remove all widgets from stack
            while stack.count():
                stack.removeWidget(stack.widget(0))
            stack.addWidget(webview)
            stack.addWidget(self.batch_loadings[idx])
            stack.setCurrentIndex(1)

            # Update parent container and layout
            parent = stack.parentWidget()
            if parent:
                parent.resize(400, parent.height())
                parent.adjustSize()
                parent.updateGeometry()
                parent.update()
                if parent.layout():
                    parent.layout().invalidate()
                    parent.updateGeometry()
                    parent.update()
            webview.adjustSize()
            webview.updateGeometry()
            QApplication.processEvents()

            # Restore cached HTML
            html = self._webview_html_cache.get(view_name)
            if view_name == "batchloss":
                self._update_batchloss_plot(html)
            elif view_name == "batchdist":
                self._update_batchdist_plot(html)
            elif view_name == "batchresiduals":
                self._update_batchresiduals_plot(html)

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
        self.run_button.clicked.connect(self._on_run_batch_model)
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
        self.overall_progress_bar.setVisible(False)  # Hide initially
        right_layout.addWidget(self.overall_progress_bar)

        # self.selected_model_label = QLabel("")
        # self.selected_model_label.setAlignment(Qt.AlignCenter)
        # self.selected_model_label.setVisible(False)
        # right_layout.addWidget(self.selected_model_label)

        # Add panels to main layout
        main_layout.addWidget(left_panel, stretch=0)
        main_layout.addWidget(right_panel, stretch=2)

        return self.basemodel_tab

    def _setup_batchanalysis_tab(self):
        self.batchanalysis_tab = QWidget()
        self.batchanalysis_layout = QVBoxLayout(self.batchanalysis_tab)

        # --- Top row: Two plots ---
        top_row = QHBoxLayout()
        vbox0, loss_container, loss_stack = self.make_plot_container(
            self.formatted_webviews['batchloss'], self.batchloss_loading
        )
        vbox1, dist_container, dist_stack = self.make_plot_container(
            self.formatted_webviews['batchdist'], self.batchdist_loading
        )
        top_row.addWidget(loss_container)
        top_row.addWidget(dist_container)
        self.batchanalysis_layout.addLayout(top_row)

        # --- Bottom row: Dropdown + plot ---
        bottom_row = QVBoxLayout()
        vbox2, residual_container, residual_stack = self.make_plot_container(
            self.formatted_webviews['batchresiduals'], self.batchresiduals_loading
        )
        bottom_row.addWidget(residual_container)
        self.feature_dropdown = QComboBox()
        bottom_row.addWidget(self.feature_dropdown)
        self.batchanalysis_layout.addLayout(bottom_row)

        self.batch_plot_stacks = [loss_stack, dist_stack, residual_stack]

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
        self._update_modelanalysis_tab(data)
        self._update_factoranalysis_tab(data)

    def _update_batchloss_plot(self, html=None):
        if html is None:
            dataset_name = self.dataset_selection_widget.selected_dataset
            batch_analysis_dict = getattr(self.controller.main_controller, "batch_analysis_dict", {})
            if not batch_analysis_dict or dataset_name not in batch_analysis_dict:
                logger.error(f"Dataset '{dataset_name}' not found in batch_analysis_dict.")
                html = ""
            else:
                batchanalysis_manager = self.controller.main_controller.batch_analysis_dict[dataset_name]
                self._batch_loss_fig = batchanalysis_manager.loss_plot
                self._batch_loss_fig.update_layout(
                    title=dict(font=dict(size=12), x=0.5, xanchor="center"),
                    width=None,
                    height=None,
                    autosize=True,
                    margin=dict(l=5, r=5, t=30, b=5)
                )
                html = self._batch_loss_fig.to_html(
                    full_html=False, include_plotlyjs='cdn',
                    config={'responsive': True, 'displayModeBar': 'hover'}
                )

        self.toggle_loader(self.batch_plot_stacks[0], self.batchloss_movie, True)

        def hide_spinner(_ok):
            self.toggle_loader(self.batch_plot_stacks[0], self.batchloss_movie, False)
            try:
                self.formatted_webviews['batchloss'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.formatted_webviews['batchloss'].loadFinished.connect(hide_spinner)
        self.set_webview_html("batchloss", html)

    def _update_batchdist_plot(self, html=None):
        if html is None:
            dataset_name = self.dataset_selection_widget.selected_dataset
            batch_analysis_dict = getattr(self.controller.main_controller, "batch_analysis_dict", {})
            if not batch_analysis_dict or dataset_name not in batch_analysis_dict:
                logger.error(f"Dataset '{dataset_name}' not found in batch_analysis_dict.")
                html = ""
            else:
                batchanalysis_manager = self.controller.main_controller.batch_analysis_dict[dataset_name]
                self._batch_dist_fig = batchanalysis_manager.loss_distribution_plot
                self._batch_dist_fig.update_layout(
                    title=dict(font=dict(size=12), x=0.5, xanchor="center"),
                    width=None,
                    height=None,
                    autosize=True,
                    margin=dict(l=5, r=5, t=30, b=5)
                )
                html = self._batch_dist_fig.to_html(
                    full_html=False, include_plotlyjs='cdn',
                    config={'responsive': True, 'displayModeBar': 'hover'}
                )
        self.toggle_loader(self.batch_plot_stacks[1], self.batchdist_movie, True)

        def hide_spinner(_ok):
            self.toggle_loader(self.batch_plot_stacks[1], self.batchdist_movie, False)
            try:
                self.formatted_webviews['batchdist'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.formatted_webviews['batchdist'].loadFinished.connect(hide_spinner)
        self.set_webview_html("batchdist", html)

    def _update_batchresiduals_plot(self, html=None):
        if html is None:
            dataset_name = self.dataset_selection_widget.selected_dataset

            batch_analysis_dict = getattr(self.controller.main_controller, "batch_analysis_dict", {})
            if not batch_analysis_dict or dataset_name not in batch_analysis_dict:
                logger.error(f"Dataset '{dataset_name}' not found in batch_analysis_dict.")
                html = ""
            else:
                feature_list = self.controller.main_controller.dataset_manager.loaded_datasets[
                    dataset_name].input_data_df.columns.tolist() if dataset_name else None
                self.feature_dropdown.clear()
                self.feature_dropdown.addItems(feature_list)

                # Set initial feature plot
                if feature_list:
                    batchanalysis_manager = self.controller.main_controller.batch_analysis_dict[dataset_name]
                    self._batch_residual_fig = batchanalysis_manager.temporal_residual_plot
                    self._batch_residual_fig.update_layout(
                        title=dict(font=dict(size=12), x=0.5, xanchor="center", text=f"Model Residual - Feature {feature_list[0]}"),
                        width=None,
                        height=None,
                        autosize=True,
                        margin=dict(l=5, r=5, t=30, b=5)
                    )
                    html = self._batch_residual_fig.to_html(
                        full_html=False, include_plotlyjs='cdn',
                        config={'responsive': True, 'displayModeBar': 'hover'}
                    )

                    # Update feature plot on dropdown change
                    def on_feature_changed(index):
                        self.toggle_loader(self.batch_plot_stacks[2], self.batchresiduals_movie, True)

                        feature = self.feature_dropdown.currentText()
                        # redraw the feature plot with the selected feature
                        if not feature:
                            logger.warning("No feature selected, skipping update.")
                            return
                        V_primes = batchanalysis_manager.analysis.aggregated_output
                        # Iterate over the V_primes and calculate the residual for the specific feature for all models and update trace
                        for i, v_prime in V_primes.items():
                            if feature not in v_prime:
                                logger.warning(f"Feature '{feature}' not found in V_prime for model {i}.")
                                continue
                            # Get the residuals for the selected feature
                            residuals = batchanalysis_manager.data_handler.input_data_plot[feature] - v_prime[feature]
                            # Update self._batch_residual_fig with the new residuals
                            trace = self._batch_residual_fig.data[i]
                            if trace.name == feature:
                                trace.y = residuals.values
                        self._batch_residual_fig.update_layout(
                            title=dict(font=dict(size=12), x=0.5, xanchor="center", text=f"Model Residual - Feature {feature}")
                        )
                        plot_html = self._batch_residual_fig.to_html(
                            full_html=False, include_plotlyjs='cdn',
                            config={'responsive': True, 'displayModeBar': 'hover'}
                        )
                        self.formatted_webviews['batchresiduals'].loadFinished.connect(hide_spinner)
                        self.set_webview_html("batchresiduals", plot_html)

                    self.feature_dropdown.currentIndexChanged.connect(on_feature_changed)

        self.toggle_loader(self.batch_plot_stacks[2], self.batchresiduals_movie, True)

        def hide_spinner(_ok):
            self.toggle_loader(self.batch_plot_stacks[2], self.batchresiduals_movie, False)
            try:
                self.formatted_webviews['batchresiduals'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.formatted_webviews['batchresiduals'].loadFinished.connect(hide_spinner)
        self.set_webview_html("batchresiduals", html)

    def _update_batchanalysis_tab(self):
        self._update_batchloss_plot()
        self._update_batchdist_plot()
        self._update_batchresiduals_plot()

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
        self._model_table_data = table_data

        if best_row >= 0:
            self.model_dropdown.clear()
            self.model_dropdown.addItems([f"Model {row[0]}" for row in table_data])
            self.model_dropdown.setEnabled(True)
        else:
            self.model_dropdown.clear()
            self.model_dropdown.setEnabled(False)

        self.basemodel_progress_table.rowClicked.connect(self.on_row_clicked)
        self.model_dropdown.currentIndexChanged.connect(self.on_dropdown_changed)

        self.controller.main_controller.batchanalysis_finished.connect(self._update_batchanalysis_tab)
        self._restore_run_button()

    def _set_cancel_button(self):
        if getattr(self, "_batchsa_running", False):
            return  # Prevent double start

        self._batchsa_running = True
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
        self.run_button.clicked.connect(self.cancel_batchsa)

    def _restore_run_button(self):
        # Restore run button
        self._batchsa_running = False
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

    def completed_batch_table(self, table_data, best_row=-1):
        logger.info("Updating completed batch table with results...")
        logger.info(f"Best model: {best_row+1} with Q(True) value: {table_data[best_row][2] if best_row >= 0 else 'N/A'}")

        self.overall_progress_bar.setVisible(False)
        # self.selected_model_label.setVisible(True)
        # if best_row >= 0:
        #     self.selected_model_label.setText(f"Selected Model: {best_row + 1}")
        # else:
        #     self.selected_model_label.setText("No model selected")

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

        # self.selected_model_label.setVisible(True)
        # self.selected_model_label.setText(f"Selected Model: Model {best_row + 1}")
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
            # self.selected_model_label.setText("Selected Model")
            self.model_dropdown.setCurrentIndex(row)
        # else:
        #     self.selected_model_label.setText("No model selected")

    def on_row_doubleclicked(self, row):
        print(f"Row {row} double-clicked")

    def cancel_batchsa(self):
        reply = QMessageBox.question(
            self,
            "Confirm Cancel",
            "Confirm cancelation of batch model run?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            logger.info("BatchSA cancel requested")
            # Show InfoDialog
            self.cancel_info_dialog = InfoDialog("Canceling batch model run...", self)
            self.cancel_info_dialog.show()
            # Connect to batchsa_canceled to close dialog
            if hasattr(self.controller, "main_controller") and hasattr(self.controller.main_controller,
                                                                       "batchsa_canceled"):
                self.controller.main_controller.batchsa_canceled.connect(self._on_batchsa_canceled)
            # Call the controller's cancel method if implemented
            if hasattr(self.controller, "main_controller") and hasattr(self.controller.main_controller, "cancel_batch"):
                self.controller.main_controller.cancel_batch()
        else:
            logger.info("BatchSA cancel aborted by user")

    def _on_batchsa_canceled(self):
        if hasattr(self, "cancel_info_dialog") and self.cancel_info_dialog:
            self.cancel_info_dialog.close()
            del self.cancel_info_dialog
        # Optionally disconnect the signal to avoid duplicate calls
        if hasattr(self.controller, "main_controller") and hasattr(self.controller.main_controller, "batchsa_canceled"):
            self.controller.main_controller.batchsa_canceled.disconnect(self._on_batchsa_canceled)


class HoverableTableWidget(QTableWidget):
    rowClicked = Signal(int)
    rowHovered = Signal(int)
    rowDoubleClicked = Signal(int)

    def __init__(self, *args, selection_color="#ADD8E6", completed_color="#43A047", **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseTracking(True)
        self._hovered_row = -1
        self._selected_row = -1
        self.completed_rows = set()  # Track completed rows
        self.hover_color = QColor("#2196F3")  # Light blue for hover
        self.selection_color = QColor(selection_color)
        self.completed_color = QColor(completed_color)  # Green for completed rows
        self.setSelectionMode(QAbstractItemView.NoSelection)  # Disable default selection behavior
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)

    def mark_row_completed(self, row):
        """Mark a row as completed."""
        self.completed_rows.add(row)
        self.viewport().update()

    def _on_cell_double_clicked(self, row, column):
        self.rowDoubleClicked.emit(row)

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

            if row in self.completed_rows:
                painter.fillRect(rect, self.completed_color)  # Static color for completed rows
            elif row == self._selected_row:
                painter.fillRect(rect, self.selection_color)
            elif row == self._hovered_row:
                painter.fillRect(rect, self.hover_color)

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

