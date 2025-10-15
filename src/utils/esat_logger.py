# src/utils/esat_logger.py
from logging import Formatter, ERROR, WARNING, INFO, DEBUG, getLogger, FileHandler
from warnings import showwarning
from sys import __excepthook__, excepthook
from os import path

_logger = None
_file_handler = None

class HighlightFormatter(Formatter):
    def format(self, record):
        if record.levelno >= ERROR:
            record.msg = "[ERROR] " + str(record.msg)
        elif record.levelno == WARNING:
            record.msg = "[WARNING] " + str(record.msg)
        return super().format(record)

def init_logger():
    global _logger
    if _logger is None:
        _logger = getLogger('esat')
        _logger.setLevel(DEBUG)

    def log_warning(message, category, filename, lineno, file=None, line=None):
        _logger.warning(f'{filename}:{lineno}: {category.__name__}: {message}')
    showwarning = log_warning

    def log_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            __excepthook__(exc_type, exc_value, exc_traceback)
            return
        _logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
    excepthook = log_exception

def set_log_file(project_dir, level=INFO):
    global _logger, _file_handler
    if _logger is None:
        init_logger()
    log_path = path.join(project_dir, 'error.log')
    if _file_handler:
        _logger.removeHandler(_file_handler)
    _file_handler = FileHandler(log_path, mode='a')
    _file_handler.setLevel(level)
    formatter = HighlightFormatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    _file_handler.setFormatter(formatter)
    _logger.addHandler(_file_handler)

def get_logger():
    global _logger
    if _logger is None:
        raise RuntimeError("Logger not initialized. Call init_logger() first.")
    return _logger
