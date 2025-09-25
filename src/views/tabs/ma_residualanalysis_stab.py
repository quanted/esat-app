import os
import pandas as pd
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QGroupBox, QVBoxLayout, QLabel, QSizePolicy, QTableWidget,
                               QSplitter, QTableWidgetItem, QApplication, QLineEdit, QFileDialog)
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest
from PySide6.QtGui import QDoubleValidator
from PySide6.QtCore import Qt, QTimer

from src.utils import create_loader, toggle_loader, create_plot_container
from src.utils.optimization import create_optimized_plotly_html
from src.utils.esat_logger import get_logger


class ResidualAnalysisSubTab(QWidget):
    def __init__(self, parent=None, controller=None, webviews=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller
        
        self.logger = get_logger()

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
        splitter.setStretchFactor(1, 55)
        splitter.setStretchFactor(2, 15)

        main_layout.addWidget(splitter)

    def set_webview_html(self, view_name, html):
        """Set HTML and cache it for the given webview name."""
        if view_name in self.webviews.keys() and html:
            self.logger.info(f"Setting HTML for webview: {view_name}")
            self.webviews[view_name].setHtml(html)
            self._webview_html_cache[view_name] = html
            self.setup_webview_downloads(view_name=view_name, webview=self.webviews[view_name])

    def setup_webview_downloads(self, view_name, webview):
        """Enable download functionality for webviews."""
        if hasattr(webview, 'page'):
            profile = webview.page().profile()
            try:
                profile.downloadRequested.disconnect()
            except Exception:
                pass
            profile.downloadRequested.connect(lambda download: self.handle_download(download, view_name))

    def handle_download(self, download: QWebEngineDownloadRequest, webview_name: str):
        """Handle download requests from webview."""
        suggested_filename = download.suggestedFileName()
        self.logger.info(f"Download requested: {suggested_filename} from webview: {webview_name}")
        # Generate filename based on webview type
        model_id = getattr(self.controller.main_controller, 'current_model_idx', 0)
        project_dir = self.controller.main_controller.current_project.output_directory if self.controller and self.controller.main_controller and self.controller.main_controller.current_project else "."
        plot_dir = os.path.join(project_dir, "plots")
        os.makedirs(plot_dir, exist_ok=True)
        feature_idx = self.feature_table.currentRow() if self.feature_table.currentRow() >= 0 else 0
        feature_label = self.feature_table.item(feature_idx, 0).text() if self.feature_table.columnCount() > 0 and self.feature_table.rowCount() > feature_idx else f"feature{feature_idx}"
        suggested_filename = os.path.join(f"{plot_dir}", suggested_filename or f"residual_distribution_{feature_label}_m{model_id}.png")

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Plot",
            suggested_filename,
            "PNG files (*.png);;SVG files (*.svg);;HTML files (*.html);;All files (*.*)"
        )

        if filename:
            download.setDownloadFileName(filename)
            download.accept()
            self.logger.info(f"Plot download started: {filename}")
        else:
            download.cancel()

    def _fit_splitter_to_content(self):
        """Set splitter sizes based on table content widths."""
        splitter = self.findChild(QSplitter)
        if not splitter:
            return

        total_width = splitter.width()

        # Don't try to resize if splitter doesn't have proper width yet
        if total_width <= 100:
            QTimer.singleShot(100, self._fit_splitter_to_content)
            return

        # Calculate actual content widths
        left_width = 0
        right_width = 0

        # Get left table content width
        if self.feature_table.columnCount() > 0:
            left_width = sum(self.feature_table.columnWidth(i) for i in range(self.feature_table.columnCount()))
            left_width += 40  # Add padding for margins

        # Get right table content width
        if self.scaled_table.columnCount() > 0:
            right_width = sum(self.scaled_table.columnWidth(i) for i in range(self.scaled_table.columnCount()))
            right_width += 40  # Add padding for margins

        # Set minimum widths if tables are empty
        left_width = max(left_width, 200)
        right_width = max(right_width, 180)

        # Calculate center width (remaining space)
        center_width = max(total_width - left_width - right_width, 300)

        # print(f"Fitting splitter: total={total_width}, left={left_width}, center={center_width}, right={right_width}")
        splitter.setSizes([left_width, center_width, right_width])

    def showEvent(self, event):
        """Override showEvent to ensure proper splitter sizing when widget becomes visible."""
        super().showEvent(event)
        if self.stats_table_created:
            QTimer.singleShot(100, self._fit_splitter_to_content)

    def set_statistics_table(self, headers, data: pd.DataFrame):
        if data is None:
            self.feature_table.setColumnCount(len(headers))
            self.feature_table.setHorizontalHeaderLabels(headers)
            self.feature_table.setRowCount(0)
            self.logger.error('Unable to create Residual Feature Statistics table')
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
                    item.setTextAlignment(Qt.AlignCenter)
                    self.feature_table.setItem(row_idx, col_idx, item)
            if len(data) > 0 and not self.stats_table_created:
                print(f"Setting stats table to 0. Current row: {self.feature_table.currentRow()}. Created: {self.stats_table_created}")
                self.feature_table.selectRow(0)
            # Set table properties
            self.feature_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.feature_table.resizeColumnsToContents()
            self.feature_table.resizeRowsToContents()
            self.feature_table.horizontalHeader().setStretchLastSection(False)

            self.stats_table_created = True
            QTimer.singleShot(50, self._fit_splitter_to_content)

    def set_residuals_table(self, data: pd.DataFrame=None, update=False):
        if data is None and not update:
            self.scaled_table.setColumnCount(3)
            self.scaled_table.setHorizontalHeaderLabels(["Date", "Feature"])
            self.scaled_table.setRowCount(0)
            self.logger.error('Unable to create Scaled Residuals table')
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
            self.logger.info(f"Setting scaled residuals table with {len(data)} rows and {len(headers)} columns.")
            for row_idx, row_data in enumerate(data):
                for col_idx, value in enumerate(row_data):
                    # round numeric values to 3 decimal places
                    if isinstance(value, (int, float)):
                        value = round(value, 3)
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.scaled_table.setItem(row_idx, col_idx, item)
            # Set table properties
            self.scaled_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.scaled_table.resizeColumnsToContents()
            self.scaled_table.resizeRowsToContents()
            self.scaled_table.horizontalHeader().setStretchLastSection(False)

            # Fit splitter after table is populated
            QTimer.singleShot(50, self._fit_splitter_to_content)

    def create_histogram_plot(self, fig=None, html=None):
        self.logger.info("[ResidualAnalysisSubTab] Creating histogram plot.")
        feature_idx = self.feature_table.currentRow() if self.feature_table.currentRow() >= 0 else 0
        if fig is None:
            try:
                fig, residuals_df = self.controller.main_controller.selected_modelanalysis_manager.plots[f"residual_histogram_{feature_idx}"]
                self.set_residuals_table(residuals_df)
            except Exception as e:
                self.logger.error(f"Error retrieving residual histogram plot: {e}")
                fig = None
                html = ""
        if fig is not None:
            html = create_optimized_plotly_html(fig, xanchor="center", x=0.5)

        def hide_spinner(_ok):
            toggle_loader(self.plot_stack, self.histogram_movie, False)
            QApplication.processEvents()  # Ensure layout is updated
            QTimer.singleShot(500, self._fit_splitter_to_content)
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
        # Detach the webview
        webview = self.webviews['residual_histogram']
        self.logger.info(f"Reattaching webview: residual_histogram")
        webview.setHtml("")  # Clear content
        # Do NOT call setParent(None) to avoid deletion of the webview
        webview.setParent(None)
        webview.setMinimumSize(0, 0)  # Remove minimum size constraints
        webview.setMaximumSize(16777215, 16777215)
        webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        QApplication.processEvents()

        # Remove all widgets from stack
        while self.plot_stack.count():
            self.plot_stack.removeWidget(self.plot_stack.widget(0))

        # Re-add webview and loading widget
        self.plot_stack.addWidget(webview)
        self.plot_stack.addWidget(self.histogram_loading)
        self.plot_stack.setCurrentIndex(0)  # Show webview by default

        # Ensure webview expands properly
        webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        webview.setMinimumSize(0, 0)

        # Update parent container
        parent = self.plot_stack.parentWidget()
        if parent:
            parent.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            parent.updateGeometry()
            if parent.layout():
                parent.layout().invalidate()
                parent.layout().activate()

        QApplication.processEvents()

        # Clear and trigger plot update
        webview.setHtml("")
        self.create_histogram_plot(html=self._webview_html_cache.get('residual_histogram'))

    def on_residual_metrics_ready(self):
        """
        Slot to update the residuals metrics table when residual metrics are ready.
        """
        # Example: feature_metrics should be a dict or list of dicts with headers and data
        columns = ["Feature", "Input Mean", "Input Var", "Est Mean", "Est Var", "RMSE"]
        try:
            self.logger.info("[ResidualAnalysis SubTab] Residual Metrics ready, updating table.")
            model_metrics = self.controller.main_controller.selected_modelanalysis_manager.analysis.residual_metrics
            self.set_statistics_table(columns, model_metrics)

        except Exception as e:
            self.logger.error("Residual Metrics not available in the analysis.")
            self.logger.error(f"Error updating residual metrics table: {e}")

    def refresh_on_activate(self):
        """
        Call this when the subtab is activated to ensure the table and plots are updated.
        If analysis results are available, update directly. Otherwise, trigger analysis.
        """
        self.logger.info("Refreshing Residual Analysis SubTab on activation.")
        if not self.stats_table_created:
            self.logger.info("Creating statistics table for Residual Analysis SubTab.")
            self.on_residual_metrics_ready()
            self.stats_table_created = True
        self.update_plots()

    def update_plots(self, feature_idx: int = None):
        """
        Update the plots based on the selected feature index.
        """
        self.logger.info("Updating plots in Residual Analysis SubTab.")
        if self.controller.main_controller.selected_modelanalysis_manager is None:
            self.logger.warning("No model analysis manager available.")
            return

        toggle_loader(self.plot_stack, self.histogram_movie, True)
        self.create_histogram_plot()

    def update_plots_on_row_click(self):
        feature_idx = self.feature_table.currentRow()
        if feature_idx >= 0:
            self.controller.main_controller.selected_modelanalysis_manager.run_residual_histogram(feature_idx=feature_idx)
