"""
TODO:
"""
import os
import re
from typing import List
from collections import deque
from lxml import etree
from PySide6.QtCore import QObject, Signal
from utilities.log import get_logger

logger = get_logger(__name__)


class SyncSignal(QObject):
    """
    DialogSignal is a  QObject that allow the BrowseDialog to emit signals
    """
    sync = Signal(str)
    logger.debug("SyncSignal created")


PATH = ''
WORKING_PATH = ''
SAVING_PATH = ''


def env_sync(path):
    """
    Sync the Working environemt path.
    """
    global WORKING_PATH
    WORKING_PATH = path


def sync(path):
    """
    Sync the BTC tool run path
    """
    global PATH
    PATH = path


def saving_sync(path):
    """
    Sync the saving output path
    """
    global SAVING_PATH
    SAVING_PATH = path


signal = SyncSignal()
signal.sync.connect(sync)

bct_signal = SyncSignal()
bct_signal.sync.connect(env_sync)

bct_saving_signal = SyncSignal()
bct_saving_signal.sync.connect(saving_sync)


def is_required(item_class: str, item_extension: str):
    """
    Check if the item is required for the BCT.
    """
    check_list = [['BAMF', 'bamf'], ['CONFCHK', 'chk'], ['CONFDTD', 'dtd'], ['CONFEXPDTD', 'dtd'],
                  ['CONFGEN', 'xpt'], ['CONFLIB', 'ext'], ['CONFPATH', '*'], ['CONFPROC', 'pm'],
                  ['CONFPROPS', 'properties'], ['CONFRULES', 'xml'], ['CONFRULES', 'arxml'],
                  ['CONFTOOL', '*'], ['CONFTPLCDA', '*'], ['CONFTPLHDR', '*'], ['CONFTPLMSC', '*'],
                  ['CONFTPLSRC', '*'], ['CONFTPLTDA', '*'], ['CONFTPLXML', '*'], ['CONFWF', '*']]

    for check_class, check_extension in check_list:
        if check_class == item_class:
            if check_extension == '*' or check_extension == item_extension:
                return True
    return False


def is_runable(path):
    """
    Check version of EcuWork to get the tool command
    """
    check_path = os.path.join(path, r'_tbmeta\dependencies.ini')
    if not os.path.isfile(check_path):
        logger.error("No dependencies.ini found")
        return
    with open(check_path, "r", encoding="utf-8") as file:
        for line in file:
            if line.startswith('ecl_bct'):
                return ' -bct rebuild -l '
    return ' -bsw rebuild -l '


def get_all_bfw_actions(root, action):
    """
    take all the actions existed in the buildframework.cfg file (bfw)
    """
    original_action = [actions.attrib['id']
                       for actions in root.findall('.//{*}' + action)]
    return original_action


def get_pm_actions(path, pm_paths):
    """
    Check inside the buildframework-roles.cfg to list all [.pm] files
    """
    tree = etree.parse(path)
    root = tree.getroot()
    pm_files = {}
    pm_actions = {}

    for pm_path in pm_paths:
        pm_files[pm_path.split('/')[-1]] = pm_path

    for ecu_out_pm in root.findall('.//{*}property/[@value="pm"]...'):
        if (ecu_out_pm.find('.//{*}property/[@name="filter"]')) is not None:
            pm_actions[ecu_out_pm.find('./{*}property/[@name="filter"]')
                           .attrib['value'] + '.pm'] = \
                ecu_out_pm.find('./{*}description').text.split("'")[1]
    return pm_files, pm_actions


def get_cfg_actions(cfg_path, bamf_actions: List, pm_paths: List) -> List:
    """
    Recursive function to get all the actions after parsing .bamf files:
    parameters:
        cfg_path : including buildframework.cfg and buildframework-roles.cfg type of files
        bamf_actions: all the actions have stored from bamf files
        pm_paths: all the path have stored from PVER directory`
    """
    global BFW_ACTIONS
    global INPUT_LIST
    global OUTPUT_LIST
    global PREDECESSOR_LIST

    for path in cfg_path:
        if 'buildframework.cfg' in path:
            tree = etree.parse(path)
            root = tree.getroot()
            if root.tag.endswith('buildConfiguration'):
                action = 'actionDefinition'
                input_tag = 'actionInput'
                output_tag = 'actionOutput'
                io_mapping_tag = 'role'
                io_identify_tag = 'id'
                pred_attrib = 'id'
            else:
                action = 'action'
                input_tag = 'input'
                output_tag = 'output'
                io_mapping_tag = 'IOMapping'
                io_identify_tag = 'roleId'
                pred_attrib = 'name'
        else:
            pm_files, pm_actions = get_pm_actions(path, pm_paths)
    BFW_ACTIONS = get_all_bfw_actions(root, action)  # all the actions of the bfw are taken in order
    bamf_actions.sort(key=lambda i: BFW_ACTIONS.index(i)
    if i in BFW_ACTIONS else len(BFW_ACTIONS) - 1)

    action_queue = deque()
    action_queue.extend(bamf_actions)

    action_result = set()
    action_result.update(bamf_actions)

    INPUT_LIST = {}  # all the dependant actions type: [ecu_out_...]
    OUTPUT_LIST = {}  # actions that creates a dependant action [output_tags]
    PREDECESSOR_LIST = {}

    for input_action in root.findall('.//{*}' + action):
        INPUT_LIST[input_action.attrib['id']] = [inputs.attrib[io_identify_tag] for inputs in
                                                 input_action.findall(
                                                     './/{*}' + input_tag + '/[@type="ECUC_IN"]' + '/{*}' + io_mapping_tag)
                                                 if 'role_ecuc_out' in inputs.attrib[io_identify_tag]]

        for created_action in [outputs.attrib[io_identify_tag] for outputs in
                               input_action.findall('.//{*}' + output_tag + '/{*}' + io_mapping_tag) if
                               'role_ecuc_out' in outputs.attrib[io_identify_tag]]:
            OUTPUT_LIST[created_action] = input_action.attrib['id']

    for dependant_action in root.findall('.//{*}action'):
        PREDECESSOR_LIST[dependant_action.attrib['id']] = \
            [pred_action.attrib[pred_attrib] for pred_action in
             dependant_action.findall('.//{*}predecessor')]
    current_dependant_list = []
    current_pm_list = []
    while action_queue:
        action = action_queue.pop()
        # if action in action_result:
        #     continue
        dependence_actions = get_action_dependencies(action, current_dependant_list,
                                                     pm_files, pm_actions)
        # dependence_actions.extend(get_action_in_pm(action, current_pm_list))
        for each_action in dependence_actions:
            if each_action not in action_queue and each_action not in action_result:
                action_result.add(each_action)
                action_queue.append(each_action)
        current_dependant_list.clear()
        current_pm_list.clear()

    return action_result


def get_action_dependencies(action, dependencies, pm_files, pm_actions):
    """
    get all the dependencies of the action in .cfg files
    """
    global BFW_ACTIONS
    global INPUT_LIST
    global OUTPUT_LIST
    global PREDECESSOR_LIST

    if action in BFW_ACTIONS and action not in dependencies:
        for ecu_out in INPUT_LIST[action]:
            if (OUTPUT_LIST[ecu_out] not in dependencies):
                dependencies.append(OUTPUT_LIST[ecu_out])
                get_action_dependencies(OUTPUT_LIST[ecu_out], dependencies, pm_files, pm_actions)

        for predecessor in PREDECESSOR_LIST[action]:
            if (predecessor not in dependencies):
                dependencies.append(predecessor)
                get_action_dependencies(predecessor, dependencies, pm_files, pm_actions)
        dependencies.extend(get_action_in_pm(action, dependencies, pm_files, pm_actions))
    return dependencies


def get_action_in_pm(action, dependencies, pm_files, pm_actions):
    """
    get all the dependencies of the action in .pm file
    """
    for pm_file, pm_action in pm_actions.items():
        if action in pm_action and action not in dependencies:
            if str(action + '.pm') in pm_files:
                add_actions = pm_parse(pm_files[str(action + '.pm')])
                if add_actions is not None:
                    for add_action in add_actions:
                        if add_action in pm_action and action not in dependencies:
                            dependencies.append(add_action)
                            get_action_in_pm(add_action, dependencies, pm_files, pm_actions)
    return dependencies


def pm_parse(pm_path):
    """
    search line by line to take all the necessary action.
    """
    if (os.path.exists(pm_path)):
        all_lines = []
        pm_list = []
        with open(pm_path, 'r', encoding='utf-8') as file:
            all_lines += all_lines + (file.readlines())
            file.close()
        search_lines = [line.strip() for line in all_lines if
                        ("::" in line and "conf_process" not in line and ~line.startswith('#'))]
        for line in search_lines:
            line = line.split("::")[0].split()[-1]
            line = re.findall(r'\w+', line)
            if line[-1] not in pm_list:
                pm_list.append(line[-1])

            if '_process' in line[-1]:
                line[-1] = line[-1].replace('_process', '')
                if line[-1] not in pm_list:
                    pm_list.append(line[-1])
    return pm_list


def get_arguments_arxml(arxml_path):
    """
    Get the arguments of the arxml file if have in modified PVER.
    """
    arguments = []
    tree = etree.parse(arxml_path)
    root_node = tree.getroot()
    elements = root_node.findall(".//ECUC-MODULE-DEF")
    if len(elements) > 0:
        for element in elements:
            if element.find('.//{*}SHORT-NAME'):
                arg_path = []
                for ancestor in element.xpath('ancestor-or-self::*[.//SHORT-NAME]'):
                    children = ancestor.getchildren()
                    for child in children:
                        # Only get short name if it is of actual ancestor of the SWC.
                        if child.tag == "SHORT-NAME":
                            arg_path.append(child.text)
                            if ancestor.tag == "ECUC-MODULE-DEF":
                                arguments.append(str.join("/", arg_path))
    return arguments


def bamf_parser(modified_paths, bamf_paths, arxml_arguments) -> List:
    """
    parse inside the .bamf files to get action to run
    :param modified_paths: contain all the path of the current change in PVER
    :param bamf_paths: contains all the bamf files
    """
    action_to_run = []
    for fpath in modified_paths:
        fpath = fpath.replace('\\', '/')
        tree = etree.parse(fpath)
        root = tree.getroot()

        for action in root.iterfind(".//{*}BUILD-ACTION"):
            for artifacts in action.iterfind(
                    './{*}CREATED-DATAS/{*}BUILD-ACTION-IO-ELEMENT/{*}CATEGORY'):
                if artifacts.text == 'ARTIFACT':
                    if fpath in bamf_paths:
                        add_action = action.find('./{*}SHORT-NAME').text
                        if add_action not in action_to_run:
                            action_to_run.append(action.find('./{*}SHORT-NAME').text)
                    else:
                        for ecu_ref in action.iterfind(
                                './/{*}INPUT-DATAS/{*}BUILD-ACTION-IO-ELEMENT'):
                            for ecu_def in ecu_ref.iterfind('./{*}ECUC-DEFINITION-REF'):
                                if ecu_def.text in arxml_arguments:
                                    action_to_run.append(action.find('./{*}SHORT-NAME').text)
    return action_to_run


def get_arguments(modified_paths, bamf_paths, arxml_paths, cfg_path, pm_paths) -> List:
    """
    get all the actions to run the BTC tools
    :param modified_paths: contain all the path of the current change in PVER
    :param bamf_paths: contains all the bamf files
    """
    global BFW_ACTIONS
    arxml_arguments = []

    for fpath in arxml_paths:

        tree = etree.parse(fpath)
        root = tree.getroot()

        if '.arxml' in arxml_paths:
            for argument in get_arguments_arxml(arxml_paths):
                arxml_arguments.append(argument)
            for msrelem in root.findall(
                    ".//{*}ECUC-MODULE-CONFIGURATION-VALUES/{*}DEFINITION-REF/[@DEST='ECUC-MODULE-DEF']"):
                arxml_arguments.append(msrelem.text)
        else:
            for msrelem in root.findall(
                    './/{*}SW-SYSTEM/{*}CONF-SPEC/{*}CONF-ITEMS/{*}CONF-ITEM/{*}SHORT-NAME'):
                arxml_arguments.append('/MEDC17/' + msrelem.text)

    action_to_run = bamf_parser(modified_paths, bamf_paths, arxml_arguments)
    action_to_run.append('Setup')
    action_to_run.append('BctStart')

    if len(action_to_run) != 2:
        arguments = get_cfg_actions(cfg_path, action_to_run, pm_paths)
        args = list(arguments)
        args.sort(key=lambda i: BFW_ACTIONS.index(i) if i in BFW_ACTIONS else len(BFW_ACTIONS) - 1)
        logger.info(f"Total number of actions available: {len(BFW_ACTIONS)}")
        logger.info(f"Number of actions to run for the current changes: {len(args)}")
        if len(args) / len(BFW_ACTIONS) > 7:
            logger.info(
                "Almost more than 70% of the actions need to run for the current changes. "
                "It is recommended to run complete BCT instead of this selective build")
        return args
    return None


def get_command(modified_paths, bamf_paths, arxml_paths, cfg_path, pm_paths) -> (str, str):
    """
    Return BCT command, and its working path
    """
    founded = False

    env = os.path.normpath(WORKING_PATH)
    if not os.path.isdir(env):
        os.makedirs(env, exist_ok=True)

    if not os.path.exists(PATH):
        logger.error("BCT :: No ecu.Worx tools found")
        return None, env
    tool = is_runable(PATH)

    arguments = get_arguments(modified_paths, bamf_paths, arxml_paths, cfg_path, pm_paths)

    saving_path = os.path.normpath(SAVING_PATH + '\\bct')
    if not os.path.isdir(saving_path):
        os.makedirs(saving_path, exist_ok=True)
    output_str = '/'.join(saving_path.split('\\')[-2:])
    # change the setup file (saving directory information)
    setup_path = os.path.join(WORKING_PATH, r'MAK\MakeWare\setup.bamf')
    if os.path.exists(setup_path):
        tree = etree.parse(setup_path)
        root = tree.getroot()

        elements = root.findall('.//{*}SD')
        for element in elements:
            if element.attrib['GID'] == 'DIR_OUT':
                element.text = os.path.normpath(output_str)
                founded = True

        if not founded:
            new_element = etree.fromstring(f'<SD GID="DIR_OUT">{output_str}</SD>')
            root.find('.//{*}SDG').append(new_element)
        with open(setup_path, 'wb') as file:
            tree.write(file, encoding='utf-8')
        file.close()
    else:
        logger.info('BCT :: no setup path has been founded!')

    if arguments:
        btc_cli = 'cmd.exe /q /c call texec ' \
                  + str.join('/', [PATH.split('\\')[-2], PATH.split('\\')[-1]]) + tool \
                  + str.join(',', arguments) + ' -p %cd% --continue'
        return btc_cli, env
    return None, env
