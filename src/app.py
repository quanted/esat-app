from PySide6.QtWidgets import QApplication, QSplashScreen, QLabel
from PySide6.QtGui import QPixmap, QMovie
from PySide6.QtCore import Qt, QSize, QTimer
from src.controllers.main_controller import MainController
import sys

def do_init(app, splash):
    from PySide6.QtWebEngineWidgets import QWebEngineView

    # Pre-initialize all QWebEngineView instances needed
    webviews = []
    for _ in range(8):  # Adjust the range to the number of plots you need
        wv = QWebEngineView()
        wv.setAttribute(Qt.WA_DontShowOnScreen, True)
        wv.setHtml("<html></html>")
        wv.show()
        webviews.append(wv)
        app.processEvents()  # Ensure each is fully initialized

    # Pass webviews to your controller if needed
    controller = MainController(webviews=webviews)
    controller.show()
    splash.finish(controller)

def main():
    app = QApplication(sys.argv)

    splash_pix = QPixmap(64, 64)
    splash_pix.fill(Qt.white)
    splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    splash.setAttribute(Qt.WA_TranslucentBackground)
    spinner = QLabel(splash)
    spinner.setFixedSize(64, 64)
    movie = QMovie("src/resources/icons/loading_spinner.gif")
    movie.setScaledSize(QSize(64, 64))
    spinner.setMovie(movie)
    movie.start()
    splash.show()
    app.processEvents()

    QTimer.singleShot(1000, lambda: do_init(app, splash))

    sys.exit(app.exec())