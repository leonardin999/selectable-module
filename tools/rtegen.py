"""
TODO: Write docstring
"""
import os.path
import re

from lxml import etree
from PySide6.QtCore import QObject, Signal
from utilities.log import get_logger

logger = get_logger(__name__)


class SyncSignal(QObject):
    """
    SyncSignal is a QObject that allows the MainWindow to emit signals
    """
    sync = Signal(str)
    logger.debug("SyncSignal created")


PATH = ""
WORKING_PATH = ''


def env_sync(path):
    """
    Sync the Working environemt path.
    """
    global WORKING_PATH
    WORKING_PATH = path


def sync(path):
    """
    Sync the Rtegen path.
    """
    global PATH
    PATH = path


signal = SyncSignal()
rtegen_signal = SyncSignal()
# noinspection PyUnresolvedReferences
signal.sync.connect(sync)
rtegen_signal.sync.connect(env_sync)


def is_required(item_class, item_extension):
    """
    Check if the item is required for the Rtegen.
    """
    class_check = ["CONF", "PJTCOREFS", "PJTECUCVPRO", "PJTMCSIFDATA",
                   "DOCMISC", "PJTRTEGENMCS", "PRJARFWD",
                   "PJTMCSUPP", "TDATA-EOC"]
    if "CONFSY-AR" in item_class and item_extension == "arxml":
        return True
    if not any(x in item_class for x in class_check) and item_extension == "arxml":
        return True
    return False


def get_contract_argument(path):
    """
    Get the contract paths from the arxml file.
    """
    result = []
    component_types = ["APPLICATION-SW-COMPONENT-TYPE", "ATOMIC-SW-COMPONENT-TYPE",
                       "COMPLEX-DEVICE-DRIVER-SW-COMPONENT-TYPE", "ECU-ABSTRACTION-SW-COMPONENT-TYPE",
                       "NV-BLOCK-SW-COMPONENT-TYPE", "SENSOR-ACTUATOR-SW-COMPONENT-TYPE",
                       "SERVICE-PROXY-SW-COMPONENT-TYPE", "SERVICE-SW-COMPONENT-TYPE"]
    with open(path, 'r', encoding='utf-8') as file:
        content = file.read()

    content = re.sub('\\sxmlns="[^"]+"', '', content, count=1)
    content = re.sub('\\sencoding="[^"]+"', '', content, count=1)
    content = re.sub('\\sencoding=\'[^"]+\'', '', content, count=1)
    root_node = etree.fromstring(content)

    for component_type in component_types:
        # search if component type is in the file
        elements = root_node.findall(f".//{component_type}")
        if len(elements)>0:
            for element in elements:
                if element.find('.//{*}SHORT-NAME') is not None:
                    arg_path = [""]
                    for ancestor in element.xpath('ancestor-or-self::*[.//SHORT-NAME]'):
                        children = ancestor.getchildren()
                        for child in children:
                            # Only get short name if it is of actual ancestor of the SWC.
                            if child.tag == "SHORT-NAME":
                                arg_path.append(child.text)
                                if ancestor.tag == component_type:
                                    result.append(str.join("/", arg_path))
    return result


def get_command(paths, arxml_path) -> (str, str):
    """
        Return RTEGEN command, and its working path
    """
    storing_path = os.path.join(WORKING_PATH, '_smb/rtegen')
    all_arxml_file = os.path.join(WORKING_PATH, "_smb/SMB_Rtegen_all_files.lst")
    env = os.path.join(PATH, "bin")
    saving_file = (all_arxml_file).replace('\\', '/')

    arguments = []
    if not os.path.isdir(storing_path):
        os.makedirs(storing_path)

    for path in paths:
        arg = get_contract_argument(path)
        if arg not in arguments:
            arguments.extend(arg)
            logger.info(f"rtegen :: Contract arguments: {arg}")

    if os.path.exists(all_arxml_file):
        with open(all_arxml_file, 'w', encoding='utf-8') as file:
            file.write("")
        file.close()

    with open(all_arxml_file, 'w', encoding='utf-8') as file:
        file.write("; Input Files \n")
        for path in arxml_path:
            file.write(f"\"{path}\"\n")
        file.close()

    if len(arguments) > 0:
        rtegen_commands = 'cmd call /q /c call ' \
                            + os.path.join(env, 'RTEGen.exe') +' -c '.join(arguments) \
                            + ' -o [*.*]' + f"\"{os.path.normpath(storing_path)}\"" \
                            + ' --samples=swc -f ' + f"\"{os.path.normpath(saving_file)}\""

        return rtegen_commands, WORKING_PATH

    return None, WORKING_PATH
