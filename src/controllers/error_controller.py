from src.views.error_view import ErrorView
from esat.model import SA


class ErrorController:
    def __init__(self, main_controller, webviews=None):
        self.main_controller = main_controller
        self.error_view = ErrorView(parent=self.main_controller.main_view, controller=self, webviews=webviews)
        self.error_view.setVisible(False)
        self.first_load = True

        self.selected_model = None

    def set_model(self, model: SA):
        self.selected_model = model

    def show_view(self):
        # Remove current main content
        if self.first_load:
            self.error_view.setVisible(True)
            self.first_load = False

        central_layout = self.main_controller.main_view.content_layout
        for i in reversed(range(central_layout.count())):
            widget = central_layout.itemAt(i).widget()
            if widget is not None:
                central_layout.removeWidget(widget)
                widget.setParent(None)
        # Add ErrorView if not already present
        if self.error_view not in [central_layout.itemAt(i).widget() for i in range(central_layout.count())]:
            central_layout.addWidget(self.error_view)

        self.error_view.reattach_webviews()