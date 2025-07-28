import os
from PySide6.QtWidgets import QWidget

from src.views.project_view import ProjectView


class ProjectController:
    def __init__(self, main_controller):
        self.main_controller = main_controller
        self.project_view = ProjectView(parent=self.main_controller.main_view, controller=self)
        self.project_view.setVisible(False)
        self.first_load = True

    def show_project_view(self):
        # Remove current main content
        if self.first_load:
            self.project_view.setVisible(True)
            self.first_load = False
        central_layout = self.main_controller.main_view.content_layout
        for i in reversed(range(central_layout.count())):
            widget = central_layout.itemAt(i).widget()
            if widget is not None:
                central_layout.removeWidget(widget)
                widget.setParent(None)
        # Add ProjectView if not already present
        if self.project_view not in [central_layout.itemAt(i).widget() for i in range(central_layout.count())]:
            central_layout.addWidget(self.project_view)
