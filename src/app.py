from os import path
from sys import argv, exit

from PySide6.QtWidgets import QApplication, QSplashScreen
from PySide6.QtGui import QMovie, QIcon
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings

from src.controllers.main_controller import MainController
from src.utils import xWebEngineView
from src.utils.loader import get_resource_path



def cleanup():
    # Example: terminate multiprocessing pools, threads, or other resources
    MainController.global_cleanup()

def do_init(app, splash):
    webviews = []

    base_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
            <style>
                body { margin: 0; padding: 0; font-family: Arial; }
                .plotly-graph-div { height: 100%; width: 100%; }
            </style>
        </head>
        <body>
            <div id="plotly-div" style="height: 100%; width: 100%;"></div>
        </body>
        </html>
        """

    for i in range(12):
        webview = xWebEngineView()

        webview.setAttribute(Qt.WA_DontShowOnScreen, True)
        webview.setHtml(base_html)

        custom_profile = QWebEngineProfile(f"webview_{i}", webview)
        page = QWebEnginePage(custom_profile, webview)

        settings = page.settings()

        # Disable unnecessary features
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, False)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)  # Keep for Plotly
        settings.setAttribute(QWebEngineSettings.AutoLoadImages, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, False)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.SpatialNavigationEnabled, False)
        settings.setAttribute(QWebEngineSettings.TouchIconsEnabled, False)
        settings.setAttribute(QWebEngineSettings.FocusOnNavigationEnabled, False)

        # Optimize caching
        custom_profile.setHttpCacheType(QWebEngineProfile.MemoryHttpCache)
        custom_profile.setHttpCacheMaximumSize(2 * 1024 * 1024)  # 10 MB

        # Disable persistent storage
        custom_profile.setPersistentStoragePath("")

        custom_profile.setSpellCheckEnabled(False)

        webview.setPage(page)

        webview.show()
        webviews.append(webview)

        # Process events in batches rather than each iteration
        if i % 4 == 0:  # Every 4 webviews
            app.processEvents()

    controller = MainController(webviews=webviews)
    controller.show()
    splash.finish(controller)

def main():
    app = QApplication(argv)
    app.aboutToQuit.connect(cleanup)

    # Set application icon
    esat_icon_path = get_resource_path(path.join("icons", "esat-logo.png"))
    esat_transparent_icon = get_resource_path(path.join("icons", "esat-logo-transparent.png"))
    if path.exists(esat_transparent_icon):
        app.setWindowIcon(QIcon(esat_transparent_icon))

    # Load the GIF and extract the first frame as a pixmap
    movie = QMovie(esat_icon_path)
    movie.setScaledSize(QSize(64, 64))
    movie.jumpToFrame(0)
    pixmap = movie.currentPixmap()

    splash = QSplashScreen(pixmap, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
    splash.setAttribute(Qt.WA_TranslucentBackground)
    splash.show()
    app.processEvents()

    QTimer.singleShot(100, lambda: do_init(app, splash))

    exit(app.exec())

if __name__ == "__main__":
    main()