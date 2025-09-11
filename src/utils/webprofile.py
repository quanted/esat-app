from PySide6.QtWebEngineCore import QWebEngineProfile


class xWebEngineProfile(QWebEngineProfile):
    def __init__(self, name=None, parent=None):
        super().__init__(name, parent)
        self._metadata = {}  # Dictionary to store custom metadata

    def set_metadata(self, key, value):
        self._metadata[key] = value

    def get_metadata(self, key):
        if key in self._metadata:
            return self._metadata.get(key)
        return None