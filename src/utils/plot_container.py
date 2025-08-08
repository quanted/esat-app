from PySide6.QtWidgets import (QWidget, QStackedLayout)


def create_plot_container(view, loader):
    container = QWidget()
    container.setStyleSheet("background: #fff;")
    container.setMinimumSize(200, 200)

    stack = QStackedLayout()
    stack.addWidget(view)
    stack.addWidget(loader)
    container.setLayout(stack)
    return None, container, stack