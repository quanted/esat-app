import os
import pandas as pd
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, QTableWidget, QTableWidgetItem, QSplitter,
                               QSizePolicy, QGroupBox, QApplication, QFileDialog)
from PySide6.QtWebEngineCore import QWebEngineDownloadRequest
from PySide6.QtCore import Qt
from numpy.ma.core import left_shift

from src.utils import create_loader, toggle_loader, create_plot_container
from src.utils.optimization import create_optimized_plotly_html
from src.utils.esat_logger import get_logger


class FactorSummarySubTab(QWidget):
    def __init__(self, parent=None, controller=None, webviews=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller
        
        self.logger = get_logger()

        self.webviews = webviews
        self._webview_html_cache = {}

        self.profile_loading, self.profile_movie = create_loader()
        self.contrib_loading, self.contrib_movie = create_loader()

        self.plot_stacks = [None, None]
        self.loaders = [self.profile_loading, self.contrib_loading]
        self.plots_connected = False

        self._setup_ui()
        self.controller.main_controller.factors_contributions_finished.connect(self.update_plots)

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # Feature List Table (left)
        self.feature_table = QTableWidget()
        self.feature_table.setColumnCount(1)
        self.feature_table.setHorizontalHeaderLabels(["Features", "Category"])
        self.feature_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.feature_table.verticalHeader().setVisible(False)
        self.feature_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.feature_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.feature_table.itemClicked.connect(self._on_feature_selected)
        # For demo, add placeholder features
        self.feature_table.setRowCount(10)

        table_group = QGroupBox("Features")
        table_layout = QVBoxLayout()
        table_layout.addWidget(self.feature_table)
        table_group.setLayout(table_layout)
        table_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(table_group)

        # Right: Vertical Splitter for plots
        right_splitter = QSplitter(Qt.Vertical)
        _, profiles_container, self.profiles_stack = create_plot_container(
            self.webviews.get('factor_profiles'), self.loaders[0] if len(self.loaders) > 0 else QLabel('Loading...')
        )
        _, contribs_container, self.contribs_stack = create_plot_container(
            self.webviews.get('factor_contributions'), self.loaders[1] if len(self.loaders) > 1 else QLabel('Loading...')
        )
        self.plot_stacks = [self.profiles_stack, self.contribs_stack]
        right_splitter.addWidget(profiles_container)
        right_splitter.addWidget(contribs_container)
        right_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(right_splitter)

        # Set stretch: left 15%, right 85%
        splitter.setStretchFactor(0, 15)
        splitter.setStretchFactor(1, 85)
        main_layout.addWidget(splitter)

    def _on_feature_selected(self, item):
        feature_idx = self.feature_table.currentRow()
        if feature_idx >= 0:
            self.controller.main_controller.selected_modelanalysis_manager.run_factor_contributions(feature_idx=feature_idx)

    def set_webview_html(self, view_name, html):
        """Set HTML and cache it for the given webview name."""
        if view_name in self.webviews.keys() and html is not None:
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
        if webview_name in ['factor_profiles', 'factor_contributions']:
            feature_idx = self.feature_table.currentRow() if self.feature_table.currentRow() >= 0 else 0
            feature_label = self.feature_table.item(feature_idx, 0).text() if self.feature_table.item(feature_idx, 0) else f"feature{feature_idx}"
            suggested_filename = os.path.join(f"{plot_dir}", f"{webview_name}_{feature_label}_m{model_id}.png")
        else:
            suggested_filename = os.path.join(f"{plot_dir}", suggested_filename or f"plot_m{model_id}.png")

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

    def reattach_webviews(self):
        """
        Reattach shared webviews with cached HTML, ensuring correct layout and sizing.
        Also clears previous content and triggers plot update functions.
        """
        # Detach all webviews
        for view_name, webview in self.webviews.items():
            self.logger.info(f"Reattaching webview: {view_name}")
            webview.setHtml("")  # Clear content
            # Do NOT call setParent(None) to avoid deletion of the webview
            # webview.setParent(None)
            webview.setMinimumSize(400, 400)
            webview.setMaximumSize(16777215, 16777215)
            webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            QApplication.processEvents()

        for idx, view_name in enumerate(['factor_profiles', 'factor_contributions']):
            stack = self.plot_stacks[idx]
            webview = self.webviews[view_name]

            # Remove all widgets from stack
            while stack.count():
                stack.removeWidget(stack.widget(0))
            stack.addWidget(webview)
            stack.addWidget(self.loaders[idx])
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
            if view_name == 'factor_profiles':
                self.create_profiles_plot(html=self._webview_html_cache.get(view_name))
            elif view_name == 'factor_contributions':
                self.create_contribs_plot(html=self._webview_html_cache.get(view_name))

    def create_profiles_plot(self, fig=None, html=None):
        self.logger.info(f"[FactorSummary SubTab] Creating factor profiles plot.")
        feature_idx = self.feature_table.currentRow() if self.feature_table.currentRow() >= 0 else 0
        if fig is None:
            try:
                fig, _ = self.controller.main_controller.selected_modelanalysis_manager.plots[
                    f"factor_contributions_{feature_idx}"]
            except Exception as e:
                self.logger.error(f"Error retrieving factor profiles plot: {e}")
                fig = None
                html = ""
        if fig is not None:
            html = create_optimized_plotly_html(fig, x=0.5)

        def hide_spinner(_ok):
            toggle_loader(self.plot_stacks[0], self.profile_movie, False)
            try:
                self.webviews['factor_profiles'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.webviews['factor_profiles'].loadFinished.connect(hide_spinner)
        self.set_webview_html(view_name='factor_profiles', html=html)

    def create_contribs_plot(self, fig=None, html=None):
        self.logger.info(f"[FactorSummary SubTab] Creating factor contributions plot.")
        feature_idx = self.feature_table.currentRow() if self.feature_table.currentRow() >= 0 else 0
        if fig is None:
            try:
                _, fig = self.controller.main_controller.selected_modelanalysis_manager.plots[
                    f"factor_contributions_{feature_idx}"]
            except Exception as e:
                self.logger.error(f"Error factor contribs plot: {e}")
                fig = None
                html = ""

        if fig is not None:
            feature_label = self.feature_table.item(feature_idx, 0).text()
            fig_title = fig.layout.title.text + f" Feature: {feature_label}" if feature_label not in fig.layout.title.text else fig.layout.title.text
            fig.update_layout(title_text=fig_title)
            html = create_optimized_plotly_html(fig, xanchor='center', x=0.5)

        def hide_spinner(_ok):
            toggle_loader(self.plot_stacks[1], self.contrib_movie, False)
            try:
                self.webviews['factor_contributions'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.webviews['factor_contributions'].loadFinished.connect(hide_spinner)
        self.set_webview_html(view_name='factor_contributions', html=html)

    def update_table(self):
        data = self.controller.main_controller.selected_modelanalysis_manager.analysis.statistics
        columns = ["Features", "Category"]
        if data is None:
            self.feature_table.setColumnCount(len(columns))
            self.feature_table.setHorizontalHeaderLabels(columns)
            self.feature_table.setRowCount(0)
            self.logger.error('Unable to create Feature Category table')
        else:
            self.feature_table.setColumnCount(len(columns))
            self.feature_table.setHorizontalHeaderLabels(columns)
            self.feature_table.setRowCount(len(data))
            data = data[columns].values.tolist() if isinstance(data, pd.DataFrame) else data
            self.logger.info(f"Setting statistics table with {len(data)} rows and {len(columns)} columns.")
            for row_idx, row_data in enumerate(data):
                for col_idx, value in enumerate(row_data):
                    # round numeric values to 3 decimal places
                    if isinstance(value, (int, float)):
                        value = round(value, 3)
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setTextAlignment(Qt.AlignCenter)
                    self.feature_table.setItem(row_idx, col_idx, item)
            if len(data) > 0:
                self.feature_table.selectRow(0)
            # Set table properties
            self.feature_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.feature_table.resizeColumnsToContents()
            self.feature_table.resizeRowsToContents()
            self.feature_table.horizontalHeader().setStretchLastSection(False)

    def update_plots(self):
        if self.controller.main_controller.selected_modelanalysis_manager is None:
            self.logger.warning("No model analysis manager available.")
            return

        toggle_loader(self.plot_stacks[0], self.profile_movie, True)
        toggle_loader(self.plot_stacks[1], self.contrib_movie, True)

        self.create_profiles_plot()
        self.create_contribs_plot()

        splitter = self.findChild(QSplitter)
        total_width = splitter.width()
        left_width = int(total_width * 0.15)
        right_width = total_width - left_width
        splitter.setSizes([left_width, right_width])
        QApplication.processEvents()
