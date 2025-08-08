import os

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QMovie


def create_loader(loader_size=64):
    """Create a loader QWidget with a centered spinner and full background."""
    loader_path = os.path.join("src", "resources", "icons", "loading_spinner.gif")

    container = QWidget()
    container.setStyleSheet("background: #fff;")  # Fill background
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addStretch()
    label = QLabel()
    label.setFixedSize(loader_size, loader_size)
    label.setAlignment(Qt.AlignCenter)
    movie = QMovie(loader_path)
    movie.setScaledSize(QSize(loader_size, loader_size))
    label.setMovie(movie)
    layout.addWidget(label, alignment=Qt.AlignCenter)
    layout.addStretch()
    return container, movie

def toggle_loader(stack, movie, show):
    if show:
        movie.start()
        stack.setCurrentIndex(1)
    else:
        movie.stop()
        stack.setCurrentIndex(0)
