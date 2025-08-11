import logging
import pandas as pd
from PySide6.QtWidgets import QWidget, QHBoxLayout,  QGroupBox, QVBoxLayout, QLabel, QSizePolicy, QApplication, QTableWidget, QTableWidgetItem, QSplitter
from PySide6.QtCore import Qt

from src.utils import create_loader, toggle_loader, create_plot_container

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class FeatureAnalysisSubTab(QWidget):
    def __init__(self, parent=None, controller=None, webviews=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller
        self.webviews = webviews or {}
        self._webview_html_cache = {}

        self.scatterplot_loading, self.scatterplot_movie = create_loader()
        self.tsplot_loading, self.tsplot_movie = create_loader()

        self.plot_stacks = [None, None]
        self.loaders = [self.scatterplot_loading, self.tsplot_loading]

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        # Left: Table in GroupBox with label
        table_group = QGroupBox("Feature Statistics")
        table_layout = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(0)
        self.table.setRowCount(0)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        table_layout.addWidget(self.table)
        table_group.setLayout(table_layout)
        table_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(table_group)
        # Right: Vertical Splitter for plots
        right_splitter = QSplitter(Qt.Vertical)
        _, scatterplot_container, self.scatterplot_stack = create_plot_container(
            self.webviews.get('obs_pred_scatter'), self.loaders[0] if len(self.loaders) > 0 else QLabel('Loading...')
        )
        _, tsplot_container, self.tsplot_stack = create_plot_container(
            self.webviews.get('obs_pred_ts'), self.loaders[1] if len(self.loaders) > 1 else QLabel('Loading...')
        )
        self.plot_stacks = [self.scatterplot_stack, self.tsplot_stack]
        right_splitter.addWidget(scatterplot_container)
        right_splitter.addWidget(tsplot_container)
        right_splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(right_splitter)
        splitter.setSizes([1, 1])
        right_splitter.setSizes([1, 1])
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def set_modelanalysis_manager(self, manager):
        """
        Set the model analysis manager and reconnect signals.
        """
        # Optionally disconnect old signals
        try:
            self.controller.main_controller.selected_modelanalysis_manager.featureMetricsReady.disconnect(self.on_feature_metrics_ready)
        except Exception:
            pass
        try:
            self.controller.main_controller.selected_modelanalysis_manager.estimatedVsObservedReady.disconnect(self.create_scatter_plot)
        except Exception:
            pass
        try:
            self.controller.main_controller.selected_modelanalysis_manager.estimateTimeseriesReady.disconnect(self.create_ts_plot)
        except Exception:
            pass
        self.controller.main_controller.selected_modelanalysis_manager = manager
        self._setup_signals()

    def _setup_signals(self):
        manager = self.controller.main_controller.selected_modelanalysis_manager
        if manager is None:
            logger.warning("No model analysis manager available for signal setup.")
            return
        manager.featureMetricsReady.connect(self.on_feature_metrics_ready)
        manager.estimatedVsObservedReady.connect(self.create_scatter_plot)
        manager.estimateTimeseriesReady.connect(self.create_ts_plot)

    def set_webview_html(self, view_name, html):
        """Set HTML and cache it for the given webview name."""
        if view_name in self.webviews.keys() and html:
            logger.info(f"Setting HTML for webview: {view_name}")
            self.webviews[view_name].setHtml(html)
            self._webview_html_cache[view_name] = html

    def set_statistics_table(self, headers, data: pd.DataFrame):
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(data))
        data = data[headers].values.tolist() if isinstance(data, pd.DataFrame) else data
        logger.info(f"Setting statistics table with {len(data)} rows and {len(headers)} columns.")
        for row_idx, row_data in enumerate(data):
            for col_idx, value in enumerate(row_data):
                # round numeric values to 3 decimal places
                if isinstance(value, (int, float)):
                    value = round(value, 3)
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)
        if len(data) > 0:
            self.table.selectRow(0)
        # Set table properties
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.resizeColumnsToContents()
        self.table.resizeRowsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def create_scatter_plot(self, fig=None, html=None):
        logger.info(f"[FeatureAnalysis SubTab] Creating scatter plot.")

        feature_idx = self.table.currentRow() if self.table.currentRow() >= 0 else 0
        if fig is None:
            try:
                fig = self.controller.main_controller.selected_modelanalysis_manager.plots[f"estimated_vs_observed_{feature_idx}"]
            except Exception as e:
                logger.error(f"Error retrieving estimated vs observed scatter plot: {e}")
                fig = None
                html = ""
        if fig is not None:
            fig.update_layout(title=dict(font=dict(size=12), x=0.5, xanchor="center"), width=None, height=None,
                              autosize=True, margin=dict(l=5, r=5, t=30, b=5))
            html = fig.to_html(full_html=False, include_plotlyjs='cdn',
                               config={'responsive': True, 'displayModeBar': 'hover'})

        def hide_spinner(_ok):
            toggle_loader(self.plot_stacks[0], self.scatterplot_movie, False)
            try:
                self.webviews['obs_pred_scatter'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.webviews['obs_pred_scatter'].loadFinished.connect(hide_spinner)
        self.set_webview_html(view_name='obs_pred_scatter', html=html)

    def create_ts_plot(self, fig=None, html=None):
        logger.info(f"[FeatureAnalysis SubTab] Creating time series plot.")
        # logger.info(f"[FeatureAnalysis SubTab] create_ts_plot -  fig: {fig}, html: {html}")

        feature_idx = self.table.currentRow() if self.table.currentRow() >= 0 else 0
        if fig is None:
            try:
                fig = self.controller.main_controller.selected_modelanalysis_manager.plots[f"estimate_timeseries_{feature_idx}"]
            except Exception as e:
                logger.error(f"Error retrieving estimated vs observed ts plot: {e}")
                fig = None
                html = ""

        if fig is not None:
            fig.update_layout(
                title=dict(font=dict(size=12), x=0.5, xanchor="center"),
                width=None,
                height=None,
                autosize=True,
                margin=dict(l=5, r=5, t=30, b=5)
            )
            html = fig.to_html(full_html=False, include_plotlyjs='cdn',
                               config={'responsive': True, 'displayModeBar': 'hover'})

        def hide_spinner(_ok):
            toggle_loader(self.plot_stacks[1], self.tsplot_movie, False)
            try:
                self.webviews['obs_pred_ts'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.webviews['obs_pred_ts'].loadFinished.connect(hide_spinner)
        self.set_webview_html(view_name='obs_pred_ts', html=html)

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

        for idx, view_name in enumerate(['obs_pred_scatter', 'obs_pred_ts']):
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
            if view_name == 'obs_pred_scatter':
                self.create_scatter_plot(html=self._webview_html_cache.get(view_name))
            elif view_name == 'obs_pred_ts':
                self.create_ts_plot(html=self._webview_html_cache.get(view_name))

    def on_feature_metrics_ready(self):
        """
        Slot to handle feature metrics data and update the table and plots.
        """
        # Example: feature_metrics should be a dict or list of dicts with headers and data
        columns = ["Features", "Category", "r2", "Intercept", "Intercept SE", "Slope", "Slope SE", "SE",
                   "SE Regression", "KS Normal Residuals", "KS PValue", "KS Statistic"]
        # extract specified columns from dataframe
        try:
            model_metrics = self.controller.main_controller.selected_modelanalysis_manager.analysis.statistics
            self.set_statistics_table(columns, model_metrics)
        except Exception:
            logger.error("Statistics not available in the analysis.")

    def update_feature_metrics(self):
        pass

    def update_plots(self, feature_idx: int = None):
        """
        Update the plots based on the selected feature index.
        """
        if self.controller.main_controller.selected_modelanalysis_manager is None:
            logger.warning("No model analysis manager available.")
            return
        feature_idx = feature_idx if feature_idx is not None else self.table.currentRow()

        toggle_loader(self.plot_stacks[1], self.tsplot_movie, True)
        toggle_loader(self.plot_stacks[0], self.scatterplot_movie, True)

        # Connect update functions of plots to the model analysis manager
        self.controller.main_controller.selected_modelanalysis_manager.estimatedVsObservedReady.connect(self.create_scatter_plot)
        self.controller.main_controller.selected_modelanalysis_manager.estimateTimeseriesReady.connect(self.create_ts_plot)

        self.controller.main_controller.selected_modelanalysis_manager.run_est_obs(feature_idx=feature_idx)
        self.controller.main_controller.selected_modelanalysis_manager.run_est_ts(feature_idx=feature_idx)

    def on_table_click(self, row_idx: int):
        """
        Handle table row click to update plots based on selected feature.
        """
        if row_idx < 0 or row_idx >= self.table.rowCount():
            return
        feature_idx = row_idx
        logger.info(f"Selected feature index: {feature_idx}")
        self.update_plots(feature_idx=feature_idx)

    def refresh_on_activate(self):
        """
        Call this when the subtab is activated to ensure the table and plots are updated.
        If analysis results are available, update directly. Otherwise, trigger analysis.
        """
        manager = self.controller.main_controller.selected_modelanalysis_manager
        if manager is None or manager.analysis is None:
            logger.info("No analysis available, triggering model analysis.")
            # Attempt to trigger model analysis for the current dataset/model
            dataset_name = getattr(self.controller.main_controller, 'current_dataset', None)
            model_idx = getattr(self.controller.main_controller, 'current_model_idx', 0)
            if dataset_name is not None:
                self.controller.main_controller.run_model_analysis(dataset_name, model_idx)
            else:
                logger.warning("No dataset/model index available to trigger model analysis.")
            return
        logger.info("Analysis available, updating table and plots.")
        self.on_feature_metrics_ready()
        self.update_plots()

    def showEvent(self, event):
        """
        Ensure the table and plots are updated when the subtab is shown/activated.
        """
        super().showEvent(event)
        self.refresh_on_activate()
        self.table.itemSelectionChanged.connect(self.update_plots_on_row_click)

    def update_plots_on_row_click(self):
        feature_idx = self.table.currentRow()
        if feature_idx >= 0:
            self.update_plots(feature_idx=feature_idx)
