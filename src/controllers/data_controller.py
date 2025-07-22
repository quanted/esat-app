from PySide6.QtCore import QTimer

from src.views.data_view import DataView


class DataController:
    def __init__(self, main_controller, webviews=None):
        self.main_controller = main_controller  # Expected to be MainView
        self.data_view = DataView(parent=self.main_controller.main_view, controller=self, webviews=webviews)
        self.data_view.setVisible(False)
        self.first_load = True

    def show_data_view(self):
        # Remove current main content
        if self.first_load:
            self.data_view.setVisible(True)
            self.first_load = False
        central_layout = self.main_controller.main_view.content_layout
        for i in reversed(range(central_layout.count())):
            widget = central_layout.itemAt(i).widget()
            if widget is not None:
                central_layout.removeWidget(widget)
                widget.setParent(None)
        # Add DataView if not already present
        if self.data_view not in [central_layout.itemAt(i).widget() for i in range(central_layout.count())]:
            central_layout.addWidget(self.data_view)

        QTimer.singleShot(0, self.data_view.reattach_webviews)
