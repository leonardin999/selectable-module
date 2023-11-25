"""
TODO: Insert description here
"""
import logging
import os
import time

from PySide6.QtCore import QObject, SIGNAL


class CustomFormatter(logging.Formatter):
    """
    setup colour and logging message display
    """
    blue = "(coded: #0000FF)"
    black = "(coded: #000000)"
    red = "(coded: #FF0000)"
    purple = "(coded: #800080)"
    format = "%(asctime)s - %(name)s : %(message)s"

    FORMATS = {
        logging.DEBUG: f"{blue} {format}",
        logging.INFO: f"{black} {format}",
        logging.WARNING: f"{blue} {format}",
        logging.ERROR: f"{red} {format}",
        logging.CRITICAL: f"{purple} {format}",
    }
    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

class ConsoleWindowLogHandler(logging.Handler):
    """
    A handler class which writes logging records, appropriately formatted,
    """

    def __init__(self, signal_emitter):
        super().__init__()
        self.signal_emitter = signal_emitter
        self.setLevel(logging.DEBUG)
        self.setFormatter(CustomFormatter())

    def emit(self, record):
        """
        Emit a log message to the console window.
        """
        message = self.format(record)
        # noinspection PyTypeChecker
        # QString is automatically converted to bytes in C++
        # noinspection PydanticTypeChecker
        self.signal_emitter.emit(SIGNAL("to_console(QString)"), message)


emitter = QObject()
console_handler = ConsoleWindowLogHandler(emitter)
console_handler.setLevel(logging.DEBUG)

def get_logger(name):
    """
    Returns a logger with the given name.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(console_handler)
    return logger


def setup_logger(module: str, path: str):
    """
    setup file loggers
    """
    config_global = os.path.join(path, f'_smb/{module}')
    logger = logging.getLogger(f'{module}')
    logger.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    log_name = time.strftime("%Y%m%d") + '_' + time.strftime("%H%m%S")
    if not os.path.isdir(f"{config_global}/logs"):
        os.makedirs(f"{config_global}/logs", exist_ok=True)
    file_handler = logging.FileHandler(f"{config_global}/logs/{log_name}.txt", mode='w')
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    return logger
