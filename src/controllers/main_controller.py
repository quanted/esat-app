from PySide6.QtWidgets import QMainWindow, QStackedWidget

from src.views.main_view import MainView
from src.controllers import ProjectController, DataController
from src.models.dataset_manager import DatasetManager

class MainController(QMainWindow):
    def __init__(self, parent=None, webviews=None):
        super().__init__(parent)
        self.setWindowTitle("ESAT")
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.main_view = MainView(self)
        self.stack.addWidget(self.main_view)

        self.webviews = webviews if webviews is not None else []
        self.dataset_manager = DatasetManager(self)

        self.project_controller = ProjectController(self)
        self.data_controller = DataController(self, webviews=self.webviews)