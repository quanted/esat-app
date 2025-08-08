from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class FactorAnalysisSubTab(QWidget):
    def __init__(self, parent=None, controller=None):
        super().__init__(parent)
        self.controller = controller
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Factor Analysis Content"))

