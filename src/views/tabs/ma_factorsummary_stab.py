import logging
import pandas as pd
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QHBoxLayout, QTableWidget, QTableWidgetItem, QSplitter,
                               QSizePolicy, QGroupBox, QApplication)
from PySide6.QtCore import Qt

from src.utils import create_loader, toggle_loader, create_plot_container


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FactorSummarySubTab(QWidget):
    def __init__(self, parent=None, controller=None, webviews=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller

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

        # Set stretch: left 20%, right 80%
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 5)
        main_layout.addWidget(splitter)

    def _on_feature_selected(self, item):
        feature_idx = self.feature_table.currentRow()
        if feature_idx >= 0:
            self.controller.main_controller.selected_modelanalysis_manager.run_factor_contributions(feature_idx=feature_idx)

    def set_webview_html(self, view_name, html):
        """Set HTML and cache it for the given webview name."""
        if view_name in self.webviews.keys() and html:
            logger.info(f"Setting HTML for webview: {view_name}")
            self.webviews[view_name].setHtml(html)
            self._webview_html_cache[view_name] = html

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
        logger.info(f"[FactorSummary SubTab] Creating factor profiles plot.")
        feature_idx = self.feature_table.currentRow() if self.feature_table.currentRow() >= 0 else 0
        if fig is None:
            try:
                fig, _ = self.controller.main_controller.selected_modelanalysis_manager.plots[
                    f"factor_contributions_{feature_idx}"]
            except Exception as e:
                logger.error(f"Error retrieving factor profiles plot: {e}")
                fig = None
                html = ""
        if fig is not None:
            fig.update_layout(
                title=dict(font=dict(size=14), x=0.5, xanchor="center"),
                width=None, height=None,
                autosize=True, margin=dict(l=5, r=5, t=30, b=5))
            html = fig.to_html(full_html=False, include_plotlyjs='cdn',
                               config={'responsive': True, 'displayModeBar': 'hover'})

        def hide_spinner(_ok):
            toggle_loader(self.plot_stacks[0], self.profile_movie, False)
            try:
                self.webviews['factor_profiles'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.webviews['factor_profiles'].loadFinished.connect(hide_spinner)
        self.set_webview_html(view_name='factor_profiles', html=html)

    def create_contribs_plot(self, fig=None, html=None):
        logger.info(f"[FactorSummary SubTab] Creating factor contributions plot.")
        feature_idx = self.feature_table.currentRow() if self.feature_table.currentRow() >= 0 else 0
        if fig is None:
            try:
                _, fig = self.controller.main_controller.selected_modelanalysis_manager.plots[
                    f"factor_contributions_{feature_idx}"]
            except Exception as e:
                logger.error(f"Error factor contribs plot: {e}")
                fig = None
                html = ""

        if fig is not None:
            fig.update_layout(
                title=dict(font=dict(size=14), x=0.04),
                width=None,
                height=None,
                autosize=True,
                margin=dict(l=5, r=5, t=30, b=5)
            )
            html = fig.to_html(full_html=False, include_plotlyjs='cdn',
                               config={'responsive': True, 'displayModeBar': 'hover'})

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
            logger.error('Unable to create Feature Category table')
        else:
            self.feature_table.setColumnCount(len(columns))
            self.feature_table.setHorizontalHeaderLabels(columns)
            self.feature_table.setRowCount(len(data))
            data = data[columns].values.tolist() if isinstance(data, pd.DataFrame) else data
            logger.info(f"Setting statistics table with {len(data)} rows and {len(columns)} columns.")
            for row_idx, row_data in enumerate(data):
                for col_idx, value in enumerate(row_data):
                    # round numeric values to 3 decimal places
                    if isinstance(value, (int, float)):
                        value = round(value, 3)
                    item = QTableWidgetItem(str(value))
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.feature_table.setItem(row_idx, col_idx, item)
            if len(data) > 0:
                self.feature_table.selectRow(0)
            # Set table properties
            self.feature_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.feature_table.resizeColumnsToContents()
            self.feature_table.resizeRowsToContents()
            self.feature_table.horizontalHeader().setStretchLastSection(True)

    def update_plots(self):
        if self.controller.main_controller.selected_modelanalysis_manager is None:
            logger.warning("No model analysis manager available.")
            return

        toggle_loader(self.plot_stacks[0], self.profile_movie, True)
        toggle_loader(self.plot_stacks[1], self.contrib_movie, True)

        self.create_profiles_plot()
        self.create_contribs_plot()
