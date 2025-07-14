import os
import json

from PySide6.QtWidgets import (
    QMainWindow, QMenuBar, QToolBar, QStatusBar, QProgressBar,
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QMenu, QLabel, QTextBrowser
)
from PySide6.QtGui import QIcon, QGuiApplication
from PySide6.QtCore import Qt, QSize

from src.controllers import ProjectController, DataController, ModelController


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

        # Set minimum size based on screen geometry
        screen_geom = QGuiApplication.primaryScreen().availableGeometry()
        min_width = min(1000, screen_geom.width())
        min_height = min(600, screen_geom.height())
        self.setMinimumSize(min_width, min_height)

        with open(os.path.join("src", "resources", "styles", "main_theme.qss"), "r") as f:
            self.setStyleSheet(f.read())
        self.icons_path = os.path.join("src", "resources", "icons")
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
        self.menu_icon_btn.setIcon(QIcon(os.path.join(self.icons_path, "menu-white.svg")))
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
            icon_path = os.path.join(self.icons_path, f"{item.lower()}-white.svg")
            list_icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()
            list_item = QListWidgetItem(list_icon, "")
            list_item.setToolTip(item)
            self.sidebar_widget.addItem(list_item)

        self.central_layout.addWidget(self.sidebar_widget)

        # Main content area (for swapping views)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.central_layout.addWidget(self.content_widget)

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
        self.load_main_content()

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
            self.load_main_content()
        elif tooltip == "Project":
            self.main_controller.project_controller.show_project_view()
        elif tooltip == "Data":
            self.main_controller.data_controller.show_data_view()
        elif tooltip == "Models":
            self.main_controller.model_controller.show_data_view()

    def load_main_content(self):
        content_path = os.path.join("src", "resources", "content")
        json_path = os.path.join(content_path, "main_content.json")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Clear central widget layout
        layout = self.content_layout
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setAlignment(Qt.AlignCenter)
        for i in reversed(range(layout.count())):
            widget = layout.itemAt(i).widget()
            if widget is not None:
                layout.removeWidget(widget)
                widget.setParent(None)

        # Title
        title_label = QLabel(f"<h2>{data.get('title', '')}</h2>")
        layout.addWidget(title_label, alignment=Qt.AlignHCenter)

        # Description
        desc_label = QLabel(data.get("description", ""))
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label, alignment=Qt.AlignHCenter)

        # Links
        links = data.get("links", [])
        if links:
            links_browser = QTextBrowser()
            links_html = "<ul>"
            for link in links:
                links_html += f'<li><a href="{link["url"]}">{link["text"]}</a></li>'
            links_html += "</ul>"
            links_browser.setHtml(links_html)
            links_browser.setOpenExternalLinks(True)
            links_browser.setMaximumHeight(100)
            layout.addWidget(links_browser)
