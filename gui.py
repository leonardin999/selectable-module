"""
TODO: Write docstring
"""
import argparse
import sys
import functools
import os
import time

from PySide6.QtCore import Qt, QThreadPool, SIGNAL
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStyleFactory,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
    QMessageBox
)
from utilities.check import is_environment_compatible
from utilities.log import console_handler, emitter, get_logger
from utilities.profiler import profiler_signal
from widgets import PVERTreeWidget, ToolsDetailWidget
from tools.rtegen import rtegen_signal
from tools.bct import bct_signal, bct_saving_signal
from tools.damos import damos_signal

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """
    Main window of the application.
    """

    def __init__(self) -> None:
        super().__init__()

        # Setup Logging First
        self.file_name = ''
        self.style_string = ''
        self._console = QTextBrowser()
        self._console.setReadOnly(True)

        self._console.setFontPointSize(10)
        self._console.setFontWeight(50)
        self._console.setTextInteractionFlags(Qt.TextSelectableByMouse)

        def __to_console__(log_record: str) -> None:
            """
            format the log message to the console
            """

            import re
            re_find_color = re.compile(r"\(coded:(.+?)\)")
            color = re_find_color.findall(log_record)[-1].strip()
            message = str(re_find_color.sub("", log_record).strip())
            self.style_string += f"<div style=\"color:{color};white-space: pre-line;\" >{message}</div>"
            self._console.moveCursor(QTextCursor.End)
            self._console.setHtml(self.style_string)
            self._console.moveCursor(QTextCursor.End)

        self.connect(emitter, SIGNAL("to_console(QString)"), __to_console__)

        # Global Instance
        self.thread_pool = QThreadPool.globalInstance()

        # Main Windows Attribute
        self.setStyle(QStyleFactory.create("default"))
        self.setWindowTitle("Selectable Module Build")
        self.setFixedWidth(1500)
        self.setFixedHeight(900)
        self.closeEvent = functools.partial(self.quit_action)

        # Create Main GUI Component
        widget = QWidget()
        layout = QHBoxLayout(widget)
        self.global_path = None
        self.pver_tree = PVERTreeWidget()
        layout.addWidget(self.pver_tree)

        self.tools_detail = ToolsDetailWidget()
        layout.addWidget(self.create_right_frame())
        self.setCentralWidget(widget)

        self.pver_tree.signal.loaded.connect(self.global_path_config)
        self.pver_tree.signal.loaded.connect(self.tools_detail.fetch_pver_tools)

    def global_path_config(self, path: str) -> None:
        """
        config the current directory that SMB tools is working on.
        """
        # clear the console after reload a PVER
        self.global_path = path

        log_name = time.strftime("%Y%m%d")
        working_path = self.global_path + "/_smb"
        if os.path.isdir(working_path):
            os.makedirs(working_path, exist_ok=True)
        log_path = working_path + '/logs'
        if not os.path.isdir(log_path):
            os.makedirs(log_path, exist_ok=True)
        self.file_name = log_path + f"/logs_{log_name}.txt"
        if self.file_name:
            with open(self.file_name, "a", encoding="utf-8") as file:
                file.write(self._console.toPlainText())
            file.close()
        self._console.clear()
        self.style_string =''
        logger.debug('Loading PVER: {}\n'.format(self.global_path.split('/')[-1]))

        # remove all the created in the process run tools
        if os.path.exists(self.global_path + r"/_smb/damos/smb_pavast.xml"):
            os.remove(self.global_path + r"/_smb/damos/smb_pavast.xml")

        if os.path.exists(self.global_path + r"/_smb/SMB_Rtegen_all_files.lst"):
            os.remove(self.global_path + r"/_smb/SMB_Rtegen_all_files.lst")

        rtegen_signal.sync.emit(self.global_path)
        bct_signal.sync.emit(self.global_path)
        bct_saving_signal.sync.emit(working_path)
        damos_signal.sync.emit(working_path)
        profiler_signal.sync.emit(working_path)

    def create_right_frame(self):
        """
        Create the right frame of the main window.
        """
        right_frame = QWidget()
        right_frame.setLayout(QVBoxLayout())
        right_frame.layout().addWidget(self.tools_detail)
        right_frame.layout().addWidget(self.pver_tree.widget_progress)
        right_frame.layout().addWidget(self._console)
        return right_frame

    def quit_action(self, event=None):
        """
        Action to do when quitting the tool. killing the thread and multiprocess before qutting
        """
        msg = QMessageBox()
        msg.setWindowTitle("Exit?!")
        msg.setText("Do you want to quit the application?\n\nNote: Tools will be unresponsive "
                    "for a moment while killing the background tasks or "
                    "reverting back the changes.")
        msg.setIcon(QMessageBox.Question)
        yes_button = msg.addButton(QMessageBox.Yes)
        msg.addButton(QMessageBox.No)
        msg.exec()
        if msg.clickedButton() == yes_button:
            logger.critical("System exit!\n")
            logger.debug('-'*200+'\n')
            if self.file_name:
                with open(self.file_name, "a", encoding="utf-8") as file:
                    file.write(self._console.toPlainText())
                file.close()
            if event:
                if self.pver_tree.process_running:
                    self.pver_tree.stop_process()
                event.accept()
            else:
                if self.pver_tree.process_running:
                    self.pver_tree.stop_process()
            sys.exit()
        else:
            pass

def run():
    """
    Start the application.
    """
    if is_environment_compatible():
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Select Module Build Tool')

    parser.add_argument('--dev', action='store_true', help='Run in development mode')

    args = parser.parse_args()
    if args.dev:
        console_handler.setLevel("DEBUG")
    run()
