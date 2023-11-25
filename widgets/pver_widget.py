"""
TODO: Write Docstring
"""
import os
import re
import glob
import pathlib
import sqlite3
import sys
import traceback
import math
import psutil
from typing import List
from PySide6.QtCore import (QDir, QObject, QRunnable, Qt,
                            QThreadPool, Signal, Slot, QProcess)
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QMessageBox, QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QProgressBar,
    QHBoxLayout,
    QWidget
)
from tools import bct, rtegen, damos
from utilities.check import check_pver_is_built, is_modified
from utilities.log import get_logger, setup_logger
from utilities.profiler import profiling

logger = get_logger(__name__)
TEALEAVES_PATH = os.path.join("C:\\toolbase\\tealeaves")


class BrowseDialog(QFileDialog):
    """
    BrowseDialog is a QFileDialog that allows the user to browse for a PVER folder
    """

    class DialogSignal(QObject):
        """
        DialogSignal is a QObject that allows the BrowseDialog to emit signals
        """
        build_pver = Signal(bool, object)
        fetch_tools = Signal(str)

    def __init__(self):
        super().__init__()
        self.setFilter(self.filter() | QDir.Hidden)
        self.setFileMode(self.Directory)
        self.setAcceptMode(self.AcceptOpen)
        self.signal = self.DialogSignal()
        if self.exec() == self.Accepted:
            path = self.selectedFiles()[0]
            thread_pool = QThreadPool().globalInstance()
            self.worker = PverLoadWorker(path)
            # noinspection PyUnresolvedReferences
            self.worker.signal.result.connect(self.on_result)
            # noinspection PyUnresolvedReferences
            self.worker.signal.finished.connect(self.on_finish)
            # noinspection PyUnresolvedReferences
            self.worker.signal.error.connect(self.on_error)
            thread_pool.start(self.worker)

    def on_result(self,permit, path, tree):
        """
        on_result is a Slot that is called when the worker thread emits a result signal
        """
        self.signal.fetch_tools.emit(path)
        # noinspection PyUnresolvedReferences
        self.signal.build_pver.emit(permit, tree)
        # noinspection PyUnresolvedReferences

    def on_finish(self):
        """
        on_finish is a Slot that is called when the worker thread finishes
        """
        self.worker = None

    def on_error(self, exec_type, value, exception_str):
        logger.error(f"Exception occurs. Type: {exec_type}, value: {value}, detail: {exception_str}")

        msg = QMessageBox()
        msg.setWindowTitle("Fatal error!!")
        msg.setText("Some exception happens. Please re-open the application.\n"
                    "If issue still exists please contact SMB support team.")
        msg.setIcon(QMessageBox.Abort)
        yes_button = msg.addButton(QMessageBox.Ok)
        msg.exec()
        if msg.clickedButton() == yes_button:
            pass


class PverLoadWorker(QRunnable):
    """
    PverLoadWorker is a QRunnable that loads a PVER folder
    """

    class WorkerSignal(QObject):
        """
        WorkerSignal is a QObject that allows the PverLoadWorker to emit signals
        """
        finished = Signal()
        result = Signal(bool, str, dict)
        error = Signal(tuple)

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.signal = self.WorkerSignal()
        self.conn = None
        self.cursor = None
        self.arxml_files = []
        self.build = True

    @Slot()
    def run(self):
        """
        run is a Slot that is called when the worker thread is started
        """
        # noinspection PyBroadException
        try:
            if not check_pver_is_built(self.path):
                self.build = False
                logger.error("=> PVER is not built")
            if not self.is_supported():
                logger.error("MDGB Version is incompatibility")
                self.build = False
            result = self.load_pver()
        except Exception as e:
            # traceback.print_exc()
            exec_type, value = sys.exc_info()[:2]
            # noinspection PyUnresolvedReferences
            self.signal.error.emit(exec_type, value, traceback.format_exc())
        else:
            # noinspection PyUnresolvedReferences
            self.signal.result.emit(self.build, self.path, result)
            # noinspection PyUnresolvedReferences
        finally:
            # noinspection PyUnresolvedReferences
            self.signal.finished.emit()

    def is_supported(self) -> bool:
        """
        Check if the pver is supported (Currently only MDGB)
        """
        with open(os.path.join(self.path, "medc17_tools.ini"), "r", encoding='utf-8') as file:
            # noinspection PyTypeChecker,PydanticTypeChecker
            medc17_ini = dict(line.strip().split('=') for line in file.readlines() if len(line.strip().split('=')) == 2)

        if medc17_ini["PRJ_BUILD_NAME"] != "mdgb":
            return False
        return True

    def load_pver(self):
        """
        Connect and fetch SQLite data
        """
        logger.critical("PVER Loading.")
        self.conn = sqlite3.connect(str(pathlib.Path(self.path).joinpath("workunit.lws.cc.db3")))
        self.cursor = self.conn.cursor()
        result = self.fetch()
        self.cursor.close()
        self.conn.close()

        logger.critical("Pver Loaded.")
        return result

    def fetch(self, current_id=1):
        """
        Fetch all artifacts and their children using recursion
        """
        children = self.get_children(current_id)
        children_dict = {}
        for child in children:
            child = child[0]
            cls, name, variant, Upd, file_name, path, ext, size, crc, a_paths = self.get_detail(child)
            children_dict[name] = {"cls": cls, "variant": variant, "Upd": Upd, "f_name": file_name,
                                   "path": path, "ext": ext, "size": str(size),
                                   "crc": crc, "arxmls": a_paths}
            children_dict[name]["children"] = self.fetch(child)
        return children_dict

    def get_children(self, parent_id):
        """
        Get children of an artifact
        :param parent_id: id of the parent artifact
        """
        self.cursor.execute(
            "SELECT r.ChildId "
            "FROM Relations as r, Artifacts as a "
            "WHERE r.ChildId = a.Id and r.ParentId =? "
            "ORDER BY a.Class, a.Name",
            [parent_id])

        children = self.cursor.fetchall()
        return children

    def get_detail(self, artifact_id):
        """
        Get detail of an artifact
        :param artifact_id: id of the artifact
        """

        self.cursor.execute(
            "SELECT a.Class, a.Name, a.Variant, a.Upd, f.Name, "
            "f.FilePath, f.Extension,f.FileSize, f.CRC "
            "FROM Artifacts as a "
            "LEFT OUTER JOIN Files as f "
            "ON a.Id = f.ArtifactId "
            "WHERE a.Id=? ",
            [artifact_id])
        cls, name, variant, Upd, file_name, path, ext, size, crc = self.cursor.fetchall()[0]
        if file_name and ext:
            file_name = "{}.{}".format(file_name, ext)
            path = os.path.join(path, file_name)
            if rtegen.is_required(cls, ext):
                self.arxml_files.append(path)
        return cls, name, variant, Upd, file_name, path, ext, size, crc, self.arxml_files


class BuildToolWorker(QRunnable):
    """
    BuildToolWorker is QRunnable that build tools command to run
    """

    class WorkerSignals(QObject):
        """
        Defines the signals available from a running worker thread.

        Supported signals are:
        finished
            No data
        error
            tuple (exctype, value, traceback.format_exc() )
        result
            object data returned from processing, anything
        """
        finished = Signal()
        error = Signal(tuple)
        result = Signal(object)

    def __init__(self, function, *args, **kwargs):
        super().__init__()

        # Store constructor arguments (re-used for processing)
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = self.WorkerSignals()

    @Slot()
    def run(self):
        """
        Initialise the runner function with passed args, kwargs.
        """

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.function(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done


class PVERTreeWidget(QGroupBox):
    """
    A tree widget that displays the contents of a PVER.
    """
    PVER_TREE_WIDTH = 400

    class QSignal(QObject):
        """
        Signal class for PVER tree widget
        """
        loaded = Signal(str)

    def __init__(self):
        super().__init__()
        self.setTitle("PVER Tree")
        self.setFixedWidth(self.PVER_TREE_WIDTH)

        self.base_path = None
        self.selected_rtegen_artifacts = []
        self.selected_btc_artifacts = []
        self.selected_damos_artifacts = []
        self.thread_pool = QThreadPool().globalInstance()
        self.arxml_paths = []

        self.pver_tree = QTreeWidget()
        self.pver_tree.setHeaderLabels(["Name", "Class", "Variant"])
        self.pver_tree.setColumnWidth(0, int(self.PVER_TREE_WIDTH * 3 / 6))
        self.pver_tree.setColumnWidth(1, int(self.PVER_TREE_WIDTH * 1 / 6))
        self.pver_tree.setColumnWidth(2, int(self.PVER_TREE_WIDTH * 1 / 6))


        self.pver_tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.pver_tree.itemClicked.connect(self.on_item_clicked)
        self.pver_tree.itemChanged.connect(self.on_item_changed)
        self.tree_items = []
        self.allow_change = True

        self.signal = self.QSignal()
        self.threadpool = QThreadPool()

        self.browse_button = QPushButton()
        self.browse_button.setFixedWidth(100)
        self.browse_button.setText("Browse PVER")
        self.browse_button.clicked.connect(self.on_browse)
        self.browse_dialog = None

        self.build_button = QPushButton()
        self.build_button.setFixedWidth(100)
        self.build_button.setText("Build")
        self.build_button.clicked.connect(self.on_build_pver)
        self.build_button.setDisabled(True)

        self.pressed = False
        self.check_button = QPushButton()
        self.check_button.setFixedWidth(70)
        self.check_button.setText("Check")
        self.check_button.clicked.connect(lambda: self.trigger_tealeaves_check(pver_root = self.base_path, pressed=True))
        self.check_button.setDisabled(True)

        self.build_progress = QProgressBar()
        self.build_progress.setVisible(False)
        self.build_progress.setValue(0)
        self.build_progress.setRange(0, 100)
        self.build_progress.setAlignment(Qt.AlignCenter)
        self.build_progress.setTextVisible(True)

        self.stop_button = QPushButton()
        self.stop_button.setFixedWidth(100)
        self.stop_button.setVisible(False)
        self.stop_button.setText("Stop")
        self.stop_button.clicked.connect(self.stop_process)
        self.stop_button.setDisabled(True)

        self.process_running = False

        self.file_check = []
        self.mandatory_paths = []
        self.process_list = []

        self.read_data = {}

        layout = QHBoxLayout()
        layout.addWidget(self.stop_button)
        layout.addWidget(self.build_progress)
        layout.setAlignment(Qt.AlignCenter)
        self.widget_progress = QWidget()
        self.widget_progress.setLayout(layout)

        self.bct_required_check = False
        self.damos_required_check = False
        self.tealeaves_run = False
        self.have_errors = False
        self.progress_count = 0
        self.total_progress = 0
        self.total_command = []
        self.command_list = {}

        self.rtegen_file_paths = {
            "modified_path": [],
            "arxml_path": []
        }
        self.bct_artifacts = {
            "modified_path": [],
            "bamf_path": [],
            "arxml_path": [],
            "cfg_path": [],
            "pm_path": []
        }
        self.damos_file_paths = {
            "modified_path": [],
            "pavast_path": []
        }

        tree_layout = QGridLayout(self)
        tree_layout.addWidget(self.browse_button, 0, 0, 1, 1)
        tree_layout.addWidget(self.build_button, 0, 1, 1, 1)
        tree_layout.addWidget(self.check_button, 0, 3, 2, 1)
        tree_layout.addWidget(self.pver_tree, 2, 0, 1, 4)

    @profiling()
    def build_tree(self, permit, data):
        """
        Clear the pver tree then build the tree widget from the data.
        """
        self.tree_items = []
        self.allow_change = True
        self.pver_tree.blockSignals(True)
        self.pver_tree.clear()
        self.tealeaves_run = False
        self.selected_rtegen_artifacts.clear()
        self.selected_btc_artifacts.clear()
        self.selected_damos_artifacts.clear()
        self.build(self.pver_tree, data)
        self.pver_tree.blockSignals(False)
        self.build_button.setDisabled(False)
        self.check_button.setDisabled(False)
        self.setTitle(f"PVER TREE: {self.base_path.split('/')[-1]}")
        if not permit:
            self.tree_set_disable()

    # "Name", "cls", "variant",  "f_name", "path", "ext", "size", "crc"
    def build(self, parent=None, data=None, check_state=Qt.Unchecked):
        """
        Build the tree widget from the data using recursion
        """
        class_name =  ["BC", "MC", "FC", "GC", "BX", "MX", "GX",
                      "FX", "CEL", "CC", "GENC", "FSY", "PJT"]

        for key, value in data.items():
            self.arxml_paths = value["arxmls"]
            if value["Upd"] != 'TEMPORARY':
                is_checked = check_state
                widget = QTreeWidgetItem(parent,
                                         [key,value["cls"],value["variant"],
                                          value["f_name"], value["path"], value["ext"],
                                          value["size"], value["crc"]])
                widget.setCheckState(0, is_checked)
                # check if the artifact should be hidden
                is_showed = False
                for name in class_name:
                    if name in value["cls"]:
                        is_showed = True
                        break

                if not is_showed:
                    widget.setHidden(True)
                # get required artifacts
                if 'SWAdp' in key or value["cls"] in ['CEL', 'GENC']:
                    widget.setCheckState(0, Qt.Checked)
                    widget.setToolTip(0, "This artifact is required")
                    is_checked = Qt.Checked
                    widget.setDisabled(True)
                    self.set_parent_state(widget)
                if "children" in value:
                    self.build(widget, value["children"], is_checked)
                self.tree_items.append(widget)
    def on_browse(self):
        """
        Open a file dialog to browse for a PVER.
        """
        self.browse_dialog = BrowseDialog()
        # noinspection PyUnresolvedReferences
        self.browse_dialog.signal.fetch_tools.connect(self.signal.loaded)
        # noinspection PyUnresolvedReferences
        self.browse_dialog.signal.fetch_tools.connect(self.set_path)
        # noinspection PyUnresolvedReferences
        self.browse_dialog.signal.build_pver.connect(self.build_tree)


    def set_path(self, path):
        """
        Set the base path of the PVER.
        """
        self.base_path = path

    def set_parent_state(self, current_item):
        """
        Set the state of the parent of the item.
        """
        parent = current_item.parent()
        if parent:
            states = []
            for i in range(parent.childCount()):
                child = parent.child(i)
                if not child.isHidden():
                    state = parent.child(i).checkState(0)
                    states.append(state)
            if Qt.Checked not in states and Qt.PartiallyChecked not in states:
                parent.setCheckState(0, Qt.Unchecked)
            elif Qt.Unchecked not in states and Qt.PartiallyChecked not in states:
                parent.setCheckState(0, Qt.Checked)
            else:
                parent.setCheckState(0, Qt.PartiallyChecked)
            self.set_parent_state(parent)

    def on_item_clicked(self, item):
        """
        Handle the user clicking on an item in the tree.
        """
        self.set_parent_state(item)

    # "Name", "cls", "variant",  "f_name", "path", "ext", "size", "crc"
    def on_item_changed(self, item):
        """
        Handle the user changing the state of an item in the tree.
        """
        if self.allow_change:
            # Set child item's state if current item is check/unchecked
            if item.checkState(0) != Qt.PartiallyChecked and item.childCount() > 0:
                for j in range(item.childCount()):
                    item.child(j).setCheckState(0, item.checkState(0))

            # Get required files for build tools
            if item.checkState(0) == Qt.Checked:
                if rtegen.is_required(item.text(1), item.text(5)):
                    self.selected_rtegen_artifacts.append(item)

                if bct.is_required(item.text(1), item.text(5)):
                    if item.text(1) == "BC":
                        self.selected_btc_artifacts.append(item)
                    self.selected_btc_artifacts.append(item)

                if damos.is_required(item.text(1), item.text(3)):
                    self.selected_damos_artifacts.append(item)
            # Remove files from build tools if not check
            else:
                if rtegen.is_required(item.text(1), item.text(5)):
                    self.selected_rtegen_artifacts.remove(item)

                if damos.is_required(item.text(1), item.text(3)):
                    self.selected_damos_artifacts.remove(item)
                    self.damos_file_paths["modified_path"].clear()

                if bct.is_required(item.text(1), item.text(5)):
                    if item.text(1) == "BC":
                        self.selected_btc_artifacts.remove(item)
                    self.selected_btc_artifacts.remove(item)

    def tree_set_disable(self):
        self.allow_change = False
        self.build_button.setDisabled(True)
        self.check_button.setDisabled(True)
        if self.tree_items:
            for item in self.tree_items:
                item.setDisabled(True)

    def tree_set_enable(self):
        self.build_button.setEnabled(True)
        self.check_button.setEnabled(True)
        if self.tree_items:
            for item in self.tree_items:
                item.setDisabled(False)
        self.allow_change = True

    def stop_process(self):
        """
        Stopping process and threading run inside the tool function
        """
        self.process_running = False
        self.build_progress.setFormat("Canceling build process...")
        logger.warning("Building process being stopped")
        logger.debug("-"*200+'\n')
        self.total_progress = 0
        self.stop_button.setText('stopping')
        self.stop_button.setDisabled(True)
        self.build_button.setEnabled(True)
        for process in self.process_list:
            if process:
                process.terminate()
                try:
                    parent = psutil.Process(process.processId())
                    children = parent.children(recursive=True)
                    for child in children:
                        child.kill()
                    process.kill()
                except:
                    pass
        self.process_list.clear()
        for thread in self.threadpool.children():
            thread.disconnect()
        self.threadpool.clear()
        self.stop_button.setVisible(False)
        self.build_progress.setVisible(False)
        if not self.allow_change:
            self.tree_set_enable()

    @profiling()
    def on_build_pver(self):
        """
        Build the PVER.
        """
        self.total_command.clear()
        self.command_list.clear()
        self.mandatory_paths.clear()

        def get_bamf_file(path):
            """
            get all the .bamf in current working PVER directory
            """
            for root, dirs, files in os.walk(os.path.dirname(path)):
                for file in files:
                    check_file = os.path.join(root, file).replace("\\", "/")
                    if '.bamf' in check_file:
                        return check_file

        def get_pm_files(path):
            """
            get all the .pm in current working PVER directory
            """
            list_of_files = []
            files = glob.glob(path + '/**/*.pm', recursive=True)
            for file in files:
                list_of_files.append(file.replace('\\', '/'))
            return list_of_files

        def get_pavast_files(path):
            """
            get all the *_pavast.xml in current working PVER directory
            """
            list_of_files = []
            mandatory_paths = []
            files = glob.glob(path + '/**/*_pavast.xml', recursive=True)
            for file in files:
                format_file = file.replace('\\', '/').split(self.base_path)[1]
                name = format_file.split('/', 1)[1]
                list_of_files.append(name)
                if 'CEL' in name.split('/')[0] or 'GENC' in name.split('/')[0]:
                    mandatory_paths.append(name)
            return mandatory_paths, list_of_files

        def get_cfg_paths():
            """
            get buildframework.cfg and buildframework-roles.cfg in current working PVER directory
            """
            cfg_path = '.buildframework/default/persistence/'
            path = os.path.join(self.base_path, cfg_path).replace("\\", "/")
            list_of_files = [files for files in os.listdir(path) if '.cfg' in files]
            return [os.path.join(path, file) for file in list_of_files]

        def check_file(file_path, size, crc):
            """
            Check if the file path is valid.
            """
            if not os.path.exists(file_path):
                logger.error(f"File path does not exist: {file_path}")
                button = QMessageBox.warning(self, "File path does not exist",
                                             "File path does not exist: {}, \n "
                                             "Is it new file?".format(file_path),
                                             QMessageBox.Yes | QMessageBox.Ignore | QMessageBox.Cancel)
                if button == QMessageBox.Cancel:
                    raise FileNotFoundError(f"File path does not exist: {file_path}")

                elif button == QMessageBox.Ignore:
                    logger.warning(f"Ignoring file: {file_path}")
                    return False
                elif button == QMessageBox.Yes:
                    logger.debug(f"Add file to build: {file_path} (not found in db3)")
                    return True

            if is_modified(file_path, size, crc):
                return True

            return False

        # Check if the selected items was modified
        logger.debug("Checking if the selected items was modified")
        try:
            # Query all the arxml paths inside the PVER path
            for item in self.arxml_paths:
                self.rtegen_file_paths["arxml_path"]. \
                    append(os.path.join(self.base_path, item).replace("\\", "/"))

            for item in self.selected_rtegen_artifacts:
                path = os.path.join(self.base_path, item.text(4)).replace("\\", "/")
                if check_file(path, item.text(6), item.text(7)):
                    self.rtegen_file_paths["modified_path"].append(
                        os.path.join(self.base_path, item.text(4)).replace("\\", "/"))

            for item in self.selected_btc_artifacts:
                path = os.path.join(self.base_path, item.text(4)).replace("\\", "/")
                if check_file(path, item.text(6), item.text(7)):

                    if (item.text(1).startswith('CONF') or item.text(1).startswith('XD')) \
                            and (item.text(5) == 'xml' or item.text(5) == 'arxml'):
                        self.bct_artifacts["arxml_path"].append(path)
                        get_path = get_bamf_file(path)
                        self.bct_artifacts["modified_path"].append(path)
                        if get_path is not None and get_path not in self.bct_artifacts["bamf_path"]:
                            self.bct_artifacts["modified_path"].append(get_path)

                    if (item.text(1).startswith('CONF') or item.text(1) == 'BAMF') and item.text(
                            5) != 'xml' and item.text(5) != 'arxml':  # look for all bamf files
                        get_path = get_bamf_file(path)
                        if get_path is not None \
                                and get_path not in self.bct_artifacts["bamf_path"]:
                            self.bct_artifacts["bamf_path"].append(get_path)
                            self.bct_artifacts["modified_path"].append(get_path)

            for item in self.selected_damos_artifacts:
                self.damos_file_paths["modified_path"].append(item.text(4).replace("\\", "/"))

            # add the buildframework.cfg, and buildframework-roles.cfg
            self.bct_artifacts["cfg_path"].extend(get_cfg_paths())
            self.bct_artifacts["pm_path"].extend(get_pm_files(self.base_path))
            self.mandatory_paths, all_pavast = get_pavast_files(self.base_path)
            self.damos_file_paths["pavast_path"].extend(all_pavast)
            self.damos_file_paths["modified_path"].extend(self.mandatory_paths)

            self.file_check.extend(self.damos_file_paths["pavast_path"])
        except FileNotFoundError as exception:
            logger.error(exception)
            logger.error("Cancel build pver")
            return

        # Build phase
        self.build_action()

    def initialize_progress_bar(self, name=''):
        """
        Initialize the progress bar
        """
        self.build_progress.setVisible(True)
        self.build_progress.setStyleSheet("color: black;")
        self.build_progress.setFormat(f'Initializing {name}....')
        self.build_progress.setValue(0)
        self.stop_button.setVisible(True)
        self.stop_button.setEnabled(True)
        self.stop_button.setText('stop')
        self.build_button.setEnabled(False)

    def started_format(self, name):
        """
        format string to started process
        """
        self.build_progress.setFormat(f"Enabling tool {name}")
        logger.debug('\n'+'-' * 90 + f'BULDING TOOL: {name}' + '-' * 85)

    def trigger_bct(self):
        """
        Preparing to run BCT
        """
        self.process_running = True
        self.progress_run_bct()

    def progress_run_bct(self):
        """
        Generate appropriate BCT command and run it
        """
        bct_command, env = bct.get_command(self.bct_artifacts["modified_path"],
                                           self.bct_artifacts["bamf_path"],
                                           self.bct_artifacts["arxml_path"],
                                           self.bct_artifacts["cfg_path"],
                                           self.bct_artifacts["pm_path"])
        if bct_command is not None:
            logger.debug('BCT stage ready to run.')
        else:
            logger.critical('Aborting BCT tool run...')
            self.initialize_progress_bar(name='RTEGEN')
            self.trigger_rtegen()
            return

        new_logger = setup_logger('bct', env)
        self.initialize_progress_bar(name='BCT')
        process = QProcess()

        def handle_stdout():
            stdout = bytes(process.readAllStandardOutput()).decode("utf8", errors='ignore').strip()
            if stdout:
                logger.info(f'bct :: {stdout})')
                new_logger.info(stdout)
                self.build_progress.setValue(self.build_progress.value() + 1)
                current_progress = self.build_progress.value()
                if current_progress < 98:
                    self.build_progress.setFormat(f" Building BCT tool: {current_progress}% ")
                    self.build_progress.setStyleSheet("color: black;")
                    value = round(math.log(100 - current_progress, 2) * 2)
                    self.build_progress.setValue(current_progress + value)

        def handle_stderr():
            stderr = bytes(process.readAllStandardError()).decode("utf8", errors='ignore').strip()
            if stderr:
                logger.error(f'bct :: {stderr})')
                new_logger.info(stderr)

        def process_finished():

            self.build_progress.setValue(self.build_progress.maximum())
            self.build_progress.setFormat(f" Building BCT tool: "
                                          f"{self.build_progress.value()}% completed")
            self.build_progress.setStyleSheet("color: black;")
            self.build_progress.setVisible(False)
            self.build_button.setEnabled(True)
            self.build_button.setText('Build')
            self.stop_button.setVisible(False)
            self.stop_button.setDisabled(True)
            if self.process_running:
                logger.debug('-' * 160)
                self.trigger_rtegen()

        process.started.connect(self.started_format('BCT'))
        process.setProcessChannelMode(QProcess.SeparateChannels)
        process.readyReadStandardOutput.connect(handle_stdout)
        process.readyReadStandardError.connect(handle_stderr)
        process.finished.connect(lambda: process_finished())
        process.setWorkingDirectory(os.path.normpath(env))
        process.startCommand(bct_command)
        self.process_list.append(process)

    def trigger_rtegen(self):
        """
        Preparing to run RTEGEN
        """
        self.progress_run_rtegen()


    def progress_run_rtegen(self):
        """
            Generate appropriate RTEGEN command and run it
        """
        rtegen_command, env = rtegen.get_command(self.rtegen_file_paths["modified_path"],
                                                 self.rtegen_file_paths["arxml_path"])
        if rtegen_command is not None:
            logger.debug('tools RTEGEN ready to run.')
        else:
            logger.critical('Aborting RTEGEN tool run...')
            self.initialize_progress_bar(name='DAMOS')
            self.initialize_damos()
            return

        new_logger = setup_logger('rtegen', env)
        self.initialize_progress_bar(name='RTEGEN')
        process = QProcess()

        def handle_stdout():
            stdout = bytes(process.readAllStandardOutput()).decode("utf8", errors='ignore').strip()
            if stdout:
                logger.info(f'rtegen :: {stdout})')
                new_logger.info(stdout)
                self.build_progress.setValue(self.build_progress.value() + 1)
                current_progress = self.build_progress.value()
                if current_progress < 98:
                    self.build_progress.setFormat(f" Building RTEGEN tool: {current_progress}% ")
                    self.build_progress.setStyleSheet("color: black;")
                    value = round(math.log(100 - current_progress, 2) * 2)
                    self.build_progress.setValue(current_progress + value)

        def handle_stderr():
            stderr = bytes(process.readAllStandardError()).decode("utf8", errors='ignore').strip()
            if stderr:
                logger.error(f'rtegen :: {stderr})')
                new_logger.info(stderr)

        def process_finished():
            self.build_progress.setValue(self.build_progress.maximum())
            self.build_progress.setFormat(f" Building RTEGEN tool: {self.build_progress.value()}% completed")
            self.build_progress.setStyleSheet("color: black;")
            self.build_progress.setVisible(False)
            self.build_button.setEnabled(True)
            self.build_button.setText('Build')
            self.stop_button.setVisible(False)
            self.stop_button.setDisabled(True)
            if self.process_running:
                logger.debug('-' * 160)
                self.initialize_progress_bar(name='DAMOS')
                self.initialize_damos()

        process.started.connect(self.started_format('RTEGEN'))
        process.setProcessChannelMode(QProcess.SeparateChannels)
        process.readyReadStandardOutput.connect(handle_stdout)
        process.readyReadStandardError.connect(handle_stderr)
        process.finished.connect(lambda: process_finished())
        process.setWorkingDirectory(os.path.normpath(env))
        process.startCommand(rtegen_command)
        self.process_list.append(process)

    def get_damos_command(self):
        """
        generating damos command
        """
        damos_command, env = damos.get_command(self.damos_file_paths["modified_path"],
                                               self.damos_file_paths["pavast_path"])
        if damos_command:
            logger.debug('tools DAMOS ready to run.')
            return 'damos', damos_command, env
        return 'damos', None, env

    def initialize_damos(self):
        """
        Initializing the damos process
        """
        self.total_progress = 0
        damos.signal.sync.emit(self.base_path)
        damos_worker = BuildToolWorker(self.get_damos_command)
        damos_worker.signals.result.connect(self.progress_run_damos)

        # Execute
        self.threadpool.start(damos_worker)

    def progress_run_damos(self, command_args):
        """
        running  tools cli
            name = command_args[0]
            command = command_args[1]
            env = command_args[2]
        """
        if command_args[1] is not None:
            new_logger = setup_logger(command_args[0].lower(), command_args[2])
            self.initialize_progress_bar(name='DAMOS')
            process = QProcess()

        def handle_stdout():
            stdout = bytes(process.readAllStandardOutput()).decode("utf8", errors='ignore').strip()
            if stdout:
                logger.info(f'{command_args[0]} :: {stdout}')
                new_logger.info(stdout)
                self.build_progress.setValue(self.build_progress.value() + 1)
                current_progress = self.build_progress.value()
                if current_progress < 98:
                    self.build_progress.setFormat(f" Building {command_args[0]} "
                                                  f"tool: {current_progress}% completed")
                    self.build_progress.setStyleSheet("color: black;")
                    value = round(math.log(100 - current_progress, 2) * 2)
                    self.build_progress.setValue(current_progress + value)

        def handle_stderr():
            stderr = bytes(process.readAllStandardError()).decode("utf8", errors='ignore').strip()
            if stderr:
                logger.error(f'{command_args[0]} :: {stderr}')
                new_logger.info(stderr)
        def process_finished():
            self.build_progress.setValue(self.build_progress.maximum())
            self.build_progress.setFormat(f" Building {command_args[0]} tool:"
                                          f" {self.build_progress.value()}% completed)")
            self.build_progress.setStyleSheet("color: black;")
            self.build_progress.setVisible(False)
            self.build_button.setEnabled(True)
            self.build_button.setText('Build')
            self.stop_button.setVisible(False)
            self.stop_button.setDisabled(True)
            self.process_running = False
            logger.debug('-' * 160)
            self.tree_set_enable()

        process.started.connect(self.started_format(command_args[0]))
        process.setProcessChannelMode(QProcess.SeparateChannels)
        process.readyReadStandardOutput.connect(handle_stdout)
        process.readyReadStandardError.connect(handle_stderr)
        process.finished.connect(lambda: process_finished())
        process.setWorkingDirectory(os.path.normpath(command_args[2]))
        process.startCommand(command_args[1])
        self.process_list.append(process)

    def trigger_tealeaves_check(self, pver_root, version="latest",pressed =False) -> (bool, set):
        """
        Trigger tealeaves and return tuple with boolean result
        and a set containing all files having errors
        """
        self.pressed = pressed
        def get_tealeaves_exe_path() -> str:
            tealeaves_path = os.path.join("C:\\toolbase\\tealeaves")
            if version == "latest":
                all_versions = [os.path.join(tealeaves_path, v)
                                for v in os.listdir(tealeaves_path)]
                return os.path.join(max(all_versions, key=os.path.getmtime), "tealeaves.exe")

            return os.path.join(tealeaves_path, version, "tealeaves.exe")

        def get_tealeaves_result():
            result = set()
            tealeaves_folder = os.path.join(self.base_path, "_tealeaves")
            if not os.path.isdir(tealeaves_folder):
                logger.error("_tealeaves folder was not generated")
                return result

            with open(tealeaves_folder + "/tealeaves.log", "r", encoding='utf-8') as file:
                errors = file.readlines()
            try:
                idx = errors.index("list of errors:\n")
            except ValueError:
                logger.debug("no abort error for this PVER")
                self.build_progress.setVisible(False)
                self.stop_button.setVisible(False)
                self.stop_button.setDisabled(True)
                return result

            # this should contain all abort error
            errors = errors[idx + 2:]
            errors = [e for e in errors if ".xml" in e]

            for error in errors:
                find = re.search(r"\w+\.xml", error)
                if find:
                    found = find.group(0)
                    result.add(found)
            logger.debug(f'tealeaves :: {result}')
            return result

        def handle_stdout():
            stdout = bytes(process.readAllStandardOutput()).decode("utf-8", errors='ignore').strip()
            if stdout:
                logger.info(f" tealeaves :: {stdout}")

                self.build_progress.setValue(self.build_progress.value() + 12)
                current_progress = self.build_progress.value()
                if current_progress < 98:
                    self.build_progress.setFormat(f" Tealeaves progress: {current_progress}%")
                    self.build_progress.setStyleSheet("color: black;")
                    value = round(math.log(100 - current_progress, 2) * 2)
                    self.build_progress.setValue(current_progress + value)

        def handle_stderr():
            stderr = bytes(process.readAllStandardError()).decode("utf-8", errors='ignore').strip()
            if stderr:
                logger.error(f" tealeaves :: {stderr}")

        def process_finished():
            self.have_errors = False
            self.tealeaves_run = True
            self.check_button.setEnabled(True)
            self.build_progress.setValue(100)
            self.build_progress.setStyleSheet("color: black;")
            self.build_button.setEnabled(True)
            self.build_button.setText('Build')
            self.build_progress.setVisible(False)
            self.stop_button.setVisible(False)
            self.stop_button.setDisabled(True)

            file_having_error = get_tealeaves_result()

            for file in self.file_check:
                if file.split('/')[-1] in file_having_error:
                    self.have_errors = True
                    msg = QMessageBox()
                    msg.setWindowTitle("Error Detected!")
                    msg.setText("Tealeaves detected some files are having error.\n"
                                "Build process cannot be completed. Please consider to repair the PVER before run!")
                    msg.setIcon(QMessageBox.Information)
                    cancel_button = msg.addButton(QMessageBox.Cancel)
                    msg.exec()
                    self.build_button.setDisabled(True)
                    self.check_button.setDisabled(True)
                    logger.error("Build process canceled.")
                    break

            if not self.have_errors:
                if not self.pressed:
                    self.initialize_progress_bar(name='BCT')
                    self.trigger_bct()
                return

            self.pressed = False

        self.check_button.setEnabled(False)
        tealeaves_exe = get_tealeaves_exe_path()

        self.initialize_progress_bar(name='TEALEAVES')
        self.stop_button.setVisible(True)
        process = QProcess()
        command = f"{tealeaves_exe} tealeaves --root={pver_root} --solve --solve-no-request"

        process.started.connect(self.started_format(name="TEALEAVES"))
        process.setProcessChannelMode(QProcess.SeparateChannels)
        process.readyReadStandardOutput.connect(handle_stdout)
        process.readyReadStandardError.connect(handle_stderr)
        process.finished.connect(lambda: process_finished())
        process.setWorkingDirectory(pver_root)
        process.startCommand(command)
        self.process_list.append(process)

    def check_tealeaves_exist(self) -> bool:
        tealeaves_path = os.path.join("C:\\toolbase\\tealeaves")

        if not os.path.isdir(tealeaves_path):
            msg = QMessageBox(self)
            msg.setWindowTitle("Tealeaves error")
            msg.setText("Tealeaves was not installed in this machine.\n"
                        "Please install it via Toolbase.")
            msg.setIcon(QMessageBox.Warning)
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
            msg.exec()
            return False

        return True

    def check_tealeaves_already_run(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Tealeaves info")
        msg.setText("Tealeaves has already run on this PVER.\n"
                    "Would you like to run it again?")
        msg.setIcon(QMessageBox.Information)
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        msg.exec()
        if msg.clickedButton() == QMessageBox.Ok:
            self.trigger_tealeaves_check(pver_root=self.base_path)
            return
        else:
            self.initialize_progress_bar(name='BCT')
            self.trigger_bct()
            return

    def build_action(self):
        """
        Start the build action.
        Firstly: it will check and trigger tealeaves. if the tealeaves have run before,
                 trigger the message to notify the user.
        Secondly it will trigger BCT.
        Thirdly will be RTEGEN (called in BCT step)
        Finally will be DAMOS (called in RTEGEN step)
        """
        self.tree_set_disable()
        if not self.check_tealeaves_exist():
            return
        else:
            if not self.tealeaves_run:
                self.trigger_tealeaves_check(pver_root=self.base_path)
            else:
                self.check_tealeaves_already_run()
