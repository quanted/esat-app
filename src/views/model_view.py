import logging

import numpy as np
from PySide6.QtWidgets import (QWidget, QTabWidget, QVBoxLayout, QLabel, QHBoxLayout, QSizePolicy, QFormLayout,
                               QComboBox, QGroupBox, QStackedLayout, QStyledItemDelegate, QApplication)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMovie, QColor, QPen

from src.widgets.dataset_selection_widget import DatasetSelectionWidget
from src.views.tabs.mv_batchrun_tab import BatchRunTab
from src.views.tabs.mv_batchanalysis_tab import BatchAnalysisTab
from src.views.tabs.mv_model_analysis_tab import ModelAnalysisTab
from src.views.tabs.ma_featureanalysis_stab import FeatureAnalysisSubTab

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


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

        self._model_table_data = {}

        # Batch analysis plots
        self.batch_webviews = {
            'batchloss': self.webviews[0],
            'batchdist': self.webviews[1],
            'batchresiduals': self.webviews[2]
        }

        # Model analysis plots
        self.model_analysis_plots = {
            'obs_pred_scatter': self.webviews[3],
            'obs_pred_ts': self.webviews[4],
            'residual_histogram': self.webviews[5],
            'profile_contrib_plot': self.webviews[6],
            'factor_fingerprints': self.webviews[7],
            'g_plot': self.webviews[8],
            'factor_contribution': self.webviews[9],
        }

        self._setup_ui()

        # Connect to DataManager's data_loaded signal if available
        if self.controller and hasattr(self.controller, "data_manager"):
            data_manager = self.controller.data_manager
            if hasattr(data_manager, "data_loaded"):
                data_manager.data_loaded.connect(self.on_data_loaded)

        self.dataset_selection_widget.dataset_selected.connect(self._on_dataset_changed)

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
        self.model_dropdown.currentIndexChanged.connect(self.on_model_changed)

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

        self.model_dataset_label = QLabel("-")
        self.model_dataset_label.setStyleSheet("font-size: 12px;")
        group_layout.addWidget(QLabel("<b>Dataset:</b>"))
        group_layout.addWidget(self.model_dataset_label)

        self.model_details_layout = QFormLayout()
        self.model_details_labels = {
            ""
            "Converged": QLabel("-"),
            "Q(True)": QLabel("-"),
            "Q(Robust)": QLabel("-"),
            "MSE":  QLabel("-")
        }
        for key, label in self.model_details_labels.items():
            self.model_details_layout.addRow(QLabel(f"<b>{key}: </b>"), label)
        group_layout.addLayout(self.model_details_layout)

        return group_box

    def _on_dataset_changed(self, dataset_name):
        # Update base model table for the new dataset
        self._refresh_base_model_table(dataset_name)
        # Update batch analysis plots
        self.batchanalysis_tab.update_all()
        # Update the model dropdown and details
        model_data = self._model_table_data.get(dataset_name, [])
        self.model_dropdown.clear()
        if model_data:
            self.model_dropdown.addItems([f"Model {row[0]}" for row in model_data])
            self.model_dropdown.setEnabled(True)
            # Highlight best row if available
            best_row = -1
            min_qtrue = float('inf')
            for i, row in enumerate(model_data):
                try:
                    qtrue = float(row[2])
                    if qtrue < min_qtrue:
                        min_qtrue = qtrue
                        best_row = i
                except ValueError:
                    continue
            if best_row >= 0:
                self.model_dropdown.setCurrentIndex(best_row)
                self.batchrun_tab.basemodel_progress_table._selected_row = best_row
                self.batchrun_tab.basemodel_progress_table.setCurrentCell(best_row, 0)
                self.batchrun_tab.basemodel_progress_table.viewport().update()
                self.on_model_changed(best_row)
        else:
            self.model_dropdown.setEnabled(False)
        self.model_dataset_label.setText(dataset_name if dataset_name else "-")
        for label in self.model_details_labels.values():
            label.setText("-")

    def _refresh_base_model_table(self, dataset_name):
        # Fetch model data for the selected dataset
        if dataset_name not in self._model_table_data:
            logger.warning(f"No model data found for dataset: {dataset_name}")
            # Clear the table
            self.batchrun_tab.basemodel_progress_table.setRowCount(0)
            return
        model_data = self._model_table_data[dataset_name]
        self.batchrun_tab.completed_batch_table(model_data, best_row=-1)
        # Enable/disable model dropdown as needed
        if model_data:
            self.model_dropdown.clear()
            self.model_dropdown.addItems([f"Model {row[0]}" for row in model_data])
            self.model_dropdown.setEnabled(True)
        else:
            self.model_dropdown.clear()
            self.model_dropdown.setEnabled(False)

    def on_model_changed(self, index):
        dataset = self.dataset_selection_widget.selected_dataset
        model_table_data = self._model_table_data.get(dataset, [])
        if index >= 0 and index < len(model_table_data):
            self.batchrun_tab.basemodel_progress_table._selected_row = index
            self.batchrun_tab.basemodel_progress_table.setCurrentCell(index, 0)
            self.batchrun_tab.basemodel_progress_table.viewport().update()
            for col in range(self.batchrun_tab.basemodel_progress_table.columnCount()):
                item = self.batchrun_tab.basemodel_progress_table.item(index, col)
                if item:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
            for row in range(self.batchrun_tab.basemodel_progress_table.rowCount()):
                if row != index:
                    for col in range(self.batchrun_tab.basemodel_progress_table.columnCount()):
                        item = self.batchrun_tab.basemodel_progress_table.item(row, col)
                        if item:
                            font = item.font()
                            font.setBold(False)
                            item.setFont(font)
            row = model_table_data[index]
            self.model_details_labels["Converged"].setText(row[5])
            self.model_details_labels["Q(True)"].setText(row[2])
            self.model_details_labels["Q(Robust)"].setText(row[3])
            self.model_details_labels["MSE"].setText(row[4])
            dataset_name = self.dataset_selection_widget.selected_dataset
            self.model_dataset_label.setText(dataset_name if dataset_name else "-")

            # Update the selected model analysis manager
            if dataset in self.controller.main_controller.modelanalysis_manager:
                self.controller.main_controller.selected_modelanalysis_manager = self.controller.main_controller.modelanalysis_manager[dataset].get(index)

            # Trigger plot updates
            if self.controller.main_controller.selected_modelanalysis_manager:
                self.feature_analysis_tab.update_plots(feature_idx=0)
        else:
            for label in self.model_details_labels.values():
                label.setText("-")

        # Update model analysis tab
        self.controller.main_controller.run_model_analysis(dataset_name=dataset, model_idx=index)
        self._update_modelanalysis_tab()

    def _setup_tabs(self):
        # Create and set up the main tabs for the ModelView
        # Batch Run Tab
        self.batchrun_tab = BatchRunTab(parent=self, controller=self.controller)
        self.tabs.addTab(self.batchrun_tab, "Base Models")

        # Batch Analysis Tab
        self.batchanalysis_tab = BatchAnalysisTab(
            parent=self,
            controller=self.controller,
            webviews=self.batch_webviews
        )
        self.tabs.addTab(self.batchanalysis_tab, "Batch Analysis")

        # Model Analysis Tab
        self.modelanalysis_tab = ModelAnalysisTab(parent=self, controller=self.controller, webviews=self.model_analysis_plots)
        self.tabs.addTab(self.modelanalysis_tab, "Model Analysis")

        self.tabs.addTab(self._setup_factoranalysis_tab(), "Factor Analysis")

    def reattach_webviews(self):
        """
        Reattach shared webviews with cached HTML, ensuring correct layout and sizing.
        """
        self.batchanalysis_tab.reattach_webviews()

    def _setup_modelanalysis_tab(self):
        self.modelanalysis_tab = QWidget()
        layout = QVBoxLayout(self.modelanalysis_tab)

        # Create subtabs
        self.modelanalysis_subtabs = QTabWidget()
        self.modelanalysis_subtabs.setTabPosition(QTabWidget.South)  # Tabs at the top

        # Add subtabs with placeholders
        self.feature_analysis_tab = FeatureAnalysisSubTab(parent=self, controller=self.controller)

        self.residual_analysis_tab = QWidget()
        self.residual_analysis_tab.setLayout(QVBoxLayout())
        self.residual_analysis_tab.layout().addWidget(QLabel("Residual Analysis Content"))

        self.factor_analysis_tab_sub = QWidget()
        self.factor_analysis_tab_sub.setLayout(QVBoxLayout())
        self.factor_analysis_tab_sub.layout().addWidget(QLabel("Factor Analysis Content"))

        self.factor_summary_tab = QWidget()
        self.factor_summary_tab.setLayout(QVBoxLayout())
        self.factor_summary_tab.layout().addWidget(QLabel("Factor Summary Content"))

        self.modelanalysis_subtabs.addTab(self.feature_analysis_tab, "Feature Analysis")
        self.modelanalysis_subtabs.addTab(self.residual_analysis_tab, "Residual Analysis")
        self.modelanalysis_subtabs.addTab(self.factor_analysis_tab_sub, "Factor Analysis")
        self.modelanalysis_subtabs.addTab(self.factor_summary_tab, "Factor Summary")

        layout.addWidget(self.modelanalysis_subtabs)
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

    def _update_batchanalysis_tab(self):
        self.batchanalysis_tab.update_all()

    def _update_modelanalysis_tab(self):
        # Update the Model Analysis tab with new data
        self.modelanalysis_tab.feature_analysis_tab.refresh_on_activate()

    def _update_factoranalysis_tab(self, data):
        # Update the Factor Analysis tab with new data
        self.factoranalysis_placeholder.setText(f"Factor Analysis loaded: {len(data)} items")
