import logging
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QSizePolicy, QApplication

from src.utils import create_loader, toggle_loader, create_plot_container

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class BatchAnalysisTab(QWidget):
    def __init__(self, parent=None, controller=None, webviews=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller
        self.webviews = webviews or {}
        self._webview_html_cache = {}

        self.batchloss_loading, self.batchloss_movie = create_loader()
        self.batchdist_loading, self.batchdist_movie = create_loader()
        self.batchresiduals_loading, self.batchresiduals_movie = create_loader()

        self.batch_plot_stacks = [None, None, None]
        self.loaders = [self.batchloss_loading, self.batchdist_loading, self.batchresiduals_loading]

        self.feature_dropdown = QComboBox()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        # --- Top row: Two plots ---
        top_row = QHBoxLayout()
        _, loss_container, self.loss_stack = create_plot_container(
            self.webviews.get('batchloss'), self.loaders[0] if len(self.loaders) > 0 else QLabel('Loading...')
        )
        _, dist_container, self.dist_stack = create_plot_container(
            self.webviews.get('batchdist'), self.loaders[1] if len(self.loaders) > 1 else QLabel('Loading...')
        )
        top_row.addWidget(loss_container)
        top_row.addWidget(dist_container)
        layout.addLayout(top_row)
        # --- Bottom row: Dropdown + plot ---
        bottom_row = QVBoxLayout()
        _, residual_container, self.residual_stack = create_plot_container(
            self.webviews.get('batchresiduals'), self.loaders[2] if len(self.loaders) > 2 else QLabel('Loading...')
        )

        bottom_row.addWidget(residual_container)
        bottom_row.addWidget(self.feature_dropdown)
        layout.addLayout(bottom_row)
        self.plot_stacks = [self.loss_stack, self.dist_stack, self.residual_stack]

    def update_batchloss_plot(self, html=None):
        toggle_loader(self.loss_stack, self.batchloss_movie, True)
        if html is None and self.parent:
            dataset_name = self.parent.dataset_selection_widget.selected_dataset
            batch_analysis_dict = getattr(self.controller.main_controller, "batch_analysis_dict", {})
            if not batch_analysis_dict or dataset_name not in batch_analysis_dict:
                html = ""
            else:
                batchanalysis_manager = batch_analysis_dict[dataset_name]
                fig = batchanalysis_manager.loss_plot
                fig.update_layout(title=dict(font=dict(size=12), x=0.5, xanchor="center"), width=None, height=None, autosize=True, margin=dict(l=5, r=5, t=30, b=5))
                html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True, 'displayModeBar': 'hover'})
        def hide_spinner(_ok):
            toggle_loader(self.loss_stack, self.batchloss_movie, False)
            try:
                self.webviews['batchloss'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass
        self.webviews['batchloss'].loadFinished.connect(hide_spinner)
        self.set_webview_html(view_name='batchloss', html=html)

    def update_batchdist_plot(self, html=None):
        toggle_loader(self.dist_stack, self.batchdist_movie, True)
        if html is None and self.parent:
            dataset_name = self.parent.dataset_selection_widget.selected_dataset
            batch_analysis_dict = getattr(self.controller.main_controller, "batch_analysis_dict", {})
            if not batch_analysis_dict or dataset_name not in batch_analysis_dict:
                html = ""
            else:
                batchanalysis_manager = batch_analysis_dict[dataset_name]
                fig = batchanalysis_manager.loss_distribution_plot
                fig.update_layout(title=dict(font=dict(size=12), x=0.5, xanchor="center"), width=None, height=None, autosize=True, margin=dict(l=5, r=5, t=30, b=5))
                html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True, 'displayModeBar': 'hover'})
        def hide_spinner(_ok):
            toggle_loader(self.dist_stack, self.batchdist_movie, False)
            try:
                self.webviews['batchdist'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass
        self.webviews['batchdist'].loadFinished.connect(hide_spinner)
        self.set_webview_html(view_name='batchdist', html=html)

    def update_batchresiduals_plot(self, html=None):
        toggle_loader(self.residual_stack, self.batchresiduals_movie, True)
        if html is None and self.parent:
            dataset_name = self.parent.dataset_selection_widget.selected_dataset
            batch_analysis_dict = getattr(self.controller.main_controller, "batch_analysis_dict", {})
            if not batch_analysis_dict or dataset_name not in batch_analysis_dict:
                html = ""
            else:
                feature_list = self.controller.main_controller.dataset_manager.loaded_datasets[dataset_name].input_data_df.columns.tolist() if dataset_name else None
                self.feature_dropdown.clear()
                self.feature_dropdown.addItems(feature_list)
                batchanalysis_manager = batch_analysis_dict[dataset_name]
                if feature_list:
                    fig = batchanalysis_manager.temporal_residual_plot
                    fig.update_layout(title=dict(font=dict(size=12), x=0.5, xanchor="center", text=f"Model Residual - Feature {feature_list[0]}"), width=None, height=None, autosize=True, margin=dict(l=5, r=5, t=30, b=5))
                    html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True, 'displayModeBar': 'hover'})
                    def on_feature_changed(index):
                        toggle_loader(self.residual_stack, self.batchresiduals_movie, True)
                        feature = feature_list[index] if index >= 0 else None
                        if not feature:
                            return
                        V_primes = batchanalysis_manager.analysis.aggregated_output
                        input_y = batchanalysis_manager.data_handler.input_data_plot[feature]
                        for i, trace in enumerate(fig.data):
                            if i == 0:
                                trace.visible = True
                                continue
                            model_v_prime = V_primes[i - 1]
                            if feature in model_v_prime:
                                model_y = model_v_prime[feature]
                                if len(input_y) == len(model_y):
                                    trace.y = input_y.values - model_y.values
                                else:
                                    trace.y = [None] * len(input_y)
                            trace.visible = True
                            trace.name = f"Model {i} - {feature}"
                        fig.update_layout(title=dict(font=dict(size=12), x=0.5, xanchor="center", text=f"Model Residual - Feature {feature}"))
                        plot_html = fig.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True, 'displayModeBar': 'hover'})
                        self.webviews['batchresiduals'].loadFinished.connect(hide_spinner)
                        self.webviews['batchresiduals'].setHtml(plot_html)
                    self.feature_dropdown.currentIndexChanged.connect(on_feature_changed)
        def hide_spinner(_ok):
            toggle_loader(self.residual_stack, self.batchresiduals_movie, False)
            try:
                self.webviews['batchresiduals'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass
        self.webviews['batchresiduals'].loadFinished.connect(hide_spinner)
        self.set_webview_html(view_name='batchresiduals', html=html)

    def update_all(self):
        self.update_batchloss_plot()
        self.update_batchdist_plot()
        self.update_batchresiduals_plot()

    def set_webview_html(self, view_name, html):
        """Set HTML and cache it for the given webview name."""
        if view_name in self.webviews.keys() and html:
            logger.info(f"Setting HTML for webview: {view_name}")
            self.webviews[view_name].setHtml(html)
            self._webview_html_cache[view_name] = html

    def reattach_webviews(self):
        """
        Reattach shared webviews with cached HTML, ensuring correct layout and sizing.
        """
        # Detach all webviews
        for view_name, webview in self.webviews.items():
            webview.setHtml("")  # Clear content
            webview.setParent(None)
            webview.setMinimumSize(200, 200)
            webview.setMaximumSize(16777215, 16777215)
            webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            QApplication.processEvents()

        for idx, view_name in enumerate(['batchloss', 'batchdist', 'batchresiduals']):
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

            # Restore cached HTML
            html = self._webview_html_cache.get(view_name)
            if view_name == "batchloss":
                self.update_batchloss_plot(html)
            elif view_name == "batchdist":
                self.update_batchdist_plot(html)
            elif view_name == "batchresiduals":
                self.update_batchresiduals_plot(html)
