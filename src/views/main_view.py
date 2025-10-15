from os import path
from json import load

from PySide6.QtWidgets import (
    QMainWindow, QMenuBar, QStatusBar, QProgressBar,
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QMenu, QLabel, QTextBrowser
)
from PySide6.QtGui import QIcon, QGuiApplication, QPixmap
from PySide6.QtCore import Qt, QSize

from src.utils.loader import get_resource_path
from src.utils.esat_logger import get_logger


class CustomMenuBar(QMenuBar):
    def __init__(self, parent, hide_callback):
        super().__init__(parent)
        self.hide_callback = hide_callback

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.hide_callback()


class MainView(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.main_controller = controller
        self.setWindowTitle("ESAT")
        self.resize(1200, 600)

        self.logger = get_logger()

        # Set minimum size based on screen geometry
        screen_geom = QGuiApplication.primaryScreen().availableGeometry()
        min_width = min(1000, screen_geom.width())
        min_height = min(600, screen_geom.height())
        self.setMinimumSize(min_width, min_height)

        if True:  # Always use helper for resource path
            qss_path = get_resource_path(path.join('styles', 'main_theme.qss'))
        else:
            qss_path = 'src/resources/styles/main_theme.qss'
        try:
            with open(qss_path, "r") as f:
                self.setStyleSheet(f.read())
        except PermissionError as e:
            self.logger.warning(f"[MainView]: Permission error: {e}")
        except Exception as e:
            self.logger.warning(f"[MainView]: Other error: {e}")

        self.icons_path = None  # Not needed anymore
        self.icon_height = 32

        # Menu Bar and Icon
        self.menu_bar = CustomMenuBar(self, self.hide_menu_bar)
        self.menu_bar.setFixedHeight(self.icon_height)
        self.menu_bar.addMenu("File")
        self.menu_bar.addMenu("Edit")
        self.menu_bar.addMenu("View")
        self.menu_bar.addMenu("Help")

        self.menu_icon_btn = QPushButton()
        self.menu_icon_btn.setObjectName("MenuIconButton")
        self.menu_icon_btn.setIcon(QIcon(get_resource_path(path.join('icons', 'menu-white.svg'))))
        self.menu_icon_btn.setFixedHeight(self.icon_height)
        self.menu_icon_btn.setFlat(True)

        # Top widget for menu
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        top_layout.setAlignment(Qt.AlignLeft)
        left_spacer = QWidget()
        left_spacer.setFixedWidth(4)
        top_layout.addWidget(left_spacer)
        top_layout.addWidget(self.menu_icon_btn)
        top_layout.addWidget(self.menu_bar)
        self.setMenuWidget(top_widget)

        self.menu_icon_btn.clicked.connect(self.show_menu_bar)
        for menu in self.menu_bar.findChildren(QMenu):
            menu.aboutToHide.connect(self.hide_menu_bar)
        self.menu_bar.setVisible(False)
        self.menu_icon_btn.setVisible(True)

        # Central widget with sidebar and main content
        self.central_widget = QWidget()
        self.central_layout = QHBoxLayout(self.central_widget)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)

        # Sidebar Navigation
        self.sidebar_widget = QListWidget()
        self.sidebar_widget.setObjectName("SidebarNav")
        self.sidebar_widget.setIconSize(QSize(20, 20))
        self.sidebar_widget.setFixedWidth(40)
        self.sidebar_widget.setSpacing(8)
        self.sidebar_widget.setSelectionMode(QListWidget.SingleSelection)
        self.sidebar_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.sidebar_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        nav_items = [
            "Home", "Project", "Data", "Models", "Workflows", "Error", "Docs", "Settings"
        ]
        for item in nav_items:
            icon_path = get_resource_path(path.join('icons', f"{item.lower()}-white.svg"))
            list_icon = QIcon(icon_path) if path.exists(icon_path) else QIcon()
            list_item = QListWidgetItem(list_icon, "")
            list_item.setToolTip(item)
            self.sidebar_widget.addItem(list_item)

        self.central_layout.addWidget(self.sidebar_widget)

        # Main content area (for swapping views)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.central_layout.addWidget(self.content_widget)

        # Container for main view widget (DataView, ProjectView, etc.)
        self.view_container = QWidget()
        self.view_layout = QVBoxLayout(self.view_container)
        self.view_layout.setContentsMargins(0, 0, 0, 0)
        # self.view_layout.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.view_container)
        # self.content_layout.setAlignment(Qt.AlignCenter)
        self.setCentralWidget(self.central_widget)

        # Status Bar with Progress Bar
        status_bar = QStatusBar(self)
        self.setStatusBar(status_bar)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        status_bar.addPermanentWidget(self.progress_bar)

        self.sidebar_widget.itemClicked.connect(self.handle_navbar_click)
        self.sidebar_widget.setCurrentRow(0)

    def _create_layout(self):
        self.title_label = QLabel()
        self.logo_label = QLabel()
        self.desc_label = QLabel()
        self.links_browser = QTextBrowser()
        self.links_browser.setMaximumHeight(100)
        # Align widgets in the content layout
        self.content_layout.addWidget(self.title_label, alignment=Qt.AlignHCenter)
        self.content_layout.addWidget(self.logo_label, alignment=Qt.AlignHCenter)
        self.content_layout.addWidget(self.desc_label, alignment=Qt.AlignHCenter)
        self.content_layout.addWidget(self.links_browser)

    def show_menu_bar(self):
        self.menu_icon_btn.setVisible(False)
        self.menu_bar.setVisible(True)
        self.menu_bar.setFocus()

    def hide_menu_bar(self):
        self.menu_bar.setVisible(False)
        self.menu_icon_btn.setVisible(True)

    def handle_navbar_click(self, item):
        tooltip = item.toolTip()
        if tooltip == "Home":
            self.main_controller.show_main_view()
        elif tooltip == "Project":
            self.main_controller.project_controller.show_view()
        elif tooltip == "Data":
            self.main_controller.data_controller.show_view()
        elif tooltip == "Models":
            self.main_controller.model_controller.show_view()

    def load_main_content(self):
        self._create_layout()
        json_path = get_resource_path(path.join('content', 'main_content.json'))
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = load(f)
        except Exception as e:
            self.logger.warning(f"[MainView]: Failed to load main content JSON: {e}")
            data = {"title": "", "description": "", "links": []}

        logo_path = get_resource_path(path.join('icons', 'esat-logo-transparent.png'))
        if path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            scaled_pixmap = pixmap.scaled(300, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.logo_label.setPixmap(scaled_pixmap)
            self.logo_label.setAlignment(Qt.AlignCenter)

        # Title
        self.title_label.setText(f"<h2>{data.get('title', '')}</h2>")
        # Description
        self.desc_label.setWordWrap(True)
        self.desc_label.setText(data.get("description", ""))

        # Links
        links = data.get("links", [])
        if links:
            links_html = "<ul>"
            for link in links:
                links_html += f'<li><a href="{link["url"]}">{link["text"]}</a></li>'
            links_html += "</ul>"
            self.links_browser.setHtml(links_html)
            self.links_browser.setOpenExternalLinks(True)
        else:
            self.links_browser.clear()
        self.content_widget.updateGeometry()

