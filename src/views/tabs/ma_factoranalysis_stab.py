import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QSizePolicy, QSplitter, QLabel,
                               QApplication, QComboBox, QPushButton, QDialog)
from PySide6.QtCore import Qt

from src.utils import create_loader, toggle_loader, create_plot_container

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FactorAnalysisSubTab(QWidget):
    def __init__(self, parent=None, controller=None, webviews=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller

        self.webviews = webviews
        self._webview_html_cache = {}

        self.profile_loading, self.profile_movie = create_loader()
        self.contrib_loading, self.contrib_movie = create_loader()
        self.fingerprints_loading, self.fingerprints_movie = create_loader()
        self.g_loading, self.g_movie = create_loader()
        self.plot_stacks = [None, None, None, None]
        self.plot_loadings = [self.profile_loading, self.contrib_loading,self.fingerprints_loading, self.g_loading]

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        # Left: Profile/Contribution Plot
        left_group = QGroupBox("Profile\\Contribution Plots")
        left_layout = QVBoxLayout()
        _, profile_container, profile_stack = create_plot_container(self.webviews["profile_plot"],
                                                                   self.profile_loading)
        profile_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(profile_container, stretch=1)

        _, contrib_container, contrib_stack = create_plot_container(self.webviews["contrib_plot"],
                                                                   self.contrib_loading)
        contrib_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        left_layout.addWidget(contrib_container, stretch=1)

        # --- Add factor selection dropdown with label and button ---
        factor_select_layout = QHBoxLayout()
        factor_label = QLabel('Selected Factor')
        factor_select_layout.addWidget(factor_label)
        self.factor_dropdown = QComboBox()
        self.factor_dropdown.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.factor_dropdown.currentIndexChanged.connect(self._on_factor_selected)
        factor_select_layout.addWidget(self.factor_dropdown)
        self.show_all_profiles_btn = QPushButton('Show All Profiles')
        self.show_all_profiles_btn.setStyleSheet("padding: 4px 12px;")
        self.show_all_profiles_btn.clicked.connect(self._on_show_all_profiles)
        factor_select_layout.addWidget(self.show_all_profiles_btn)
        left_layout.addLayout(factor_select_layout)
        # ---

        left_group.setLayout(left_layout)
        left_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(left_group)

        # Right: Factor Fingerprint (top) and G Plot (bottom)
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        # Top: Factor Fingerprint
        fingerprint_group = QGroupBox("Factor Fingerprint Plot")
        fingerprint_layout = QVBoxLayout()
        _, fingerprints_container, fingerprints_stack = create_plot_container(self.webviews["factor_fingerprints"],
                                                                    self.fingerprints_loading)
        fingerprints_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        fingerprint_layout.addWidget(fingerprints_container)
        # --- Add 3D button under the fingerprint plot ---
        self.show_3d_btn = QPushButton('3D')
        self.show_3d_btn.setFixedWidth(60)
        self.show_3d_btn.clicked.connect(self._on_show_3d)
        fingerprint_layout.addWidget(self.show_3d_btn, alignment=Qt.AlignRight)
        # ---
        fingerprint_group.setLayout(fingerprint_layout)
        fingerprint_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(fingerprint_group, stretch=1)

        # Bottom: G Plot
        gplot_group = QGroupBox("G Plot")
        gplot_layout = QVBoxLayout()
        _, g_container, g_stack = create_plot_container(self.webviews["g_plot"], self.g_loading)
        gplot_layout.addWidget(g_container, stretch=1)
        # --- Add X and Y factor dropdowns under the G Plot ---
        g_factor_select_layout = QHBoxLayout()
        g_x_label = QLabel('x')
        g_factor_select_layout.addWidget(g_x_label)
        self.g_x_dropdown = QComboBox()
        self.g_x_dropdown.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.g_x_dropdown.currentIndexChanged.connect(self._on_g_factor_changed)
        g_factor_select_layout.addWidget(self.g_x_dropdown)
        g_y_label = QLabel('y')
        g_factor_select_layout.addWidget(g_y_label)
        self.g_y_dropdown = QComboBox()
        self.g_y_dropdown.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.g_y_dropdown.currentIndexChanged.connect(self._on_g_factor_changed)
        g_factor_select_layout.addWidget(self.g_y_dropdown)
        gplot_layout.addLayout(g_factor_select_layout)
        # ---
        gplot_group.setLayout(gplot_layout)
        gplot_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_layout.addWidget(gplot_group, stretch=1)
        # Wrap right_layout in a QWidget before adding to splitter
        right_widget = QWidget()
        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)

        self.plot_stacks = [profile_stack, contrib_stack, fingerprints_stack, g_stack]

        splitter.setStretchFactor(0, 50)
        splitter.setStretchFactor(1, 50)
        main_layout.addWidget(splitter)

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

        for idx, view_name in enumerate(['profile_plot', 'contrib_plot', 'factor_fingerprints', 'g_plot']):
            stack = self.plot_stacks[idx]
            webview = self.webviews[view_name]
            loading = self.plot_loadings[idx]

            # Remove all widgets from stack
            while stack.count():
                stack.removeWidget(stack.widget(0))
            stack.addWidget(webview)
            stack.addWidget(loading)
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
            if view_name == 'profile_plot':
                self.update_profile_plot(profile_html=self._webview_html_cache.get(view_name))
            elif view_name == 'contrib_plot':
                self.update_contrib_plot(contrib_html=self._webview_html_cache.get(view_name))
            elif view_name == 'factor_fingerprints':
                self.update_fingerprints_plot(html=self._webview_html_cache.get(view_name))
            elif view_name == 'g_plot':
                self.update_g_plot(html=self._webview_html_cache.get(view_name))

    def update_profile_plot(self, profile_fig=None, profile_html=None):
        logger.info("[FactorAnalysisSubTab] Creating profile plots")
        if profile_fig is None:
            factor_idx = self.factor_dropdown.currentData()
            logger.info(f"[FactorAnalysisSubTab] Selected factor index: {factor_idx}")
            try:
                profile_fig, _ = self.controller.main_controller.selected_modelanalysis_manager.plots[f"factor_profile_{factor_idx}"]
            except Exception as e:
                logger.error(f"Error retrieving profile plots: {e}")
                profile_fig = None
                profile_html = ""

        if profile_fig is not None:
            profile_fig.update_layout(
                title=dict(font=dict(size=14), x=0.5, xanchor="center"),
                width=None, height=None,
                autosize=True, margin=dict(l=5, r=5, t=30, b=5),
                legend=dict(
                    x=1.06, y=1.14, xanchor='right', yanchor='top',
                    orientation='h',
                    valign='top',
                    font=dict(size=10),
                    bgcolor='rgba(0,0,0,0)'
                ),
                xaxis=dict(tickangle=45)  # Angle x tick labels to the right
            )
            profile_html = profile_fig.to_html(full_html=False, include_plotlyjs='cdn',
                               config={'responsive': True, 'displayModeBar': 'hover'})

        def hide_profile_spinner(_ok):
            toggle_loader(self.plot_stacks[0], self.profile_movie, False)
            try:
                self.webviews['profile_plot'].loadFinished.disconnect(hide_profile_spinner)
            except Exception:
                pass

        self.webviews['profile_plot'].loadFinished.connect(hide_profile_spinner)
        self.set_webview_html(view_name='profile_plot', html=profile_html)

    def update_contrib_plot(self, contrib_fig=None, contrib_html=None):
        logger.info("[FactorAnalysisSubTab] Creating contrib plots")
        if contrib_fig is None:
            factor_idx = self.factor_dropdown.currentData()
            try:
                _, contrib_fig = self.controller.main_controller.selected_modelanalysis_manager.plots[
                    f"factor_profile_{factor_idx}"]
            except Exception as e:
                logger.error(f"Error retrieving contrib plots: {e}")

                contrib_fig = None
                contrib_html = ""

        if contrib_fig is not None:
            contrib_fig.update_layout(
                title=dict(font=dict(size=14), x=0.5, xanchor="center"),
                width=None, height=None,
                autosize=True, margin=dict(l=5, r=5, t=30, b=5)
            )
            contrib_html = contrib_fig.to_html(full_html=False, include_plotlyjs='cdn',
                               config={'responsive': True, 'displayModeBar': 'hover'})

        def hide_contrib_spinner(_ok):
            toggle_loader(self.plot_stacks[1], self.contrib_movie, False)
            try:
                self.webviews['contrib_plot'].loadFinished.disconnect(hide_contrib_spinner)
            except Exception:
                pass

        self.webviews['contrib_plot'].loadFinished.connect(hide_contrib_spinner)
        self.set_webview_html(view_name='contrib_plot', html=contrib_html)

    def update_fingerprints_plot(self, fig=None, html=None):
        logger.info("[FactorAnalysisSubTab] Creating fingerprints plots")
        if fig is None:
            try:
                fig = self.controller.main_controller.selected_modelanalysis_manager.plots["factor_fingerprints"]
            except Exception as e:
                logger.error(f"Error retrieving fingerprint plot: {e}")
                fig = None
                html = ""

        if fig is not None:
            fig.update_layout(
                title=dict(font=dict(size=14), x=0.5, xanchor="center"),
                width=None, height=None,
                autosize=True, margin=dict(l=5, r=5, t=30, b=5)
            )
            html = fig.to_html(full_html=False, include_plotlyjs='cdn',
                               config={'responsive': True, 'displayModeBar': 'hover'})

        def hide_spinner(_ok):
            toggle_loader(self.plot_stacks[2], self.fingerprints_movie, False)
            try:
                self.webviews['factor_fingerprints'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.webviews['factor_fingerprints'].loadFinished.connect(hide_spinner)
        self.set_webview_html(view_name='factor_fingerprints', html=html)

    def update_g_plot(self, fig=None, html=None):
        logger.info("[FactorAnalysisSubTab] Creating g plot")
        factor_1_idx = self.g_x_dropdown.currentData()
        factor_2_idx = self.g_y_dropdown.currentData()
        factor_1_idx = 1 if factor_1_idx is None else factor_1_idx
        factor_2_idx = 2 if factor_2_idx is None else factor_2_idx
        logger.info(f"[FactorAnalysisSubTab] G Plot factors: x={factor_1_idx}, y={factor_2_idx}")
        if fig is None:
            try:
                fig = self.controller.main_controller.selected_modelanalysis_manager.plots[f"g_space_{factor_1_idx}_{factor_2_idx}"]
            except Exception as e:
                logger.error(f"Error retrieving fingerprint plot: {e}")
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
            toggle_loader(self.plot_stacks[3], self.g_movie, False)
            try:
                self.webviews['g_plot'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.webviews['g_plot'].loadFinished.connect(hide_spinner)
        self.set_webview_html(view_name='g_plot', html=html)

    def populate_factors(self, factors):
        """Populate the factor dropdown with a list of factors (e.g., [1, 2, 3, ...])"""
        self.factor_dropdown.blockSignals(True)
        self.g_x_dropdown.blockSignals(True)
        self.g_y_dropdown.blockSignals(True)

        self.factor_dropdown.clear()
        self.g_x_dropdown.clear()
        self.g_y_dropdown.clear()

        for f in factors:
            self.factor_dropdown.addItem(f"Factor {f}", f)
            self.g_x_dropdown.addItem(f"Factor {f}", f)
            self.g_y_dropdown.addItem(f"Factor {f}", f)
        if factors:
            self.factor_dropdown.setCurrentIndex(0)
            self.g_x_dropdown.setCurrentIndex(0)
            self.g_y_dropdown.setCurrentIndex(1)  # Default to second factor for Y

        self.factor_dropdown.blockSignals(False)
        self.g_x_dropdown.blockSignals(False)
        self.g_y_dropdown.blockSignals(False)

    def _on_factor_selected(self):
        """Handle factor selection change and update plots accordingly."""
        factor = self.factor_dropdown.currentData()
        factor_idx = int(factor.split("_")[-1]) if isinstance(factor, str) else factor
        logger.info(f"[FactorAnalysisSubTab] Factor selected: {factor_idx}")
        if factor_idx is not None:
            toggle_loader(self.plot_stacks[0], self.profile_movie, True)
            toggle_loader(self.plot_stacks[1], self.contrib_movie, True)
            self.controller.main_controller.selected_modelanalysis_manager.run_factor_profile(factor_idx=factor_idx)

    def _on_show_all_profiles(self):
        # Disconnect to avoid duplicate modals
        manager = self.controller.main_controller.selected_modelanalysis_manager
        if 'all_factor_profiles' in manager.plots:
            plot = manager.plots['all_factor_profiles']
            self._create_all_profiles_dialog(plot)
        else:
            manager.allfactorProfileReady.connect(self._create_all_profiles_dialog)
            manager.run_all_factor_profile()

    def _create_all_profiles_dialog(self, plot):
        manager = self.controller.main_controller.selected_modelanalysis_manager
        try:
            manager.allfactorProfileReady.disconnect(self._create_all_profiles_dialog)
        except Exception:
            pass
        num_factors = manager.sa.factors
        selected_model = manager.model_idx
        dialog = QDialog(self)
        dialog.setWindowTitle('All Factor Profiles')
        # Add minimize and maximize buttons to the dialog window
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinMaxButtonsHint)
        width = 900
        height = QApplication.primaryScreen().availableGeometry().height()
        dialog.resize(width, height)
        layout = QVBoxLayout(dialog)
        # Create a webview to show the plot
        from PySide6.QtWebEngineWidgets import QWebEngineView
        webview = QWebEngineView(dialog)
        if plot is not None:
            annotations = [
                dict(
                    text="Conc. of Features",
                    x=-0.07,  # adjust as needed
                    y=0.5,
                    xref="paper", yref="paper",
                    textangle=-90,
                    font=dict(size=14),
                    showarrow=False,
                    align="center"
                ),
                dict(
                    text="% of Features",
                    x=1.01,  # adjust as needed
                    y=0.5,
                    xref="paper", yref="paper",
                    textangle=-90,
                    font=dict(size=14),
                    showarrow=False,
                    align="center"
                )
            ]
            #TODO: labeling bug where the y subplot labels overlap
            for i in range(num_factors):
                xref = "x domain"
                if i == 0:
                    yref = "y domain"
                else:
                    yref = f"y{i} domain"
                annotations.append(dict(
                    text=f"Factor {i + 1}",
                    x=0.5,
                    y=.99,
                    xref=xref,
                    yref=yref,
                    xanchor="center",
                    yanchor="bottom",
                    showarrow=False,
                    font=dict(size=13)
                ))

            plot.update_layout(
                title=dict(font=dict(size=15), x=0.5, xanchor="center"),
                width=None,
                height=None,
                autosize=True,
                margin=dict(l=60, r=50, t=50, b=5),
                legend=dict(
                    x=1.0, y=1.04, xanchor='right', yanchor='top',
                    orientation='h',
                    valign='top',
                    font=dict(size=10),
                    bgcolor='rgba(0,0,0,0)'
                ),
                annotations=annotations
            )
            if hasattr(plot, 'to_html'):
                html = plot.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True, 'displayModeBar': 'hover'})
            else:
                html = str(plot)
            webview.setHtml(html)
        layout.addWidget(webview)
        dialog.show()  # Use show() instead of exec() to make the dialog non-modal/non-blocking

    def update_plots(self):
        """
        Update the plots based on the selected feature index.
        """
        logger.info("[FactorAnalysisSubTab] Updating plots in Factor Analysis SubTab.")
        if self.controller.main_controller.selected_modelanalysis_manager is None:
            logger.warning("No model analysis manager available.")
            return
        self.refresh_profile_plot()
        self.refresh_fingerprints_plot()
        self.refresh_g_plot()

    def refresh_profile_plot(self):
        toggle_loader(self.plot_stacks[0], self.profile_movie, True)
        toggle_loader(self.plot_stacks[1], self.contrib_movie, True)
        self.update_profile_plot()
        self.update_contrib_plot()

    def refresh_fingerprints_plot(self):
        toggle_loader(self.plot_stacks[2], self.fingerprints_movie, True)
        self.update_fingerprints_plot()

    def refresh_g_plot(self):
        toggle_loader(self.plot_stacks[3], self.g_movie, True)
        self.update_g_plot()

    def refresh_on_activate(self):
        """
        Call this when the subtab is activated to ensure the table and plots are updated.
        If analysis results are available, update directly. Otherwise, trigger analysis.
        """
        logger.info("[FactorAnalysisSubTab] Refreshing Factor Analysis SubTab on activation.")
        self.update_plots()

    def _on_show_3d(self):
        manager = self.controller.main_controller.selected_modelanalysis_manager
        if manager:
            manager.factors3dReady.connect(self._show_3d_modal)
            manager.run_factors_3d()

    def _show_3d_modal(self, plot):
        manager = self.controller.main_controller.selected_modelanalysis_manager
        try:
            manager.factors3dReady.disconnect(self._show_3d_modal)
        except Exception:
            pass
        dialog = QDialog(self)
        dialog.setWindowTitle('3D Factor Plot')
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinMaxButtonsHint)
        # width = 900
        # height = QApplication.primaryScreen().availableGeometry().height()
        dialog.resize(800, 800)
        layout = QVBoxLayout(dialog)
        from PySide6.QtWebEngineWidgets import QWebEngineView
        webview = QWebEngineView(dialog)
        if plot is not None:
            plot.update_layout(width=None, height=None, autosize=True,
                               # margin=dict(l=5, r=5, t=30, b=5)
                               )
            if hasattr(plot, 'to_html'):
                html = plot.to_html(full_html=False, include_plotlyjs='cdn', config={'responsive': True, 'displayModeBar': 'hover'})
            else:
                html = str(plot)
            webview.setHtml(html)
        layout.addWidget(webview)
        dialog.show()  # Use show() instead of exec() to make the dialog non-modal/non-blocking

    def _on_g_factor_changed(self):
        """
        Handle changes in the G Plot X or Y factor dropdowns and update the G plot accordingly.
        """
        x_factor = self.g_x_dropdown.currentData()
        y_factor = self.g_y_dropdown.currentData()
        logger.info(f"[FactorAnalysisSubTab] G Plot factors changed: x={x_factor}, y={y_factor}")
        if x_factor is not None and y_factor is not None:
            toggle_loader(self.plot_stacks[3], self.g_movie, True)
            self.controller.main_controller.selected_modelanalysis_manager.run_g_space(x_factor, y_factor)
