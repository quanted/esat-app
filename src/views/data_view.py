import os
import logging
import pandas as pd
import plotly.graph_objects as go
from time import monotonic

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QGroupBox, QTabWidget, QTableWidget, QVBoxLayout, QComboBox, QLabel, QSizePolicy,
    QTableWidgetItem, QStackedLayout, QHeaderView, QAbstractItemView, QPushButton, QDialog, QApplication
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtGui import QMovie
from PySide6.QtCore import Qt, QSize, QTimer, QPoint

from src.widgets.dataset_selection_widget import DatasetSelectionWidget

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataView(QWidget):
    def __init__(self, parent=None, controller=None, webviews=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller

        # Use provided webviews from MainController
        if webviews is None or len(webviews) < 6:
            raise ValueError("Expected 6 pre-initialized QWebEngineView instances in webviews")

        self.webviews = webviews
        self._webview_html_cache = {}

        # Initialize plot figure attributes
        self.scatter_fig = None
        self.ts_fig = None

        # Assign webviews
        self.formatted_webviews = {
            'scatter': self.webviews[0],
            'ts': self.webviews[1],
            'compare': self.webviews[2],
            'heatmap': self.webviews[3],
            'histogram': self.webviews[4],
            'ridge': self.webviews[5]
        }

        loader_path = os.path.join("src", "resources", "icons", "loading_spinner.gif")
        self.scatter_loading, self.scatter_movie = self._setup_loader(loader_path)
        self.ts_loading, self.ts_movie = self._setup_loader(loader_path)
        self.compare_loading, self.compare_movie = self._setup_loader(loader_path)
        self.heatmap_loading, self.heatmap_movie = self._setup_loader(loader_path)
        self.histogram_loading, self.histogram_movie = self._setup_loader(loader_path)
        self.ridge_loading, self.ridge_movie = self._setup_loader(loader_path)

        self.analyze_loadings = [self.scatter_loading, self.ts_loading]
        self.analyze_movies = [self.scatter_movie, self.ts_movie]
        self.analyze_plot_stacks = [None, None]

        self.compare_loadings = [self.compare_loading, self.heatmap_loading, self.histogram_loading, self.ridge_loading]
        self.compare_movies = [self.compare_movie, self.heatmap_movie, self.histogram_movie, self.ridge_movie]
        self.compare_plot_stacks = [None, None, None, None]
        self.compare_containers = [None, None, None, None]

        self.selected_feature = None
        self.dataset_metrics = []
        self.plotted_row = None
        self.category_colors = {
            'strong': 'green',
            'weak': 'orange',
            'bad': 'red'
        }

        self._setup_ui()
        self._connect_signals()

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

    def _connect_signals(self):
        if self.controller and hasattr(self.controller.main_controller, "dataset_manager"):
            dataset_manager = self.controller.main_controller.dataset_manager
            dataset_manager.datasets_changed.connect(self._check_dataset_removed)
            dataset_manager.dataset_loaded.connect(self.on_dataset_loaded)

            dataset_manager.uncertainty_plot_ready.connect(self.update_scatter_plot)
            dataset_manager.ts_plot_ready.connect(self.update_timeseries_plot)

            # dataset_manager.plot_feature_data_ready.connect(self._on_compare_plot_ready)
            # dataset_manager.plot_2d_histogram_ready.connect(self._on_compare_plot_ready)

    def toggle_loader(self, stack: QStackedLayout, movie: QMovie, show: bool):
        """Show or hide the loader in a stacked layout."""
        if show:
            movie.start()
            stack.setCurrentIndex(1)
        else:
            movie.stop()
            stack.setCurrentIndex(0)

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Left: Tab section ---
        self.tabs = QTabWidget()
        self.tabs.setContentsMargins(0, 0, 0, 0)
        self.tabs.setTabPosition(QTabWidget.South)
        self.tabs.addTab(self._create_analyze_tab(), "Feature Analysis")
        self.tabs.addTab(self._create_compare_tab(), "Feature Compare")
        self.tabs.addTab(self._create_impute_tab(), "Impute")
        self.tabs.addTab(self._create_outliers_tab(), "Outliers")
        self.tabs.addTab(self._create_simulate_tab(), "Simulate")
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

        main_layout.addWidget(right_panel, stretch=0, alignment=Qt.AlignTop)

        # Connect signal
        self.dataset_selection_widget.dataset_selected.connect(self.load_dataset)

    def _create_analyze_tab(self):
        tab_widget = QWidget()
        tab_layout = QHBoxLayout(tab_widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        self._setup_stats_table()
        # Stats table (left)
        stats_box = QGroupBox("Data Statistics")
        stats_layout = QVBoxLayout(stats_box)
        stats_layout.addWidget(self.stats_table)
        stats_layout.setContentsMargins(10, 10, 10, 10)
        tab_layout.addWidget(stats_box, stretch=1)

        plot_box = QGroupBox("Data Plots")
        plot_layout = QVBoxLayout(plot_box)

        # Scatter plot container
        scatter_box, scatter_container, scatter_stack = self.make_plot_container(
            self.formatted_webviews['scatter'], self.scatter_loading
        )
        plot_layout.addWidget(scatter_container)

        # Timeseries plot container
        ts_box, ts_container, ts_stack = self.make_plot_container(
            self.formatted_webviews['ts'], self.ts_loading
        )
        plot_layout.addWidget(ts_container)

        tab_layout.addWidget(plot_box, stretch=2)

        self.analyze_plot_stacks = [scatter_stack, ts_stack]

        return tab_widget

    def _create_compare_tab(self):
        tab_widget = QWidget()
        main_layout = QVBoxLayout(tab_widget)

        self.compare_feature1_dropdown = QComboBox()
        self.compare_feature2_dropdown = QComboBox()
        self.compare_plot_toggle = QComboBox()
        self.compare_plot_toggle.addItems(["Scatter", "2D Histogram"])

        grid = QHBoxLayout()
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        # Create plot containers
        vbox1, compare_container, compare_stack = self.make_plot_container(
            self.formatted_webviews['compare'], self.compare_loading
        )
        vbox2, heatmap_container, heatmap_stack = self.make_plot_container(
            self.formatted_webviews['heatmap'], self.heatmap_loading
        )
        vbox3, histogram_container, histogram_stack = self.make_plot_container(
            self.formatted_webviews['histogram'], self.histogram_loading
        )
        vbox4, ridge_container, ridge_stack = self.make_plot_container(
            self.formatted_webviews['ridge'], self.ridge_loading
        )
        self.compare_plot_stacks = [compare_stack, heatmap_stack, histogram_stack, ridge_stack]
        self.compare_containers = [compare_container, heatmap_container, histogram_container, ridge_container]

        left_col.addWidget(compare_container)
        left_col.addWidget(heatmap_container)
        right_col.addWidget(histogram_container)
        right_col.addWidget(ridge_container)

        left_col.setStretch(0, 1)
        left_col.setStretch(1, 1)
        right_col.setStretch(0, 1)
        right_col.setStretch(1, 1)

        combo_row = QHBoxLayout()
        combo_row.addWidget(QLabel("X Feature:"))
        combo_row.addWidget(self.compare_feature1_dropdown)
        combo_row.addWidget(QLabel("Y Feature:"))
        combo_row.addWidget(self.compare_feature2_dropdown)
        combo_row.addWidget(QLabel("Plot Type:"))
        combo_row.addWidget(self.compare_plot_toggle)
        combo_row.addStretch()
        main_layout.addLayout(combo_row)

        grid.addLayout(left_col)
        grid.addLayout(right_col)
        main_layout.addLayout(grid)

        # Populate feature dropdowns when dataset is loaded
        self.compare_feature1_dropdown.clear()
        self.compare_feature2_dropdown.clear()
        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        if dataset_manager and dataset_manager.loaded_datasets:
            dataset = next(iter(dataset_manager.loaded_datasets.values()))
            if hasattr(dataset, "input_data"):
                features = list(dataset.input_data.columns)
                self.compare_feature1_dropdown.addItems(features)
                self.compare_feature2_dropdown.addItems(features)

        # Connect compare_feature1_dropdown, compare_feature2_dropdown, and compare_plot_toggle signals
        self.compare_feature1_dropdown.currentIndexChanged.connect(self._do_update_compare_plot)
        self.compare_feature2_dropdown.currentIndexChanged.connect(self._do_update_compare_plot)
        self.compare_plot_toggle.currentIndexChanged.connect(self._do_update_compare_plot)

        return tab_widget

    def load_compare_plots(self):
        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        dataset_name = next(iter(dataset_manager.loaded_datasets.keys()),
                            None) if dataset_manager and dataset_manager.loaded_datasets else None
        if dataset_manager and dataset_name:

            # Start loaders for all compare plots
            for i in range(len(self.compare_movies)):
                i_movies = self.compare_movies[i]
                i_stack = self.compare_plot_stacks[i]
                self.toggle_loader(i_stack, i_movies, True)

            dataset_manager.plot_feature_data_ready.connect(self._on_compare_plot_ready)
            dataset_manager.plot_2d_histogram_ready.connect(self._on_compare_plot_ready)

            self.compare_feature1_dropdown.setCurrentIndex(0)
            self.compare_feature2_dropdown.setCurrentIndex(1)
            self.compare_plot_toggle.setCurrentIndex(0)

            x_feature = self.compare_feature1_dropdown.currentText()
            y_feature = self.compare_feature2_dropdown.currentText()
            view_type = self.compare_plot_toggle.currentText()
            if view_type == "Scatter":
                dataset_manager.plot_feature_data(dataset_name, x_feature, y_feature)
            else:
                dataset_manager.plot_2d_histogram(dataset_name, x_feature, y_feature)

            # Heatmap, histogram, and ridgeline plots
            dataset_manager.plot_correlation_heatmap_ready.connect(self._on_compare_correlation_heatmap_ready)
            dataset_manager.plot_correlation_heatmap(dataset_name, method="pearson")

            dataset_manager.plot_superimposed_histograms_ready.connect(self._on_compare_superimposed_histograms_ready)
            dataset_manager.plot_superimposed_histograms(dataset_name)

            dataset_manager.plot_ridgeline_ready.connect(self._on_compare_ridgeline_ready)
            dataset_manager.plot_ridgeline(dataset_name)

    def _setup_stacked_layouts(self):
        for i, i_stack in enumerate(self.compare_plot_stacks):
            i_stack.addWidget(self._compare_plot_views[i])
            i_stack.addWidget(self.compare_loadings[i])
            i_stack.setCurrentIndex(0)

    def _setup_stats_table(self):
        self.stats_table = QTableWidget(0, 8)
        self.stats_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stats_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.stats_table.setHorizontalHeaderLabels([
            "Feature", "Category", "S/N", "Min", "25th", "50th", "75th", "Max"
        ])

    def show_expanded_plot(self, view):
        dialog = QDialog(self)
        dialog.setWindowTitle("Expanded Plot")
        dialog.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        dialog.setModal(False)

        # Center the dialog
        screen = QApplication.primaryScreen().geometry()
        width, height = 1200, 800
        x = (screen.width() - width) // 2
        y = (screen.height() - height) // 2
        dialog.setGeometry(x, y, width, height)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Custom title bar as QWidget for full drag area ---
        title_bar_widget = QWidget()
        title_bar_widget.setFixedHeight(28)  # Set a fixed height for the title bar
        title_bar_layout = QHBoxLayout(title_bar_widget)
        title_bar_layout.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel("Expanded Plot")
        title_label.setStyleSheet("font-weight: bold; padding-left: 8px;")
        title_bar_layout.addWidget(title_label)
        title_bar_layout.addStretch()

        minimize_btn = QPushButton("–")
        fullscreen_btn = QPushButton("⛶")
        close_btn = QPushButton("✕")
        for btn in (minimize_btn, fullscreen_btn, close_btn):
            btn.setFixedSize(28, 28)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: none;
                    font-size: 16px;
                }
                QPushButton:hover {
                    background: #eee;
                }
            """)
        title_bar_layout.addWidget(minimize_btn)
        title_bar_layout.addWidget(fullscreen_btn)
        title_bar_layout.addWidget(close_btn)
        main_layout.addWidget(title_bar_widget)

        # --- Expanded plot view ---
        expanded_view = QWebEngineView(dialog)
        main_layout.addWidget(expanded_view)

        # Set HTML only after the original view is loaded
        def set_expanded_html(_ok=True):
            view.page().toHtml(lambda html: expanded_view.setHtml(html))
            try:
                view.loadFinished.disconnect(set_expanded_html)
            except Exception:
                pass

        view.loadFinished.connect(set_expanded_html)
        set_expanded_html()

        # --- Button actions ---
        minimize_btn.clicked.connect(dialog.showMinimized)

        def toggle_fullscreen():
            if dialog.isFullScreen():
                dialog.showNormal()
            else:
                dialog.showFullScreen()

        fullscreen_btn.clicked.connect(toggle_fullscreen)
        close_btn.clicked.connect(dialog.close)

        # --- Drag support for title bar ---
        drag_data = {"dragging": False, "offset": QPoint()}

        def mousePressEvent(event):
            if event.button() == Qt.LeftButton:
                drag_data["dragging"] = True
                drag_data["offset"] = event.globalPosition().toPoint() - dialog.frameGeometry().topLeft()

        def mouseMoveEvent(event):
            if drag_data["dragging"]:
                dialog.move(event.globalPosition().toPoint() - drag_data["offset"])

        def mouseReleaseEvent(event):
            drag_data["dragging"] = False

        title_bar_widget.mousePressEvent = mousePressEvent
        title_bar_widget.mouseMoveEvent = mouseMoveEvent
        title_bar_widget.mouseReleaseEvent = mouseReleaseEvent

        dialog.show()

    def make_plot_container(self, view, loader):
        container = QWidget()
        container.setStyleSheet("background: #fff;")
        container.setMinimumSize(200, 200)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        stack = QStackedLayout()
        stack.addWidget(view)
        stack.addWidget(loader)
        container.setLayout(stack)

        # Expand button overlay
        # button_layout = QHBoxLayout()
        # button_layout.setContentsMargins(0, 0, 0, 0)
        # button_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        #
        # expand_btn = QPushButton("⛶", container)
        # expand_btn.setFixedSize(24, 24)
        # expand_btn.setStyleSheet(
        #     """
        #     background: transparent;
        #     color: black;
        #     border: none;
        #     font-size: 16px;
        #     """
        # )
        # expand_btn.clicked.connect(lambda: self.show_expanded_plot(view))
        # button_layout.addWidget(expand_btn, alignment=Qt.AlignTop | Qt.AlignLeft)
        #
        # overlay_layout = QVBoxLayout(container)
        # overlay_layout.setContentsMargins(0, 0, 0, 0)
        # overlay_layout.addLayout(button_layout)
        # overlay_layout.addStretch()

        # vbox = QVBoxLayout()
        # vbox.setContentsMargins(0, 0, 0, 0)
        # vbox.addWidget(container)
        return None, container, stack

    def _on_compare_plot_ready(self, name, fig, html=None):
        logger.info(f"Compare plot ready: {name}")
        if html is None:
            fig.update_layout(
                title=dict(font=dict(size=12), x=0.5, xanchor="center"),
                font=dict(size=10),
                xaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                yaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                legend=dict(font=dict(size=9)),
                autosize=True,
                width=None,
                height=None,
                margin=dict(l=5, r=5, t=30, b=5)
            )
            plot_html = fig.to_html(
                full_html=False,
                include_plotlyjs='cdn',
                config={'responsive': True, 'displayModeBar': 'hover'}
            )
        else:
            plot_html = html

        def hide_spinner(_ok):
            self.toggle_loader(self.compare_plot_stacks[0], self.compare_movie, False)
            self.compare_plot_stacks[0].setCurrentIndex(0)
            try:
                self.formatted_webviews['compare'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.formatted_webviews['compare'].loadFinished.connect(hide_spinner)
        self.set_webview_html('compare', plot_html)

    def _on_compare_correlation_heatmap_ready(self, name, fig, html=None):
        # Render the heatmap in the lower left plot box
        if html is None:
            fig.update_layout(
                title=dict(font=dict(size=12), x=0.5, xanchor="center"),
                font=dict(size=10),
                xaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                yaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                legend=dict(font=dict(size=9)),
                autosize=True,
                width=None,
                height=None,
                margin=dict(l=5, r=5, t=30, b=5)
            )
            plot_html = fig.to_html(
                full_html=False,
                include_plotlyjs='cdn',
                config={'responsive': True, 'displayModeBar': 'hover'}
            )
        else:
            plot_html = html

        # Connect the heatmap loadFinish signal to toggle the loader
        def hide_spinner(_ok):
            self.toggle_loader(self.compare_plot_stacks[1], self.heatmap_movie, False)
            try:
                self.formatted_webviews['heatmap'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.formatted_webviews['heatmap'].loadFinished.connect(hide_spinner)
        self.set_webview_html('heatmap', plot_html)

    def _on_compare_superimposed_histograms_ready(self, name, fig, html=None):
        # Render the histograms in the upper right plot box
        if html is None:
            fig.update_layout(
                title=dict(font=dict(size=12), x=0.5, xanchor="center"),
                font=dict(size=10),
                xaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                yaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                legend=dict(font=dict(size=9)),
                autosize=True,
                width=None,
                height=None,
                margin=dict(l=5, r=5, t=30, b=5)
            )
            plot_html = fig.to_html(
                full_html=False,
                include_plotlyjs='cdn',
                config={'responsive': True, 'displayModeBar': 'hover'}
            )
        else:
            plot_html = html

        # Connect the histogram loadFinish signal to toggle the loader
        def hide_spinner(_ok):
            self.toggle_loader(self.compare_plot_stacks[2], self.histogram_movie, False)
            try:
                self.formatted_webviews['histogram'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.formatted_webviews['histogram'].loadFinished.connect(hide_spinner)
        self.set_webview_html('histogram', plot_html)

    def _on_compare_ridgeline_ready(self, name, fig, html=None):
        # Render the ridgeline plot in the bottom left plot box
        if html is None:
            fig.update_layout(
                title=dict(font=dict(size=12), x=0.5, xanchor="center"),
                font=dict(size=10),
                xaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                yaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                legend=dict(font=dict(size=9)),
                autosize=True,
                width=None,
                height=None,
                margin=dict(l=5, r=5, t=30, b=5)
            )
            plot_html = fig.to_html(
                full_html=False,
                include_plotlyjs='cdn',
                config={'responsive': True, 'displayModeBar': 'hover'}
            )
        else:
            plot_html = html

        # Connect the ridge loadFinish signal to toggle the loader
        def hide_spinner(_ok):
            self.toggle_loader(self.compare_plot_stacks[3], self.ridge_movie, False)
            try:
                self.formatted_webviews['ridge'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass
        self.formatted_webviews['ridge'].loadFinished.connect(hide_spinner)
        self.set_webview_html('ridge', plot_html)

    def set_webview_html(self, view_name, html):
        """Set HTML and cache it for the given webview index."""
        if view_name in self.formatted_webviews.keys():
            self.formatted_webviews[view_name].setHtml(html)
            self.formatted_webviews[view_name].update()
            self.formatted_webviews[view_name].repaint()
            self._webview_html_cache[view_name] = html

    def update_compare_feature_dropdowns(self):
        self.compare_feature1_dropdown.blockSignals(True)
        self.compare_feature2_dropdown.blockSignals(True)

        self.compare_feature1_dropdown.clear()
        self.compare_feature2_dropdown.clear()

        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        if dataset_manager and dataset_manager.loaded_datasets:
            dataset = next(iter(dataset_manager.loaded_datasets.values()))
            if hasattr(dataset, "input_data"):
                features = list(dataset.input_data.columns)
                self.compare_feature1_dropdown.addItems(features)
                self.compare_feature2_dropdown.addItems(features)
                if self.compare_feature1_dropdown.count() > 0:
                    self.compare_feature1_dropdown.setCurrentIndex(0)
                if self.compare_feature2_dropdown.count() > 1:
                    self.compare_feature2_dropdown.setCurrentIndex(1)
                elif self.compare_feature2_dropdown.count() > 0:
                    self.compare_feature2_dropdown.setCurrentIndex(0)
        self.compare_feature1_dropdown.blockSignals(False)
        self.compare_feature2_dropdown.blockSignals(False)

    def _do_update_compare_plot(self):
        self.toggle_loader(self.compare_plot_stacks[0], self.compare_movie, True)
        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        if not dataset_manager or not dataset_manager.loaded_datasets:
            return
        dataset_name = next(iter(dataset_manager.loaded_datasets.keys()))
        x_feature = self.compare_feature1_dropdown.currentText()
        y_feature = self.compare_feature2_dropdown.currentText()
        view_type = self.compare_plot_toggle.currentText()
        logger.info(f"Updating compare plot: {x_feature} vs {y_feature} ({view_type})")
        if view_type == "Scatter":
            dataset_manager.plot_feature_data(dataset_name, x_feature, y_feature)
        else:
            dataset_manager.plot_2d_histogram(dataset_name, x_feature, y_feature)

    def _create_outliers_tab(self):
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        label = QLabel("To be added")
        label.setAlignment(Qt.AlignCenter)
        tab_layout.addWidget(label)
        return tab_widget

    def _create_impute_tab(self):
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        label = QLabel("To be added")
        label.setAlignment(Qt.AlignCenter)
        tab_layout.addWidget(label)
        return tab_widget

    def _create_simulate_tab(self):
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        label = QLabel("To be added")
        label.setAlignment(Qt.AlignCenter)
        tab_layout.addWidget(label)
        return tab_widget

    def load_dataset(self, name):
        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        if dataset_manager is not None:
            try:
                dataset_manager.dataset_loaded.disconnect(self.on_dataset_loaded)
            except TypeError:
                pass
            dataset_manager.dataset_loaded.connect(self.on_dataset_loaded)
            dataset_manager.load(name)

    def on_dataset_loaded(self, dataset_name):
        # Only update if the loaded dataset is currently selected
        if dataset_name == self.dataset_selection_widget.dataset_dropdown.currentText():
            self.create_statistics_table(dataset_name)
            self.update_compare_feature_dropdowns()
            self.load_compare_plots()

    def create_statistics_table(self, dataset_name):
        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        if dataset_manager is not None:
            dataset = dataset_manager.loaded_datasets.get(dataset_name)
            if dataset is not None and hasattr(dataset, "metrics") and isinstance(dataset.metrics, pd.DataFrame):
                df = dataset.metrics
            else:
                df = pd.DataFrame()
        else:
            df = pd.DataFrame()

        self.stats_table.setRowCount(df.shape[0])
        self.stats_table.setColumnCount(df.shape[1] + 1)
        headers = ['Features'] + [str(col) for col in df.columns]
        self.stats_table.setHorizontalHeaderLabels(headers)

        for row in range(df.shape[0]):
            index_item = QTableWidgetItem(str(df.index[row]))
            self.stats_table.setItem(row, 0, index_item)
            for col in range(df.shape[1]):
                if headers[col + 1].lower() == "category":
                    combo = QComboBox()
                    for opt in ['strong', 'weak', 'bad']:
                        combo.addItem(opt)
                    value = df.iat[row, col]
                    if value in self.category_colors:
                        combo.setCurrentText(value)
                    for i, opt in enumerate(['strong', 'weak', 'bad']):
                        combo.setItemData(i, self.category_colors[opt], role=Qt.ForegroundRole)
                    # Set background color for current text
                    combo.setStyleSheet(f"background-color: {self.category_colors[combo.currentText()]};")

                    # Update background color on change
                    def on_change(idx, combo=combo):
                        color = self.category_colors[combo.currentText()]
                        combo.setStyleSheet(f"background-color: {color};")
                        self.controller.main_controller.dataset_manager.set_feature_category(
                            dataset_name, str(df.index[idx]), combo.currentText()
                        )
                    combo.currentIndexChanged.connect(on_change)

                    def on_combo_activated(idx, row=row):
                        self.on_stats_table_clicked(row, 1)  # 1 is the Category column index
                        self.stats_table.selectRow(row)
                    combo.activated.connect(on_combo_activated)

                    self.stats_table.setCellWidget(row, col + 1, combo)
                else:
                    value = df.iat[row, col]
                    if pd.isna(value):
                        value = "N/A"
                    elif isinstance(value, (int, float)):
                        value = f"{value:.4f}"
                    self.stats_table.setItem(row, col + 1, QTableWidgetItem(str(value)))

        self.stats_table.resizeColumnsToContents()
        header = self.stats_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(False)
        header.setSectionsMovable(False)
        header.setSectionsClickable(False)
        self.stats_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.stats_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.stats_table.setEditTriggers(QTableWidget.NoEditTriggers)

        def handle_stats_table_click(row, column):
            self.stats_table.selectRow(row)
            self.on_stats_table_clicked(row, column)

        self.stats_table.cellClicked.connect(handle_stats_table_click)

        # Trigger plot for the first feature if available
        if df.shape[0] > 0:
            self.stats_table.selectRow(0)
            # Treat initial load like a click on the first row
            self.on_stats_table_clicked(0, 0)

    def on_stats_table_clicked(self, row, column):
        logger.info(f"Stats table clicked at row {row}, column {column}")
        if row == self.plotted_row:
            return
        self.plotted_row = row

        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        feature_item = self.stats_table.item(row, 0)
        if not feature_item or not dataset_manager:
            return

        feature_name = feature_item.text()
        dataset_name = self.dataset_selection_widget.dataset_dropdown.currentText()
        dataset = dataset_manager.loaded_datasets.get(dataset_name)
        if not dataset:
            return
        self.toggle_loader(self.analyze_plot_stacks[0], self.scatter_movie, True)
        self.toggle_loader(self.analyze_plot_stacks[1], self.ts_movie, True)

        # Get category color
        category = None
        category_col = None
        for col in range(self.stats_table.columnCount()):
            if self.stats_table.horizontalHeaderItem(col).text().lower() == "category":
                category_col = col
                break
        if category_col is not None:
            combo = self.stats_table.cellWidget(row, category_col)
            if combo:
                category = combo.currentText()
        color = self.category_colors.get(category, "blue")

        # Prepare scatter plot
        if self.scatter_fig is not None:
            fig = self.scatter_fig
            new_x = dataset.input_data[feature_name].values
            new_y = dataset.uncertainty_data[feature_name].values
            for trace in fig.data:
                if hasattr(trace, "marker"):
                    trace.marker.color = color
                    trace.marker.line.color = color
                    trace.marker.symbol = "circle-open"
                    trace.marker.size = 4
                    trace.marker.line.width = 1
            fig.data[0].x = new_x
            fig.data[0].y = new_y
            self.update_scatter_plot(feature_name, fig)
        else:
            dataset_manager.plot_data_uncertainty(dataset_name, feature_name)

        # Prepare timeseries plot
        if self.ts_fig is not None:
            fig = self.ts_fig
            new_y = dataset.input_data[feature_name].values
            for trace in fig.data:
                if hasattr(trace, "marker"):
                    trace.marker.color = color
                    trace.marker.line.color = color
                    trace.marker.symbol = "circle-open"
                    trace.marker.size = 4
                    trace.marker.line.width = 1
                if hasattr(trace, "line"):
                    trace.line.color = color
            fig.data[0].y = new_y
            self.update_timeseries_plot(feature_name, fig)
        else:
            dataset_manager.plot_feature_timeseries(dataset_name, feature_name)

    def update_scatter_plot(self, feature_name, fig, html=None):
        logger.info(f"Updating scatter plot for feature: {feature_name}")
        if html is None:
            color = self.category_colors.get(self.stats_table.cellWidget(self.plotted_row, 1).currentText(), "blue")
            for trace in fig.data:
                if hasattr(trace, "marker"):
                    trace.marker.symbol = "circle-open"
                    trace.marker.size = 4
                    trace.marker.line.width = 1
                    trace.marker.color = color
                    trace.marker.line.color = color
            fig.update_layout(
                title_text=f"Data/Uncertainty - {feature_name}",
                title=dict(font=dict(size=12), x=0.5, xanchor="center"),
                font=dict(size=10),
                xaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                yaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                legend=dict(font=dict(size=9)),
                autosize=True,
                width=None,
                height=None,
                margin=dict(l=5, r=5, t=30, b=5)
            )
            fig.update_xaxes(title_text="Data")
            plot_html = fig.to_html(
                full_html=False,
                include_plotlyjs='cdn',
                config={'responsive': True, 'displayModeBar': 'hover'}
            )
            plot_html = f"<div style='width:100%;height:100%;padding:0;margin:0;overflow:hidden'>{plot_html}</div>"
        else:
            plot_html = html

        def hide_spinner(_ok):
            self.toggle_loader(self.analyze_plot_stacks[0], self.scatter_movie, False)
            try:
                self.formatted_webviews['scatter'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.formatted_webviews['scatter'].loadFinished.connect(hide_spinner)
        self.set_webview_html('scatter', plot_html)
        self.scatter_fig = fig

    def update_timeseries_plot(self, feature_name, fig, html=None):
        """Slot to handle the ts_plot_ready signal and update the timeseries plot."""
        logger.info(f"Updating timeseries plot for feature: {feature_name}")
        if html is None:
            color = self.category_colors.get(self.stats_table.cellWidget(self.plotted_row, 1).currentText(), "blue")
            for trace in fig.data:
                if hasattr(trace, "marker"):
                    trace.marker.symbol = "circle-open"
                    trace.marker.size = 4
                    trace.marker.line.width = 1
                    trace.marker.color = color
                    trace.marker.line.color = color
            fig.update_layout(
                title_text="Timeseries",
                title=dict(font=dict(size=12), x=0.5, xanchor="center"),
                font=dict(size=10),
                xaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                yaxis=dict(title_font=dict(size=10), tickfont=dict(size=9)),
                showlegend=False,
                autosize=True,
                width=None,
                height=None,
                margin=dict(l=5, r=5, t=30, b=5)
            )
            fig.update_yaxes(title_text="Value")
            plot_html = fig.to_html(
                full_html=False,
                include_plotlyjs='cdn',
                config={'responsive': True, 'displayModeBar': 'hover'}
            )
            plot_html = f"<div style='width:100%;height:100%;padding:0;margin:0;overflow:hidden'>{plot_html}</div>"
        else:
            plot_html = html

        def hide_spinner(_ok):
            self.toggle_loader(self.analyze_plot_stacks[1], self.ts_movie, False)

            try:
                self.formatted_webviews['ts'].loadFinished.disconnect(hide_spinner)
            except Exception:
                pass

        self.formatted_webviews['ts'].loadFinished.connect(hide_spinner)
        self.set_webview_html('ts', plot_html)
        self.ts_fig = fig

    def on_dataset_removed(self):
        # Clear stats table and plots only; widget handles dropdown/details
        self.stats_table.setRowCount(0)
        self.compare_feature1_dropdown.clear()
        self.compare_feature2_dropdown.clear()
        for view in [
            self.scatter_view, self.ts_view,
            self.compare_upper_left_view, self.compare_upper_right_view,
            self.compare_lower_left_view, self.compare_lower_right_view
        ]:
            view.setHtml("<div></div>")
        self.plotted_row = None
        self.scatter_fig = None
        self.ts_fig = None

    def _check_dataset_removed(self):
        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        names = dataset_manager.get_names() if dataset_manager else []
        if not names:
            self.on_dataset_removed()
        else:
            # If current dataset is missing, select the next available in the widget
            current = self.dataset_selection_widget.dataset_dropdown.currentText()
            if current not in names:
                self.dataset_selection_widget.dataset_dropdown.setCurrentIndex(0)
                self.load_dataset(self.dataset_selection_widget.dataset_dropdown.currentText())

    def reattach_webviews(self):
        # For compare plot stacks
        for i, (view_name, stack) in enumerate(zip(
                ['compare', 'heatmap', 'histogram', 'ridge'],
                self.compare_plot_stacks
        )):
            webview = self.formatted_webviews[view_name]
            webview.setParent(None)
            webview.setMinimumSize(200, 200)
            webview.setMaximumSize(16777215, 16777215)
            webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

            # Remove all widgets from stack
            while stack.count():
                stack.removeWidget(stack.widget(0))
            stack.addWidget(webview)
            stack.addWidget(self.compare_loadings[i])
            stack.setCurrentIndex(1)

            # Resize parent and update geometry
            parent = stack.parentWidget()
            if parent:
                parent.resize(400, parent.height())
                parent.adjustSize()
                parent.updateGeometry()
                parent.update()
            webview.adjustSize()
            webview.updateGeometry()

            # Restore HTML
            html = self._webview_html_cache.get(view_name)
            if view_name == "compare":
                self._on_compare_plot_ready(None, None, html=html)
            elif view_name == "heatmap":
                self._on_compare_correlation_heatmap_ready(None, None, html=html)
            elif view_name == "histogram":
                self._on_compare_superimposed_histograms_ready(None, None, html=html)
            elif view_name == "ridge":
                self._on_compare_ridgeline_ready(None, None, html=html)

            container = stack.parentWidget()
            if container and container.layout():
                container.layout().invalidate()
                container.updateGeometry()
                container.update()
            QApplication.processEvents()

        # For analyze plot stacks (scatter, ts)
        for i, (view_name, stack) in enumerate(zip(
                ['scatter', 'ts'],
                self.analyze_plot_stacks
        )):
            webview = self.formatted_webviews[view_name]
            webview.setParent(None)
            webview.setMinimumSize(200, 200)
            webview.setMaximumSize(16777215, 16777215)
            webview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

            while stack.count():
                stack.removeWidget(stack.widget(0))
            stack.addWidget(webview)
            stack.addWidget(self.analyze_loadings[i])
            stack.setCurrentIndex(1)

            parent = stack.parentWidget()
            if parent:
                parent.resize(400, parent.height())
                parent.adjustSize()
                parent.updateGeometry()
                parent.update()
            webview.adjustSize()
            webview.updateGeometry()
            QApplication.processEvents()

            html = self._webview_html_cache.get(view_name)
            if view_name == "scatter":
                self.update_scatter_plot(None, None, html=html)
            elif view_name == "ts":
                self.update_timeseries_plot(None, None, html=html)

        compare_tab = self.tabs.widget(1)  # Assuming compare tab is at index 1
        main_layout = compare_tab.layout()
        if main_layout and main_layout.count() > 1:
            grid = main_layout.itemAt(1).layout()  # The grid QHBoxLayout
            if grid and grid.count() == 2:
                grid.setStretch(0, 1)  # Left column
                grid.setStretch(1, 1)  # Right column
        QApplication.processEvents()
