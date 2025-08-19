import logging
import pandas as pd
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QGroupBox, QVBoxLayout, QLabel, QSizePolicy, QTableWidget,
                               QSplitter, QTableWidgetItem, QApplication, QLineEdit)
from PySide6.QtGui import QDoubleValidator
from PySide6.QtCore import Qt

from src.utils import create_loader, toggle_loader, create_plot_container

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ResidualAnalysisSubTab(QWidget):
    def __init__(self, parent=None, controller=None, webviews=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller

        self.webviews = webviews
        self._webview_html_cache = {}

        self.histogram_loading, self.histogram_movie = create_loader()
        self.plot_stack = None

        self.plots_connected = False
        self.stats_table_created = False
        self.residual_df = None
        self.current_row = 0
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # Left: Feature Residual Metrics Table
        left_group = QGroupBox("Feature Residual Metrics")
        left_layout = QVBoxLayout()
        self.feature_table = QTableWidget()
        self.feature_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.feature_table.setSelectionMode(QTableWidget.SingleSelection)
        self.feature_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.feature_table.cellClicked.connect(lambda row, col: self.update_plots_on_row_click())
        left_layout.addWidget(self.feature_table)
        left_group.setLayout(left_layout)
        left_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(left_group)

        # Center: Residual Histogram Plot
        _, plot_container, self.plot_stack = create_plot_container(self.webviews["residual_histogram"], self.histogram_loading)
        plot_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(plot_container)

        # Right: Scaled Residuals Table
        right_group = QGroupBox("Scaled Residuals")
        right_layout = QVBoxLayout()
        self.scaled_table = QTableWidget()
        self.scaled_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(self.scaled_table)

        # Add Absolute Threshold input field
        threshold_layout = QHBoxLayout()
        threshold_label = QLabel("Absolute Threshold:")
        self.threshold_input = QLineEdit()
        self.threshold_input.setValidator(QDoubleValidator())
        self.threshold_input.setText("3.0")
        self.threshold_input.setFixedWidth(60)
        self.threshold_input.editingFinished.connect(lambda: self.set_residuals_table(data=None, update=True))
        threshold_layout.addWidget(threshold_label)
        threshold_layout.addWidget(self.threshold_input)
        threshold_layout.addStretch()
        right_layout.addLayout(threshold_layout)

        right_group.setLayout(right_layout)
        right_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(right_group)

        splitter.setStretchFactor(0, 30)
        splitter.setStretchFactor(1, 45)
        splitter.setStretchFactor(2, 25)

        main_layout.addWidget(splitter)

    def set_webview_html(self, view_name, html):
        """Set HTML and cache it for the given webview name."""
        if view_name in self.webviews.keys() and html:
            logger.info(f"Setting HTML for webview: {view_name}")
            self.webviews[view_name].setHtml(html)
            self._webview_html_cache[view_name] = html

    def set_statistics_table(self, headers, data: pd.DataFrame):
        if data is None:
            self.feature_table.setColumnCount(len(headers))
            self.feature_table.setHorizontalHeaderLabels(headers)
            self.feature_table.setRowCount(0)
            logger.error('Unable to create Residual Feature Statistics table')
        else:
            self.feature_table.setColumnCount(len(headers))
            self.feature_table.setHorizontalHeaderLabels(headers)
            self.feature_table.setRowCount(len(data))
            data = data[headers].values.tolist() if isinstance(data, pd.DataFrame) else data
            for row_idx, row_data in enumerate(data):
                for col_idx, value in enumerate(row_data):
                    # round numeric values to 3 decimal places
                    if isinstance(value, (int, float)):
                        value = round(value, 3)
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.feature_table.setItem(row_idx, col_idx, item)
            if len(data) > 0 and not self.stats_table_created:
                print(f"Setting stats table to 0. Current row: {self.feature_table.currentRow()}. Created: {self.stats_table_created}")
                self.feature_table.selectRow(0)
            # Set table properties
            self.feature_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.feature_table.resizeColumnsToContents()
            self.feature_table.resizeRowsToContents()
            self.feature_table.horizontalHeader().setStretchLastSection(True)
            self.stats_table_created = True

    def set_residuals_table(self, data: pd.DataFrame=None, update=False):
        if data is None and not update:
            self.scaled_table.setColumnCount(3)
            self.scaled_table.setHorizontalHeaderLabels(["Date", "Feature"])
            self.scaled_table.setRowCount(0)
            logger.error('Unable to create Scaled Residuals table')
        else:
            if data is not None and not update:
                self.residual_df = data
            data = self.residual_df.copy()
            data.insert(0, "Date", data.index)
            headers = data.columns.tolist()
            abs_threshold = float(self.threshold_input.text())
            data = data[data[headers[-1]].abs() > abs_threshold]

            self.scaled_table.setColumnCount(len(headers))
            self.scaled_table.setHorizontalHeaderLabels(headers)
            self.scaled_table.setRowCount(len(data))
            data = data[headers].values.tolist() if isinstance(data, pd.DataFrame) else data
            logger.info(f"Setting scaled residuals table with {len(data)} rows and {len(headers)} columns.")
            for row_idx, row_data in enumerate(data):
                for col_idx, value in enumerate(row_data):
                    # round numeric values to 3 decimal places
                    if isinstance(value, (int, float)):
                        value = round(value, 3)
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.scaled_table.setItem(row_idx, col_idx, item)
            # Set table properties
            self.scaled_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.scaled_table.resizeColumnsToContents()
            self.scaled_table.resizeRowsToContents()
            self.scaled_table.horizontalHeader().setStretchLastSection(True)

    def create_histogram_plot(self, fig=None, html=None):
        logger.info("[ResidualAnalysisSubTab] Creating histogram plot.")
        feature_idx = self.feature_table.currentRow() if self.feature_table.currentRow() >= 0 else 0
        if fig is None:
            try:
                fig, residuals_df = self.controller.main_controller.selected_modelanalysis_manager.plots[f"residual_histogram_{feature_idx}"]
                self.set_residuals_table(residuals_df)
            except Exception as e:
                logger.error(f"Error retrieving residual histogram plot: {e}")
                fig = None
                html = ""
        if fig is not None:
            fig.update_layout(
                title=dict(font=dict(size=13)),
                width=None, height=None,
                autosize=True, margin=dict(l=5, r=5, t=30, b=5))
            html = fig.to_html(full_html=False, include_plotlyjs='cdn',
                               config={'responsive': True, 'displayModeBar': 'hover'})

        def hide_spinner(_ok):
            toggle_loader(self.plot_stack, self.histogram_movie, False)
            try:
                self.webviews['residual_histogram'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.webviews['residual_histogram'].loadFinished.connect(hide_spinner)
        self.set_webview_html(view_name='residual_histogram', html=html)

    def reattach_webviews(self):
        """
        Reattach shared webviews with cached HTML, ensuring correct layout and sizing.
        Also clears previous content and triggers plot update functions.
        """
        # Detach all webviews
        for view_name, webview in self.webviews.items():
            logger.info(f"Reattaching webview: {view_name}")
            webview.setHtml("")  # Clear content
            webview.setParent(None)
            webview.setMinimumSize(200, 200)
            webview.setMaximumSize(16777215, 16777215)
            webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            QApplication.processEvents()

        for idx, view_name in enumerate(['residual_histogram']):
            stack = self.plot_stack
            webview = self.webviews[view_name]

            # Remove all widgets from stack
            while stack.count():
                stack.removeWidget(stack.widget(0))
            stack.addWidget(webview)
            stack.addWidget(self.histogram_loading)
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

            # Always clear and trigger plot update
            webview.setHtml("")
            self.create_histogram_plot(html=self._webview_html_cache.get(view_name))

    def on_residual_metrics_ready(self):
        """
        Slot to update the residuals metrics table when residual metrics are ready.
        """
        # Example: feature_metrics should be a dict or list of dicts with headers and data
        columns = ["Feature", "Input Mean", "Input Var", "Est Mean", "Est Var", "RMSE"]
        try:
            logger.info("[ResidualAnalysis SubTab] Residual Metrics ready, updating table.")
            model_metrics = self.controller.main_controller.selected_modelanalysis_manager.analysis.residual_metrics
            self.set_statistics_table(columns, model_metrics)

        except Exception as e:
            logger.error("Residual Metrics not available in the analysis.")
            logger.error(f"Error updating residual metrics table: {e}")

    def refresh_on_activate(self):
        """
        Call this when the subtab is activated to ensure the table and plots are updated.
        If analysis results are available, update directly. Otherwise, trigger analysis.
        """
        logger.info("Refreshing Residual Analysis SubTab on activation.")
        if not self.stats_table_created:
            logger.info("Creating statistics table for Residual Analysis SubTab.")
            self.on_residual_metrics_ready()
            self.stats_table_created = True
        self.update_plots()

    def update_plots(self, feature_idx: int = None):
        """
        Update the plots based on the selected feature index.
        """
        logger.info("Updating plots in Residual Analysis SubTab.")
        if self.controller.main_controller.selected_modelanalysis_manager is None:
            logger.warning("No model analysis manager available.")
            return

        toggle_loader(self.plot_stack, self.histogram_movie, True)
        self.create_histogram_plot()

    def update_plots_on_row_click(self):
        feature_idx = self.feature_table.currentRow()
        if feature_idx >= 0:
            self.controller.main_controller.selected_modelanalysis_manager.run_residual_histogram(feature_idx=feature_idx)
