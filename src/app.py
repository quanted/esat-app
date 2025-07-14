from PySide6.QtWidgets import QApplication, QSplashScreen, QLabel
from PySide6.QtGui import QPixmap, QMovie
from PySide6.QtCore import Qt, QSize, QTimer
from src.controllers.main_controller import MainController
import sys

def do_init(app, splash):
    from PySide6.QtWebEngineWidgets import QWebEngineView

    webviews = []
    for _ in range(8):
        wv = QWebEngineView()
        wv.setAttribute(Qt.WA_DontShowOnScreen, True)
        wv.setHtml("<html></html>")
        wv.show()
        webviews.append(wv)
        app.processEvents()

    controller = MainController(webviews=webviews)
    controller.show()
    splash.finish(controller)

def main():
    app = QApplication(sys.argv)

    # Load the GIF and extract the first frame as a pixmap
    movie = QMovie("src/resources/icons/loading_spinner.gif")
    movie.setScaledSize(QSize(64, 64))
    movie.jumpToFrame(0)
    pixmap = movie.currentPixmap()

    splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    splash.setAttribute(Qt.WA_TranslucentBackground)
    splash.show()
    app.processEvents()

    QTimer.singleShot(1000, lambda: do_init(app, splash))

    sys.exit(app.exec())

if __name__ == "__main__":
    main()