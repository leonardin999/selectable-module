"""
TODO: Write docstring
"""
import math
import os
import sys

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox,
                               QGroupBox, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget, QScrollArea)

from tools import rtegen, bct, damos
from utilities.log import get_logger

logger = get_logger(__name__)


def get_tealeaves_path(version="latest") -> str:
    """
    get tealeaves from Toolbase
    """
    tealeaves_path = os.path.join("C:\\toolbase\\tealeaves")
    if os.path.exists(tealeaves_path):
        if version == "latest":
            all_versions = [os.path.join(tealeaves_path, v)
                            for v in os.listdir(tealeaves_path)]
            return os.path.normpath(max(all_versions, key=os.path.getmtime))
    return "\\latest"


def fetch_ecuwork_tools(path: str):
    """
    config the Ecu.Work Version compatible with the current Pver
    """
    tools = []
    path += "/medc17_tools.ini"
    if not os.path.isfile(path):
        logger.error("No medc17_tools.ini found")
        return None

    with open(path, "r", encoding='utf-8') as file:
        for line in file:
            if line.startswith('PRJ_WORKBENCH'):
                tools.append(line.strip().split("=")[1])

    tools_path = str.join('\\', tools)
    return os.path.join('c:\\toolbase\\', tools_path)


class ToolsDetailWidget(QGroupBox):
    """
    ToolDetailWidget is a QTreeWidget that displays the details of tools.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(250)
        self.process_count = 0
        self.process = None
        self.state = QProcess.NotRunning
        self.stdout = ""
        self.global_path = ""
        self.tools = {}
        for name in ["tealeaves", "rtarte", "damos", "ECU.WorX", "mdgb", "dgs_ice",
                     "dgs_signature", "dgs_signature_keys"]:
            self.tools[name] = {
                "versions": '',
                "enabled": False,
                "btn": self.create_tool_install_btn(name),
                "path": '',
            }
        self.tools_signal = {
            "rtarte": rtegen.signal.sync,
            "ECU.WorX": bct.signal.sync
        }
        self.damos_tools = {
            "damos": "",
            "dgs_ice": "",
            "dgs_signature": "",
            "dgs_signature_keys": ""
        }
        self.path = None

        self.setTitle("Tools")

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.refresh_button.setFixedWidth(100)
        self.refresh_button.setDisabled(True)

        self.install_all_button = QPushButton("Install all tools")
        self.install_all_button.clicked.connect(self.install_all_tools)
        self.install_all_button.setFixedWidth(100)
        self.install_all_button.setDisabled(True)

        self.tools_group_widget = QScrollArea()
        self.tools_group_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.tools_group_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tools_group_widget.setWidgetResizable(True)
        self.tools_group_widget.setMinimumHeight(100)
        self.layout_tools = QVBoxLayout()
        self.contain_tools = QWidget()

        layout = QHBoxLayout()
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.install_all_button)
        layout.setAlignment(Qt.AlignRight)
        widget = QWidget()
        widget.setLayout(layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Installing tools")
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setTextVisible(True)

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(widget)
        self.layout().addWidget(self.progress_bar)
        self.layout().addWidget(self.tools_group_widget)

    def refresh(self) -> None:
        """
        Refresh the tools group
        """
        if self.path is None:
            logger.warning("Please Add a Pver first.")
            dialog = QDialog()
            dialog.setWindowTitle("No Path")
            dialog.setMinimumWidth(300)
            dialog.setMinimumHeight(100)
            dialog.setLayout(QVBoxLayout())
            dialog.layout().addWidget(QLabel("Please add a path first."))
            dialog.exec()
            return
        logger.debug("Refreshing tools")
        for tool in self.tools:
            self.tools[tool] = {
                "versions": '',
                "enabled": False,
                "btn": self.create_tool_install_btn(tool),
                "path": ''
            }
        self.contain_tools.deleteLater()
        self.layout_tools.deleteLater()
        self.layout().removeWidget(self.tools_group_widget)
        self.fetch_pver_tools(self.path)

    def create_tool_install_btn(self, name: str) -> QPushButton:
        """
        Create "Install" button for each tool, if it's not installed yet.
        """
        tool_button = QPushButton("Install")

        def __on_click__():
            """
            Install the tool
            """
            self.process_count = 1
            self.initialize_progress_bar()
            logger.debug(f"Installing {name}.")
            self.enable_tool(name, self.tools[name]["versions"], self.tools[name]["btn"])

        tool_button.clicked.connect(__on_click__)
        tool_button.setFixedWidth(100)
        tool_button.setFixedHeight(25)

        return tool_button

    def clear_tools(self) -> None:
        """
        Create the tools group widget
        """
        for tool in self.tools:
            self.tools[tool] = {
                "versions": '',
                "enabled": False,
                "btn": self.create_tool_install_btn(tool),
                "path": ''
            }
        self.contain_tools.deleteLater()
        self.layout_tools.deleteLater()
        self.layout().removeWidget(self.tools_group_widget)
        self.tools_group_widget.deleteLater()
        self.tools_group_widget = QScrollArea()
        self.contain_tools = QWidget()
        self.layout_tools = QVBoxLayout()
        self.tools_group_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.tools_group_widget.setWidgetResizable(True)
        self.layout().addWidget(self.tools_group_widget)

    def fetch_pver_tools(self, path: str) -> None:
        """
        Fetch the tools of the current pver
        """
        self.clear_tools()
        self.path = path
        path += "/_log/swb/tool_vers.log"
        if not os.path.isfile(path):
            logger.error("No tool_vers.log found")
            return

        with open(path, "r") as file:
            for line in file:
                if line.startswith(tuple([tool for tool in self.tools])):
                    name, exec_path = (data.strip() for data in line.split(":", 1))
                    self.tools[name]['path'] = exec_path

        ecu_path = fetch_ecuwork_tools(self.path)
        if ecu_path is not None:
            self.tools['ECU.WorX']['path'] = ecu_path

        self.tools['tealeaves']['path'] = get_tealeaves_path()

        install_tools_list = []
        for tool_name in self.tools:
            tool_path = self.tools[tool_name]['path']
            if tool_name in self.tools_signal:
                self.tools_signal[tool_name].emit(tool_path)
            version = self.tools[tool_name]['path'].split("\\")[-1].strip()
            if tool_name in self.damos_tools:
                self.damos_tools[tool_name] = f"tini {tool_name} {version}"
            label = QLabel(f"{tool_name} - [version: {version}]")

            tool_widget = QWidget()
            tool_widget.setLayout(QHBoxLayout())
            tool_widget.layout().setContentsMargins(10, 5, 10, 2)
            tool_widget.layout().addWidget(label)
            tool_widget.layout().addWidget(self.tools[tool_name]["btn"])
            self.layout_tools.addWidget(tool_widget)
            self.contain_tools.setLayout(self.layout_tools)

            if os.path.isdir(self.tools[tool_name]['path']):
                logger.debug(f"{tool_name} {version} found")
                self.tools[tool_name]['btn'].setDisabled(True)
                self.tools[tool_name]['btn'].setText("Installed")
                self.tools[tool_name]['btn'].setFixedHeight(25)
                self.update_tool_detail(tool_name, version, True)
            else:
                logger.warning(f"{tool_name} {version} not found")
                self.update_tool_detail(tool_name, version, False)
                install_tools_list.append(tool_name)

        self.tools_group_widget.setWidget(self.contain_tools)
        self.tools_group_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.tools_group_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tools_group_widget.setWidgetResizable(True)

        damos.tini_signal.sync.emit(self.damos_tools)
        # Skip installing tools if there are no tools to install
        if len(install_tools_list) == 0:
            return

        # Enable buttons for tools widget
        self.install_all_button.setEnabled(True)
        self.refresh_button.setEnabled(True)

        # Create a dialog to ask user to install tools
        dialog = QDialog()
        dialog.setWindowTitle("Installer")
        dialog.setMinimumWidth(400)
        dialog.setMinimumHeight(100)
        dialog.setModal(True)
        dialog.setLayout(QVBoxLayout())
        text = ", ".join([f"{x} : {self.tools[x]['version']}" for x in install_tools_list])
        dialog.layout().addWidget(QLabel(f"{text} are missing."))
        dialog.layout().addWidget(QLabel("Do you want to install above tools now?"))
        q_btn = QDialogButtonBox.Yes | QDialogButtonBox.No
        button_box = QDialogButtonBox(q_btn)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog.layout().addWidget(button_box)

        if dialog.exec():
            self.process_count = len(install_tools_list)
            self.initialize_progress_bar()
            for tool_name in install_tools_list:
                self.enable_tool(tool_name, self.tools[tool_name]['version'],
                                 self.tools[tool_name]['btn'])

    def update_tool_detail(self, name, version, enabled) -> None:
        """
        Update tool
        """
        self.tools[name]["version"] = version
        self.tools[name]["enabled"] = enabled

    def initialize_progress_bar(self):
        """
        Initialize the progress bar
        """
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

    def enable_tool(self, tool_name: str, version: str, btn: QPushButton):
        """
        Install the respective tool
        """
        btn.setEnabled(False)
        btn.setText("Installing")
        self.refresh_button.setEnabled(False)
        self.install_all_button.setEnabled(False)
        process = QProcess()

        def __on_finish__():
            """
            Handle the finished signal of the installation process
            """
            logger.debug(f"{tool_name} {version} enabled.")
            btn.setText("Installed")
            self.process_count -= 1

            # If all tools are enabled, run toolbase update
            if self.process_count == 0:
                self.run_toolbase_update()
            else:
                self.progress_bar.setValue(self.progress_bar.value() + 50 / self.process_count)

        def __out__():
            """
            Handle the output of the installation process
            """
            data = process.readAllStandardOutput()
            stdout = bytes(data).decode("utf8").strip()
            if stdout:
                logger.debug(stdout)
                self.progress_bar.setValue(self.progress_bar.value() + 1)

        process.started.connect(lambda: self.progress_bar.setFormat(f"Enable {tool_name}: {version}"))
        process.readyReadStandardOutput.connect(__out__)
        process.readyReadStandardError.connect(__out__)
        process.finished.connect(__on_finish__)
        process.startCommand(f"tbexcmd -useEnv:dgs -command EnableTool {tool_name}/{version}")

    def run_toolbase_update(self):
        """
        Run the toolbase update
        """

        logger.critical("Running toolbase update")
        process = QProcess()

        def __log__(data):
            out = bytes(data).decode("utf8").strip()
            if out:
                logger.debug(out)

                current_progress = self.progress_bar.value()
                if current_progress < 98:
                    value = round(math.log(100 - current_progress, 2) * 2)
                    self.progress_bar.setValue(current_progress + value)

        def process_finished():
            logger.debug("Toolbase update complete")
            self.progress_bar.setValue(self.progress_bar.maximum())
            self.progress_bar.setVisible(False)
            self.refresh_button.setEnabled(True)
            self.install_all_button.setEnabled(True)

        process.readyReadStandardOutput.connect(
            lambda: __log__(process.readAllStandardOutput())
        )
        process.readyReadStandardError.connect(
            lambda: __log__(process.readAllStandardError())
        )
        process.started.connect(lambda: self.progress_bar.setFormat("Run Toolbase Update "))
        process.finished.connect(lambda: logger.debug("Toolbase update complete"))
        process.finished.connect(lambda: self.progress_bar.setValue(self.progress_bar.maximum()))
        process.finished.connect(lambda: self.progress_bar.setVisible(False))
        process.startCommand("tbupdate -e")

    def install_all_tools(self):
        """
        Install all tools
        """
        tools_list = [tools for tools in self.tools
                      if self.tools[tools]['enabled'] is False]
        self.process_count = len(tools_list)
        logger.critical(f"Installing {self.process_count} tools")
        self.initialize_progress_bar()
        for tool_name in tools_list:
            self.enable_tool(tool_name, self.tools[tool_name]['version'],
                             self.tools[tool_name]['btn'])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ToolsDetailWidget()
    window.show()
    sys.exit(app.exec())
