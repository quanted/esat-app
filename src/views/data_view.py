import os
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


class DataView(QWidget):
    def __init__(self, parent=None, controller=None, webviews=None):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller

        # Use provided webviews from MainController
        if webviews is None or len(webviews) < 6:
            raise ValueError("Expected 6 pre-initialized QWebEngineView instances in webviews")
        self.webviews = webviews

        # Initialize plot figure attributes
        self.scatter_fig = None
        self.ts_fig = None

        self.scatter_view = self.webviews[0]
        self.ts_view = self.webviews[1]
        self.compare_upper_left_view = self.webviews[2]
        self.compare_upper_right_view = self.webviews[3]
        self.compare_lower_left_view = self.webviews[4]
        self.compare_lower_right_view = self.webviews[5]

        self._compare1_spinner_start = 0
        self._compare1_spinner_min_time = 0.2  # seconds
        self.compare1_plot_timer = QTimer(self)
        self.compare1_plot_timer.setSingleShot(True)
        self.compare1_plot_timer.setInterval(150)  # 150 ms debounce
        self.compare1_plot_timer.timeout.connect(self._do_update_compare1_plot)

        self.selected_feature = None
        self.dataset_metrics = []
        self.plotted_row = None
        self.category_colors = {
            'strong': 'green',
            'weak': 'orange',
            'bad': 'red'
        }

        self._setup_stats_table()
        self._setup_loading_overlays()
        self._setup_stacked_layouts()
        self._setup_ui()

        self._connect_signals()

    def _setup_loading_overlays(self):
        loader_path = os.path.join("src", "resources", "icons", "loading_spinner.gif")
        loader_size = 64

        self.scatter_loading = QLabel()
        self.scatter_loading.setFixedSize(loader_size, loader_size)
        self.scatter_loading.setStyleSheet("background: #fff; border: none;")
        self.scatter_loading.setAlignment(Qt.AlignCenter)
        self.scatter_movie = QMovie(loader_path)
        self.scatter_movie.setScaledSize(QSize(loader_size, loader_size))
        self.scatter_loading.setMovie(self.scatter_movie)

        self.ts_loading = QLabel()
        self.ts_loading.setFixedSize(loader_size, loader_size)
        self.ts_loading.setStyleSheet("background: #fff; border: none;")
        self.ts_loading.setAlignment(Qt.AlignCenter)
        self.ts_movie = QMovie(loader_path)
        self.ts_movie.setScaledSize(QSize(loader_size, loader_size))
        self.ts_loading.setMovie(self.ts_movie)

        # Scatter loader container
        self.scatter_loader_container = QWidget()
        self.scatter_loader_container.setStyleSheet("background: #fff;")
        self.scatter_loader_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scatter_loader_layout = QVBoxLayout(self.scatter_loader_container)
        scatter_loader_layout.addStretch()
        scatter_loader_layout.addWidget(self.scatter_loading, alignment=Qt.AlignCenter)
        scatter_loader_layout.addStretch()
        scatter_loader_layout.setContentsMargins(0, 0, 0, 0)

        # Timeseries loader container
        self.ts_loader_container = QWidget()
        self.ts_loader_container.setStyleSheet("background: #fff;")
        self.ts_loader_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        ts_loader_layout = QVBoxLayout(self.ts_loader_container)
        ts_loader_layout.addStretch()
        ts_loader_layout.addWidget(self.ts_loading, alignment=Qt.AlignCenter)
        ts_loader_layout.addStretch()
        ts_loader_layout.setContentsMargins(0, 0, 0, 0)

    def _setup_stacked_layouts(self):
        self.scatter_stack = QStackedLayout()
        self.scatter_stack.addWidget(self.scatter_view)
        self.scatter_stack.addWidget(self._clone_loader(self.scatter_loader_container))
        self.scatter_stack.setCurrentIndex(0)

        self.ts_stack = QStackedLayout()
        self.ts_stack.addWidget(self.ts_view)
        self.ts_stack.addWidget(self._clone_loader(self.ts_loader_container))
        self.ts_stack.setCurrentIndex(0)

    def _setup_stats_table(self):
        self.stats_table = QTableWidget(0, 8)
        self.stats_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stats_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.stats_table.setHorizontalHeaderLabels([
            "Feature", "Category", "S/N", "Min", "25th", "50th", "75th", "Max"
        ])

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

    def _connect_signals(self):
        if self.controller and hasattr(self.controller.main_controller, "dataset_manager"):
            dataset_manager = self.controller.main_controller.dataset_manager
            dataset_manager.datasets_changed.connect(self._check_dataset_removed)
            dataset_manager.dataset_loaded.connect(self.on_dataset_loaded)

            dataset_manager.uncertainty_plot_ready.connect(self.update_scatter_plot)
            dataset_manager.ts_plot_ready.connect(self.update_timeseries_plot)

            dataset_manager.plot_feature_data_ready.connect(self._on_compare1_plot_ready)
            dataset_manager.plot_2d_histogram_ready.connect(self._on_compare1_plot_ready)

    def _clone_loader(self, loader_widget):
        # Helper to clone the loading spinner container for each plot
        clone = QWidget()
        clone.setStyleSheet("background: #fff;")
        layout = QVBoxLayout(clone)
        layout.setContentsMargins(0, 0, 0, 0)
        spinner = QLabel()
        spinner.setFixedSize(64, 64)
        spinner.setAlignment(Qt.AlignCenter)
        movie = QMovie(os.path.join("src", "resources", "icons", "loading_spinner.gif"))
        movie.setScaledSize(QSize(64, 64))
        spinner.setMovie(movie)
        movie.start()
        layout.addStretch()
        layout.addWidget(spinner, alignment=Qt.AlignCenter)
        layout.addStretch()
        return clone

    def _create_analyze_tab(self):
        tab_widget = QWidget()
        tab_layout = QHBoxLayout(tab_widget)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        # Stats table (left)
        stats_box = QGroupBox("Data Statistics")
        stats_layout = QVBoxLayout(stats_box)
        stats_layout.addWidget(self.stats_table)
        stats_layout.setContentsMargins(10, 10, 10, 10)
        tab_layout.addWidget(stats_box, stretch=1)

        # Plot (right)
        plot_box = QGroupBox("Data Plots")
        plot_layout = QVBoxLayout(plot_box)

        # Scatter plot container
        scatter_container = QWidget()
        scatter_container.setLayout(self.scatter_stack)
        plot_layout.addWidget(scatter_container)

        # Timeseries plot container
        ts_container = QWidget()
        ts_container.setLayout(self.ts_stack)
        plot_layout.addWidget(ts_container)

        tab_layout.addWidget(plot_box, stretch=2)

        return tab_widget

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

        # Helper to create plot containers with loader
        def make_plot_container(view, loader):
            container = QWidget()
            container.setStyleSheet("background: #fff;")
            container.setMinimumSize(200, 200)

            stack = QStackedLayout()
            stack.addWidget(view)
            stack.addWidget(loader)
            container.setLayout(stack)

            # Create a layout to hold the expand button in the top-left corner
            button_layout = QHBoxLayout()
            button_layout.setContentsMargins(0, 0, 0, 0)
            button_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

            expand_btn = QPushButton("⛶", container)
            expand_btn.setFixedSize(24, 24)
            expand_btn.setStyleSheet(
                """
                background: transparent;
                color: black;
                border: none;
                font-size: 16px;
                """
            )
            expand_btn.clicked.connect(lambda: self.show_expanded_plot(view))
            button_layout.addWidget(expand_btn, alignment=Qt.AlignTop | Qt.AlignLeft)

            # Overlay the button layout on top of the container using a QVBoxLayout
            overlay_layout = QVBoxLayout(container)
            overlay_layout.setContentsMargins(0, 0, 0, 0)
            overlay_layout.addLayout(button_layout)
            overlay_layout.addStretch()

            vbox = QVBoxLayout()
            vbox.setContentsMargins(0, 0, 0, 0)
            vbox.addWidget(container)
            return vbox, container, stack

        # Create plot containers
        vbox1, compare1_container, compare1_stack = make_plot_container(
            self.compare_upper_left_view, self._clone_loader(self.scatter_loader_container)
        )
        self.compare1_stack = compare1_stack
        vbox2, compare2_container, _ = make_plot_container(
            self.compare_upper_right_view, self._clone_loader(self.scatter_loader_container)
        )
        vbox3, compare3_container, _ = make_plot_container(
            self.compare_lower_left_view, self._clone_loader(self.scatter_loader_container)
        )
        vbox4, compare4_container, _ = make_plot_container(
            self.compare_lower_right_view, self._clone_loader(self.scatter_loader_container)
        )
        #TODO: Two known issues: The upper left plot is initialized later and is not showing the expanded button. The Ridgeline plot (bottom right) is not rendering on the expanded view.

        # Store for later use
        self._compare_plot_views = [
            self.compare_upper_left_view,
            self.compare_upper_right_view,
            self.compare_lower_left_view,
            self.compare_lower_right_view,
        ]
        self._compare_plot_containers = [
            compare1_container, compare2_container, compare3_container, compare4_container
        ]
        self._compare_plot_vboxes = [vbox1, vbox2, vbox3, vbox4]

        left_col.addWidget(compare1_container)
        left_col.addWidget(compare3_container)
        right_col.addWidget(compare2_container)
        right_col.addWidget(compare4_container)

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

        self.compare_feature1_dropdown.currentIndexChanged.connect(self.compare1_plot_timer.start)
        self.compare_feature2_dropdown.currentIndexChanged.connect(self.compare1_plot_timer.start)
        self.compare_plot_toggle.currentIndexChanged.connect(self.compare1_plot_timer.start)

        self._init_compare1_plot()

        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        dataset_name = next(iter(dataset_manager.loaded_datasets.keys()),
                            None) if dataset_manager and dataset_manager.loaded_datasets else None
        if dataset_manager and dataset_name:
            dataset_manager.plot_correlation_heatmap(dataset_name, method="pearson")
            dataset_manager.plot_correlation_heatmap_ready.connect(self._on_compare_correlation_heatmap_ready)
            dataset_manager.plot_superimposed_histograms(dataset_name)
            dataset_manager.plot_superimposed_histograms_ready.connect(self._on_compare_superimposed_histograms_ready)
            dataset_manager.plot_ridgeline(dataset_name)
            dataset_manager.plot_ridgeline_ready.connect(self._on_compare_ridgeline_ready)

        return tab_widget

    def _on_compare_correlation_heatmap_ready(self, name, fig):
        # Render the heatmap in the lower left plot box
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
        self.compare_lower_left_view.setHtml(plot_html)

    def _on_compare_superimposed_histograms_ready(self, name, fig):
        # Render the histograms in the upper right plot box
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
        self.compare_upper_right_view.setHtml(plot_html)

    def _on_compare_ridgeline_ready(self, name, fig):
        # Render the ridgeline plot in the bottom left plot box
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
        self.compare_lower_right_view.setHtml(plot_html)

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
        self.compare1_plot_timer.start()

    def _init_compare1_plot(self):
        # Get the first loaded dataset and its features
        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        if not dataset_manager or not dataset_manager.loaded_datasets:
            return
        dataset_name = next(iter(dataset_manager.loaded_datasets.keys()))
        dataset = dataset_manager.loaded_datasets[dataset_name]
        features = list(dataset.input_data.columns)
        if len(features) < 2:
            return

        # Set dropdown defaults
        self.compare_feature1_dropdown.setCurrentIndex(0)
        self.compare_feature2_dropdown.setCurrentIndex(1)
        self.compare_plot_toggle.setCurrentIndex(0)  # Default to Scatter
        print(f"Initializing compare1 plot with dataset: {dataset_name}, features: {features}")

        # Connect signals for plot ready
        dataset_manager.plot_feature_data_ready.connect(self._on_compare1_plot_ready)
        dataset_manager.plot_2d_histogram_ready.connect(self._on_compare1_plot_ready)

        # Initial plot
        self.compare1_plot_timer.start()

    def _do_update_compare1_plot(self):
        self._compare1_spinner_start = monotonic()
        self.compare1_stack.setCurrentIndex(1)
        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        if not dataset_manager or not dataset_manager.loaded_datasets:
            return
        dataset_name = next(iter(dataset_manager.loaded_datasets.keys()))
        x_feature = self.compare_feature1_dropdown.currentText()
        y_feature = self.compare_feature2_dropdown.currentText()
        view_type = self.compare_plot_toggle.currentText()
        if view_type == "Scatter":
            dataset_manager.plot_feature_data(dataset_name, x_feature, y_feature)
        else:
            dataset_manager.plot_2d_histogram(dataset_name, x_feature, y_feature)

    def _on_compare1_plot_ready(self, name, fig):
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
        self.compare_upper_left_view.setHtml(plot_html)

        def hide_spinner(_ok):
            elapsed = monotonic() - self._compare1_spinner_start
            min_time = self._compare1_spinner_min_time
            if elapsed < min_time:
                QTimer.singleShot(int((min_time - elapsed) * 1000), lambda: self.compare1_stack.setCurrentIndex(0))
            else:
                self.compare1_stack.setCurrentIndex(0)
            # Disconnect to avoid multiple triggers
            self.compare_upper_left_view.loadFinished.disconnect(hide_spinner)

        self.compare_upper_left_view.loadFinished.connect(hide_spinner)

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

    def show_scatter_loading(self, show=True):
        if show:
            self.scatter_movie.start()
            self.scatter_stack.setCurrentIndex(1)
        else:
            self.scatter_movie.stop()
            self.scatter_stack.setCurrentIndex(0)

    def show_ts_loading(self, show=True):
        if show:
            self.ts_movie.start()
            self.ts_stack.setCurrentIndex(1)
        else:
            self.ts_movie.stop()
            self.ts_stack.setCurrentIndex(0)

    def load_dataset(self, name):
        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        if dataset_manager is not None:
            dataset_manager.load(name)
            # dataset = dataset_manager.loaded_datasets.get(name)

    def on_dataset_loaded(self, dataset_name):
        # Only update if the loaded dataset is currently selected
        if dataset_name == self.dataset_selection_widget.dataset_dropdown.currentText():
            self.create_statistics_table(dataset_name)
            # self.update_dataset_details(dataset_name)
            self.update_compare_feature_dropdowns()
        dataset_manager = getattr(self.controller.main_controller, "dataset_manager", None)
        if dataset_manager and dataset_name:
            dataset_manager.plot_correlation_heatmap(dataset_name, method="pearson")
            dataset_manager.plot_correlation_heatmap_ready.connect(self._on_compare_correlation_heatmap_ready)
            dataset_manager.plot_superimposed_histograms(dataset_name)
            dataset_manager.plot_superimposed_histograms_ready.connect(self._on_compare_superimposed_histograms_ready)
            dataset_manager.plot_ridgeline(dataset_name)
            dataset_manager.plot_ridgeline_ready.connect(self._on_compare_ridgeline_ready)

    def create_statistics_table(self, dataset_name):
        self.scatter_movie.start()
        self.ts_movie.start()
        self.scatter_stack.setCurrentIndex(1)
        self.ts_stack.setCurrentIndex(1)

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

        # Connect cellClicked only once
        try:
            self.stats_table.cellClicked.disconnect()
        except Exception:
            pass

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
        if row == self.plotted_row:
            return
        self.plotted_row = row

        self.show_scatter_loading(True)
        self.show_ts_loading(True)
        if self.controller and hasattr(self.controller.main_controller, "dataset_manager"):
            dataset_manager = self.controller.main_controller.dataset_manager
        feature_item = self.stats_table.item(row, 0)
        if feature_item:
            feature_name = feature_item.text()

            category = None
            category_col = None
            # Find the column index for "Category"
            for col in range(self.stats_table.columnCount()):
                if self.stats_table.horizontalHeaderItem(col).text().lower() == "category":
                    category_col = col
                    break
            if category_col is not None:
                # If using a QComboBox as cell widget
                combo = self.stats_table.cellWidget(row, category_col)
                if combo:
                    category = combo.currentText()
            color = self.category_colors.get(category, "blue")

            dataset_name = self.dataset_selection_widget.dataset_dropdown.currentText()
            new_x = dataset_manager.loaded_datasets[dataset_name].input_data[feature_name].values
            if self.scatter_fig is not None:
                self.scatter_fig.data[0].marker.color = color
                self.scatter_fig.data[0].x = new_x
                self.scatter_fig.data[0].y = dataset_manager.loaded_datasets[dataset_name].uncertainty_data[feature_name].values
                plot_html = self.scatter_fig.to_html(
                    full_html=False,
                    include_plotlyjs='cdn',
                    config={'responsive': True, 'displayModeBar': 'hover'}
                )
                plot_html = f"<div style='width:100%;height:100%;padding:0;maring:0;overflow:hidden'>{plot_html}</div>"
                self.scatter_view.setHtml(plot_html)
            else:
                dataset_manager.plot_data_uncertainty(dataset_name, feature_name)

            if self.ts_fig is not None:
                self.ts_fig.data[0].line.color = color
                self.ts_fig.data[0].marker.color = color
                self.ts_fig.data[0].y = new_x
                plot_html = self.ts_fig.to_html(
                    full_html=False,
                    include_plotlyjs='cdn',
                    config={'responsive': True, 'displayModeBar': 'hover'}
                )
                plot_html = f"<div style='width:100%;height:100%;padding:0;maring:0;overflow:hidden'>{plot_html}</div>"
                self.ts_view.setHtml(plot_html)
            else:
                dataset_manager.plot_feature_timeseries(dataset_name, feature_name)
        QTimer.singleShot(1500, lambda: self.show_scatter_loading(False))
        QTimer.singleShot(1500, lambda: self.show_ts_loading(False))

    def update_scatter_plot(self, feature_name, fig):
        """Slot to handle the uncertainty_plot_ready signal and update the scatter plot."""
        if fig is not None:
            for trace in fig.data:
                if hasattr(trace, "marker"):
                    trace.marker.symbol = "circle-open"
                    trace.marker.size = 4
                    trace.marker.line.width = 1
                    trace.marker.color = "green"
                    trace.marker.line.color = "green"
            fig.update_layout(
                title_text="Data/Uncertainty",
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
            plot_html = f"<div style='width:100%;height:100%;padding:0;maring:0;overflow:hidden'>{plot_html}</div>"
            self.scatter_view.setHtml(plot_html)
            self.scatter_fig = fig
        self.show_scatter_loading(False)

    def update_timeseries_plot(self, feature_name, fig):
        """Slot to handle the ts_plot_ready signal and update the timeseries plot."""
        if fig is not None:
            for trace in fig.data:
                if hasattr(trace, "marker"):
                    trace.marker.symbol = "circle-open"
                    trace.marker.size = 4
                    trace.marker.line.width = 1
                    trace.marker.color = "green"
                    trace.marker.line.color = "green"
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
            plot_html = f"<div style='width:100%;height:100%;padding:0;maring:0;overflow:hidden'>{plot_html}</div>"
            self.ts_view.setHtml(plot_html)
            self.ts_fig = fig
        self.show_ts_loading(False)

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
