import os
import sys

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QApplication)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QMovie


def get_resource_path(rel_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, 'resources', rel_path)
    else:
        return os.path.join('src', 'resources', rel_path)


def create_loader(loader_size=64):
    """Create a loader QWidget with a centered spinner and full background."""
    loader_path = get_resource_path(os.path.join('icons', 'loading_spinner.gif'))

    container = QWidget()
    container.setStyleSheet("background: #fff;")  # Fill background
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addStretch()
    label = QLabel()
    label.setFixedSize(loader_size, loader_size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    movie = QMovie(loader_path)
    movie.setScaledSize(QSize(loader_size, loader_size))
    label.setMovie(movie)
    layout.addWidget(label, alignment=Qt.AlignmentFlag.AlignCenter)
    layout.addStretch()
    return container, movie


def toggle_loader(stack, movie, show, speed=500):
    if show:
        movie.setSpeed(speed)
        movie.start()
        stack.setCurrentIndex(1)
    else:
        movie.stop()
        stack.setCurrentIndex(0)
