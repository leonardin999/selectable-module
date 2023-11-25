"""
DOCSTRING: Damos run tools
"""
import os.path
import pathlib
import re
import warnings
from tools import helper
from tools import numbers
from typing import List, Dict
from lxml import etree
from PySide6.QtCore import QObject, Signal

# from utilities.log import get_logger
# logger = get_logger(__name__)


warnings.filterwarnings("ignore", category=FutureWarning)

# TODO: uncomment this part when operating the GUI function
# Saving path environment:
# PATH = ""
# WORKING_PATH = ""
# DICT_INIT_COMMAND = {}

class SyncSignal(QObject):
    """
    SyncSignal is a QObject that allows that BrowseDialog to emit signals
    """
    sync = Signal(str)
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
damos_signal = SyncSignal()
signal.sync.connect(sync)
damos_signal.sync.connect(env_sync)

class SyncInit(QObject):
    """
    SyncSignal is a QObject that allows that BrowseDialog to emit signals
    """
    sync = Signal(dict)

def tini_sync(dictionary):
    """
    Sync the Rtegen path.
    """
    global DICT_INIT_COMMAND
    DICT_INIT_COMMAND = dictionary

tini_signal = SyncInit()
tini_signal.sync.connect(tini_sync)

def is_required(item_class, item_name):
    """
    Check if the items is required for the DAMOS tools.
    """
    class_check = ["TDATA", "CTDATA"]
    if any(x in item_class for x in class_check) and '_pavast.xml' in item_name:
        return True

"""
SECTION: --> Creating the new *_pavast.xml to add in the --optionfile switch.
         --> Add the service fucntions contain all the variables which is wrote in another task.
"""
def extract_system_constant(all_pavast_paths):
    """
    find all the owned and exported system constant in *_pavast.xml files.
    """
    sc_list = []
    sc_dict = {}
    for path in all_pavast_paths:
        tree = etree.parse(path)
        root = tree.getroot()

        owned_elements = root.findall('.//{*}SW-FEATURE-OWNED-ELEMENTS//{*}SW-SYSTEMCONST-REF')
        if len(owned_elements)>0:
            for element in owned_elements:
                if element.text not in sc_list:
                    sc_list.append(element.text)

        export_elements = root.findall('.//{*}SW-INTERFACE-EXPORT//{*}SW-SYSTEMCONST-REF')
        if len(export_elements)>0:
            for element in export_elements:
                if element.text not in sc_list:
                    sc_list.append(element.text)
        sc_dict[path] = sc_list
        sc_list = []

    for path in all_pavast_paths:
        if len(sc_dict[path])<=0:
            del sc_dict[path]
    return sc_dict

def get_unresolved_value(sc_dict: Dict):
    """
    for the founded system constants --> find its value in [V,VF,VT] tags
    """
    values_dict = {}
    for path, var_list in sc_dict.items():
        tree = etree.parse(path)
        root = tree.getroot()
        sc_list = root.findall('.//SW-DATA-DICTIONARY-SPEC//{*}SW-SYSTEMCONST')
        for sc in sc_list:
            if len(sc)>0:
                sc_name = sc.find('.//{*}SHORT-NAME').text
                if sc_name in var_list:
                    for tag in helper.values_tag:
                        val = sc.find('.//{*}'+f'{tag}')
                        if val is not None:
                            value_str = re.sub(r"[\t\n]*","",etree.tostring(val, pretty_print=True).decode().strip())
                            values_dict[sc_name] = value_str
    return values_dict

def syscond_resolve(all_pavast_paths: List, sc_values: Dict):
    """
    Resolve values objects.
    resolve the system condition. Return True or False.
    """
    syscond_elements = []
    syscond_dict = {}
    syscond_tags = ['SW-SYSTEMCONST-REF-SYSCOND',
                      'SW-VARIABLE-REF-SYSCOND',
                      'SW-SERVICE-REF-SYSCOND',
                      'SW-CLASS-REF-SYSCOND',]

    for path in all_pavast_paths:
        tree = etree.parse(path)
        root = tree.getroot()

        for tag in syscond_tags:
            syscond_elements.extend(root.findall(f'.//{tag}'))

        if len(syscond_elements)>0:
            for element in syscond_elements:
                try:
                    syscond_name  = element.find(f'{element.tag.replace("-SYSCOND","")}').text
                    condition_str = element.find('SW-SYSCOND')
                    val_str = re.sub(r"[\t\n]*", "", etree.tostring(condition_str,
                                            pretty_print=True).decode()).strip()

                    value = helper.evaluate(val_str, sc_values, type='syscond')
                    if isinstance(value, numbers.Integral) or isinstance(value, numbers.Real):
                        if value == 1 :
                            syscond_dict[syscond_name] = True
                        else:
                            syscond_dict[syscond_name] = False
                    else:
                        syscond_dict[syscond_name] = value
                except:
                    pass
    return syscond_dict

def extract_elements(path):
    """
    find all elements have been exported or owned by current *_pavast.xml path.
    """
    reference_tags = ["SW-SYSTEMCONST-REF",
                      "SW-SERVICE-REF",
                      "SW-CLASS-REF",
                      "SW-VARIABLE-REF",
                      "SW-DATA-CONSTR-REF",
                      ]
    elements_list = []
    tree = etree.parse(path)
    root = tree.getroot()

    for tag in reference_tags:
        owned_elements = root.iterfind('.//{*}SW-FEATURE-OWNED-ELEMENTS//SW-FEATURE-ELEMENTS//{*}' + f'{tag}')
        if owned_elements is not None:
            for element in owned_elements:
                if element.text not in elements_list:
                    elements_list.append(element.text)

        export_elements = root.iterfind('.//{*}SW-INTERFACE-EXPORT//SW-FEATURE-ELEMENTS//{*}' + f'{tag}')
        if export_elements is not None:
            for element in export_elements:
                if element.text not in elements_list:
                    elements_list.append(element.text)

    return elements_list

def get_exported_variables(modified_paths: List)->List:
    """
    Parse inside modified *_pavast.xml to extract the elememts have been exported
    Required:
        # elements taken by all the <*-REF>
        # check tag: .//SW-INTERFACE-EXPORT
    """
    export_elements = []

    for file_path in modified_paths:
        path = os.path.join(PATH, file_path)
        if os.path.exists(path):
            export_elements.extend(extract_elements(path))

    return export_elements

def create_references_dict(all_pavast_paths: List) -> Dict:
    """
    Create a references dictionary to get which elements is used in dictionary tag
    """
    created_data = {}
    for path in all_pavast_paths:
        if os.path.exists(path):
            var_list = extract_elements(path)
            if var_list is not None:
                for key in extract_elements(path):
                    created_data[key] = path
    return created_data

def get_task_references()->(Dict, str):
    """
    get all the the task contain the process running when PVER is built
    required:
        --> get the `--os_auto_conf_sched_file` option to located the schedule file of PVER
        --> Create a Dictionary to defined which Task is produced running processes
    """
    task_dict = {}

    ### Serching the .opt file to file the option switch
    opt_dir = os.path.join(PATH, r'_gen\swb\module\data\opt')
    opt_path = [os.path.join(opt_dir, path) for path
                in os.listdir(opt_dir) if '.opt' in path]
    for path in opt_path:
        with open(path, 'r', encoding='utf-8') as file:
            for line in file.readlines():
                option = line.strip().split("\t")
                if option[0].strip('\t') == '--os_auto_conf_sched_file':
                    os_task_path = option[-1].strip()
                    break

    schedule_path = os.path.join(PATH, os_task_path)

    new_os_task_path = '/'.join(['_smb', os_task_path.split('/',1)[-1]])
    smb_task_path = os.path.join(PATH, new_os_task_path)
    if os.path.exists(smb_task_path):
        os.remove(smb_task_path)
    if not os.path.exists(schedule_path):
        return {}, new_os_task_path

    tree = etree.parse(schedule_path)
    root = tree.getroot()

    for task in root.findall('.//{*}OS_TASK'):
        process = [name.text for name in task.findall('.//{*}OS_PROCESS')]
        task_dict[task.find('.//{*}OS_TASKNAME').text] = process

    with open(smb_task_path, 'wb') as file:
        tree.write(file, pretty_print=True, method='xml')
    return task_dict, new_os_task_path

def get_accessed_references(all_pavast_paths: List):
    """
    create a references dictionary to define service functions in which
    contained all the written variables
    required:
        --> search for all SW-SERVICE has been export in all pavast file.
        --> check .//SW-VARIABLE-USAGE for the mode [WRITE, READWRITE, READ]
        --> get all the variables which is wrote.
    return dict {'service_name': list(write_variables)]}
    """
    accessed_dict = {}
    variables = []
    services = []
    for file_path in all_pavast_paths:
        path = os.path.join(PATH, file_path)
        tree = etree.parse(path)
        root = tree.getroot()
        for service in root.findall('.//{*}SW-SERVICE'):
            if service.find('.//{*}CATEGORY').text == 'PROCESS':
                for variable in service.findall('.//{*}SW-ACCESSED-VARIABLE'):
                    mode = variable.find('.//{*}SW-VARIABLE-USAGE')
                    if mode is not None:
                        if mode.text in ['WRITE', 'READWRITE']:
                            variables.append(etree.tostring(variable,
                                            pretty_print=True, encoding='utf-8'))
                for service_ref in service.findall('.//{*}SW-ACCESSED-SERVICE'):
                    variables.append(etree.tostring(service_ref,
                                        pretty_print=True, encoding='utf-8'))

                accessed_dict[service.find('.//{*}SHORT-NAME').text] = variables
                services.append(service.find('.//{*}SHORT-NAME').text)
                variables = []

    for service in services:
        if service in accessed_dict.keys():
            if not accessed_dict[service]:
                del accessed_dict[service]
    return accessed_dict

def get_element_name(elements: List):
    element_dict ={}
    if elements:
        for element in elements:
            tree = etree.fromstring(element)
            if tree.find('.//{*}SW-VARIABLE-REF') is not None:
                element_dict[tree.find('.//{*}SW-VARIABLE-REF').text]= element
            if tree.find('.//{*}SW-SERVICE-REF') is not None:
                element_dict[tree.find('.//{*}SW-SERVICE-REF').text] = element
    return element_dict

def create_service_resources(all_pavast_paths: List, references_list: List)->(Dict, str):
    """
    Create: --> new resources for services function.
            --> new Schedule path for smb run tools
    """
    tasks, task_path = get_task_references()
    accessed_dict = get_accessed_references(all_pavast_paths)

    service_dict = {}
    new_services = {}
    services_list = []
    temp = []
    for variable in references_list:
        for service, elements in accessed_dict.items():
            process_var = get_element_name(elements)
            if variable in process_var.keys():
                for task_name, process in tasks.items():
                    if service in process:
                        service_dict[process_var[variable]] = task_name

    for name in list(service_dict.values()):
        if name not in services_list:
            services_list.append(name)

    for service in services_list:
        for key, value in service_dict.items():
            if value == service:
                temp.append(key)
        new_services[service] = temp
        temp = []
    return new_services, task_path

def get_original_elements(path: str, export_variables: List, consider_variables: List)->List:

    """
    find the current reference variables in the modified PVER.
    if variable has been exported --> pass.
    """
    # parsing elements inside the  .//SW-INTERFACE-IMPORT
    import_tags = ["SW-SYSTEMCONST-REF",
                   "SW-VARIABLE-REF",
                   "SW-SERVICE-REF",
                   "SW-CLASS-REF",
                   "SW-SYSTEMCONST-CODED-REF"]

    reference_variables = []
    if os.path.exists(path):
        tree = etree.parse(path)
        root = tree.getroot()

        for tag in import_tags:
            import_elements = root.findall('.//{*}SW-INTERFACE-IMPORT//{*}' + f'{tag}')
            if len(import_elements)>0:
                for element in import_elements:
                    val = element.text
                    if val not in export_variables \
                        and val not in reference_variables \
                        and val in consider_variables:
                        reference_variables.append(val)
    return reference_variables

def get_references(path: str, key: str, export_variable: List)-> List:
    """
    find all the references if a variable has beeb used it when defining itself.
    """
    variables = []
    reference_tags = ["SW-VARIABLE-REF",
                      "SW-SERVICE-REF",
                      "SW-SYSTEMCONST-REF",
                      "SW-CLASS-REF",
                      "SW-COMPU-METHOD-REF",
                      "SW-DATA-CONSTR-REF",
                      "SW-SYSTEMCONST-CODED-REF"
                     ]
    # Creating a dictionary that contain children tags
    tree = etree.parse(path)
    element = tree.find(".//SW-DATA-DICTIONARY-SPEC")
    for ancestor in element.xpath('*[.//SHORT-NAME]'):
        children = [x for x in ancestor.getchildren() if x is not None]
        for child in children:
            # check if any variables has been referred for this current definition
            if child.find('.//SHORT-NAME') is not None:
                if child.find('.//SHORT-NAME').text == key:
                    for tag in reference_tags:
                        variables.extend([var.text for var in child.findall(f".//{tag}")
                            if var is not None and var.text not in export_variable])

            # check -ref variable in VF tag:
            for vf in child.findall('.//VF'):
                if vf is not None:
                    for element in vf.getchildren():
                        if element is not None:
                            if element.text not in variables:
                                variables.append(element.text)

                    if vf.text is not None:
                        if not re.match("[+-]?([0-9]*[.])?[0-9]+", vf.text.strip()):
                            if vf.text not in variables:
                                variables.append(vf.text)
    return variables

def get_path_of_element(variables: List, references_dict: Dict,
                      current_export: List) -> (Dict, List):
    """
    each element has its own definition in dictionary-spec, this function help to find the
    definition of that variables.
    args:
        variables : current variable need to be defined.
        references_dict : refer to which variable has been exported in which paths.
        current_export : List of all variable has been exported in current run.

    """
    global file_path
    created_resources = {}
    path_list = []
    for _, path in references_dict.items():
        key = os.path.normpath(path)
        if key not in created_resources.keys():
            created_resources[key] = []
            path_list.append(key)
    references_list = []
    references_list.extend(variables)  # this list gonna change its size cuz its references add-in.
    for variable in references_list:
        if variable in references_dict.keys():
            file_path = os.path.normpath(references_dict[variable])
            if variable not in created_resources[file_path]:
                created_resources[file_path].append(variable)

        # if the current path contain more references <*-REF>, take it all!
            references_list.extend([x for x in get_references(file_path,variable,
                                                              current_export)
                                    if x not in references_list])
    for path in path_list:
        if not created_resources[path]:
            del created_resources[path]
    return created_resources, references_list

def Create_service_function(service_resources: Dict, created_pavast: str) -> Dict:
    """
    Create a new services and add in the SMB_PAVAST.
    """
    template = """ <SW-SERVICE>
                    <SHORT-NAME></SHORT-NAME>
                    <CATEGORY>PROCESS</CATEGORY>
                    <SW-SERVICE-RETURN>
                      <SW-DATA-DEF-PROPS>
                        <SW-BASE-TYPE-REF>void</SW-BASE-TYPE-REF>
                      </SW-DATA-DEF-PROPS>
                    </SW-SERVICE-RETURN>
                    <SW-SERVICE-ARGS>
                      <SW-SERVICE-ARG>
                        <SW-DATA-DEF-PROPS>
                          <SW-BASE-TYPE-REF>void</SW-BASE-TYPE-REF>
                        </SW-DATA-DEF-PROPS>
                      </SW-SERVICE-ARG>
                    </SW-SERVICE-ARGS>
                    <SW-SERVICE-ACCESSED-ELEMENT-SETS>
                        <SW-SERVICE-ACCESSED-ELEMENT-SET>
                            <SW-ACCESSED-VARIABLES>
                            
                            </SW-ACCESSED-VARIABLES>
                            <SW-ACCESSED-SERVICES>
                            
                            </SW-ACCESSED-SERVICES>
                        </SW-SERVICE-ACCESSED-ELEMENT-SET>
                    </SW-SERVICE-ACCESSED-ELEMENT-SETS>
                    </SW-SERVICE>
               """
    added_services = {}
    for service_name, content in service_resources.items():
        new_name = 'SMB_' + service_name
        tree = etree.fromstring(template)
        tree.find('.//{*}SHORT-NAME').text = new_name
        accessed_variables = tree.find('.//{*}SW-ACCESSED-VARIABLES')
        accessed_services = tree.find('.//{*}SW-ACCESSED-SERVICES')
        for text in content:
            tag = etree.fromstring(text).tag
            if tag == 'SW-ACCESSED-VARIABLE':
                accessed_variables.append(etree.fromstring(text))
            elif tag == 'SW-ACCESSED-SERVICE':
                accessed_services.append(etree.fromstring(text))

        new_content = etree.tostring(tree, pretty_print=True, encoding='utf-8')
        added_services[new_name] = new_content

    tree = etree.parse(os.path.join(PATH,  created_pavast))
    pavast_root = tree.getroot()

    for name, content in added_services.items():
        services_tag = pavast_root.find(f'.//SW-DATA-DICTIONARY-SPEC//SW-SERVICES')
        if services_tag is not None:
            services_tag.append(etree.fromstring(content))
        ownership = pavast_root.find(
            './/SW-FEATURE-OWNED-ELEMENTS//SW-SERVICE-REFS')
        if ownership is not None:
            own_element = etree.SubElement(ownership, "SW-SERVICE-REF")
            own_element.text = name
            own_element.tail = "\n\t\t\t\t"
        export = pavast_root.find(
            './/SW-INTERFACE-EXPORT//SW-SERVICE-REFS')
        if export is not None:
            out = etree.SubElement(export, "SW-SERVICE-REF")
            out.text = name
            out.tail = "\n\t\t\t\t"

    with open(os.path.join(PATH, created_pavast), 'wb') as file:
        tree.write(file, pretty_print=True, method='xml')

    return added_services

def template_file() -> str:
    """
    Contain the template_pavast (version 1).
    --> Directory of the created template_pavast file.
    """
    _output_file = "template_pavast.xml"
    _output_string = """<?xml version='1.0' encoding='ISO-8859-1'?>
    <!DOCTYPE MSRSW PUBLIC "-//MSR//DTD MSR SOFTWARE DTD:V2.2.2:RB17:LAI:IAI:XML:MSRSW.DTD//EN" "msrsw_v222_rb17.xml.dtd">
    <MSRSW>
      <CATEGORY>PaVaSt</CATEGORY>
      <ADMIN-DATA>
    <LANGUAGE>en</LANGUAGE>
    <COMPANY-DOC-INFOS>
      <COMPANY-DOC-INFO>
        <COMPANY-REF>RB</COMPANY-REF>
        <SDGS>
          <SDG GID="RBHead-eASEE-Keywords">
            <SD GID="Filename">smb_pavast.xml</SD>
            <SD GID="Author"/>
            <SD GID="Function"></SD>
            <SD GID="Domain"></SD>
            <SD GID="User">_SMB</SD>
            <SD GID="Date"></SD>
            <SD GID="Class">TDATA</SD>
            <SD GID="Name"></SD>
            <SD GID="Variant"></SD>
            <SD GID="Revision"></SD>
            <SD GID="Type">XML</SD>
            <SD GID="State"></SD>
            <SD GID="UniqueName"/>
            <SD GID="Component"/>
            <SD GID="Generated"/>
            <SD GID="FDEF"/>
            <SD GID="History">Dummy File created for SMB tool usage</SD>
          </SDG>
        </SDGS>
      </COMPANY-DOC-INFO>
    </COMPANY-DOC-INFOS>
      </ADMIN-DATA>
      <SW-SYSTEMS>
    <SW-SYSTEM>
      <SHORT-NAME>MEDC17</SHORT-NAME>
      <SW-DATA-DICTIONARY-SPEC>
        <SW-VARIABLES>
        </SW-VARIABLES>
        <SW-SYSTEMCONSTS>
        </SW-SYSTEMCONSTS>
        <SW-COMPU-METHODS>
        </SW-COMPU-METHODS>
        <SW-DATA-CONSTRS>
        </SW-DATA-CONSTRS>
        <SW-SERVICES>
        </SW-SERVICES>
        <SW-CLASSES>
        </SW-CLASSES>
      </SW-DATA-DICTIONARY-SPEC>
      <SW-COMPONENT-SPEC>
        <SW-COMPONENTS>
          <SW-FEATURE>
            <SHORT-NAME>SMB</SHORT-NAME>
            <CATEGORY>FCT</CATEGORY>
            <SW-DATA-DICTIONARY-SPEC>
            </SW-DATA-DICTIONARY-SPEC>
            <SW-FEATURE-OWNED-ELEMENTS>
              <SW-FEATURE-ELEMENTS>
                <SW-CLASS-REFS>
                </SW-CLASS-REFS>
                <SW-COMPU-METHOD-REFS>
                </SW-COMPU-METHOD-REFS>
                <SW-SERVICE-REFS>
                </SW-SERVICE-REFS>
                <SW-SYSTEMCONST-REFS>
                </SW-SYSTEMCONST-REFS>
                <SW-VARIABLE-REFS>
                </SW-VARIABLE-REFS>
              </SW-FEATURE-ELEMENTS> 
            </SW-FEATURE-OWNED-ELEMENTS>
            <SW-FEATURE-INTERFACES>
              <SW-FEATURE-INTERFACE>
                <SHORT-NAME>SMB_Ex</SHORT-NAME>
                <CATEGORY>EXPORT</CATEGORY>
                <SW-INTERFACE-EXPORTS>
                  <SW-INTERFACE-EXPORT>
                    <SW-INTERFACE-EXPORT-SCOPE>
                      <SW-INTERFACE-EXPORT-LEVEL>PARENT</SW-INTERFACE-EXPORT-LEVEL>
                    </SW-INTERFACE-EXPORT-SCOPE>
                    <SW-FEATURE-ELEMENTS>
                <SW-CLASS-REFS>
                </SW-CLASS-REFS>
                <SW-SERVICE-REFS>
                </SW-SERVICE-REFS>
                <SW-SYSTEMCONST-REFS>
                </SW-SYSTEMCONST-REFS>
                <SW-VARIABLE-REFS>
                </SW-VARIABLE-REFS>
              </SW-FEATURE-ELEMENTS>
                  </SW-INTERFACE-EXPORT>
                </SW-INTERFACE-EXPORTS>
              </SW-FEATURE-INTERFACE>
              <SW-FEATURE-INTERFACE>
                <SHORT-NAME>SMB_Im</SHORT-NAME>
                <CATEGORY>IMPORT</CATEGORY>
    				<!--	Import section will not be used in the first version of the tool	!-->
                <SW-INTERFACE-IMPORTS>
                  <SW-INTERFACE-IMPORT>
                    <SW-FEATURE-ELEMENTS>
              </SW-FEATURE-ELEMENTS>
                  </SW-INTERFACE-IMPORT>
                </SW-INTERFACE-IMPORTS>
              </SW-FEATURE-INTERFACE>
            </SW-FEATURE-INTERFACES>
          </SW-FEATURE>
        </SW-COMPONENTS>
      </SW-COMPONENT-SPEC>
      <SW-INSTANCE-SPEC>
        <SW-INSTANCE-TREE>
          <SHORT-NAME>SMB</SHORT-NAME>
          <CATEGORY>TEST_INIT_VALUES</CATEGORY>
    				<!--	Instance tree section will not be used in the first version of the tool	!-->
    		  </SW-INSTANCE-TREE>
      </SW-INSTANCE-SPEC>
      <SW-COLLECTION-SPEC>
        <SW-COLLECTIONS>
          <SW-COLLECTION>
            <SHORT-NAME>H_C_FILES</SHORT-NAME>
            <CATEGORY>PROCOL_COMP</CATEGORY>
            <SW-COLLECTION-CONT>
              <SW-FEATURE-REFS>
                <SW-FEATURE-REF>SMB</SW-FEATURE-REF>
              </SW-FEATURE-REFS>
            </SW-COLLECTION-CONT>
          </SW-COLLECTION>
        </SW-COLLECTIONS>
      </SW-COLLECTION-SPEC>
    </SW-SYSTEM>
      </SW-SYSTEMS>
    </MSRSW>
"""
    _output_path = pathlib.Path(__file__).parent.parent.joinpath(
        "templates/").as_posix()
    if not os.path.isdir(_output_path):
        os.makedirs(_output_path)

    with open(os.path.join(_output_path, _output_file),
              'w', encoding='utf-8') as file:
        file.write(_output_string)
    file.close()
    return file.name

def element_stuffing(created_resources: Dict) -> str:
    """
    stuff all the founded variables have been defined in to the empty pavast file.
    --> return name of saved file
    """

    parser = etree.XMLParser(remove_blank_text=False)
    template_tree = etree.parse(template_file(), parser)
    template_root = template_tree.getroot()
    # Creating a dictionary that contain children tags
    for path, arguments in created_resources.items():
        tree = etree.parse(path)
        root = tree.getroot()
        element = root.find(".//SW-DATA-DICTIONARY-SPEC")
        for key in arguments:
            for ancestor in element.xpath('*[.//SHORT-NAME]'):
                children = ancestor.getchildren()
                if children is not None:
                    for child in children:
                        if child.find('.//SHORT-NAME') is not None:
                            if child.find('.//SHORT-NAME').text == key:
                                dictionary = template_root.find(f'.//SW-DATA-DICTIONARY-SPEC//{ancestor.tag}')
                                owned_tag = child.tag + '-REFS'
                                if dictionary is not None:
                                    dictionary.append(child)
                                ownership = template_root.find(
                                    './/SW-FEATURE-OWNED-ELEMENTS//{*}'+f'{owned_tag}')
                                if ownership is not None:
                                    own_element = etree.SubElement(ownership, f"{child.tag}-REF")
                                    own_element.text = key
                                    own_element.tail = "\n\t\t\t\t"
                                export = template_root.find(
                                    './/SW-INTERFACE-EXPORT//{*}'+f'{owned_tag}')
                                if export is not None:
                                    out = etree.SubElement(export, f"{child.tag}-REF")
                                    out.text = key
                                    out.tail = "\n\t\t\t\t"

    _output_file = template_tree.find(".//*[@GID='Filename']")
    saved_as = '_smb/damos'+f'/{_output_file.text}'

    with open(os.path.join(PATH, saved_as), 'wb') as file:
        template_tree.write(file, pretty_print=True, method='xml')
    return saved_as

def config_task_option(os_path, new_services):
    """
    Change the os-task-file-opt value to the newly create schedule smb file path.
    """
    task_path = os.path.join(PATH, os_path)
    tree = etree.parse(task_path)
    root = tree.getroot()

    for name, _ in new_services.items():
        for task in root.findall('.//{*}OS_TASK'):
            if task.find('.//{*}OS_TASKNAME').text == name.split('SMB_')[1]:
                process = etree.SubElement(task, "OS_PROCESS")
                process.text = name
                process.tail = '\n\t\t'

    with open(task_path, 'wb') as file:
        tree.write(file, pretty_print=True, method='xml')

def new_pavast_file(modified_paths: List=None,
                    all_pavasts: List=None,)-> (str, Dict):
    """
    create a new *_pavast.py file contain modified information.
    return:
        filename or directory to the created *_pavast.xml file.
    """
    global_all_pavast = [os.path.join(PATH, file_path)
                         for file_path in all_pavasts]

    # Creating the the export dictionary of all *_pavast.xml in PVER folder
    references = create_references_dict(global_all_pavast)

    # Creating a List of exported elements by current check
    current_exports = get_exported_variables(modified_paths)

    # create a system constant dictionary:
    sc_dict = extract_system_constant(global_all_pavast)
    values_dict = get_unresolved_value(sc_dict)

    # resolve values for all system constants :
    for name, val_str in values_dict.items():
        values_dict[name] = helper.evaluate(val_str, values_dict,type='system_const',post_eval=True)

    # Resolve system condition:
    syscond_dict = syscond_resolve(all_pavasts, values_dict)

    # consider elements with the condition is True:
    consider_elements = []
    for element, condition in syscond_dict.items():
        if condition:
            if element not in consider_elements:
                consider_elements.append(element)

    # List of all undefined elements in current check
    reference_elements = []
    for fpath in modified_paths:
        path = os.path.join(PATH, fpath)
        reference_elements.extend(get_original_elements(path, current_exports, consider_elements))

    # Creating a *_pavast.xml which add in founded elements
    created_resources, references_list = get_path_of_element(reference_elements, references, current_exports)

    # Creating a services resource dictionary
    services_resources, task_path = create_service_resources(global_all_pavast,
                                                            references_list)

    filename = element_stuffing(created_resources)
    new_services = Create_service_function(services_resources, filename)
    config_task_option(task_path, new_services)
    return filename

"""
SECTION: Create the pavast_files.lst (current change of switch: --pavast_files in option file)
"""
def path_global_config(folder: str, global_path: str=None)->str:
    """
    Create the global directory that using when the damos tools generate output files
    args:
        folder : name of generated folder of damos
    """
    config_path = (global_path or WORKING_PATH) + r'\swb'
    generated_folder = config_path + rf"\{folder}"
    if not os.path.isdir(config_path):
        os.makedirs(config_path)
    if not os.path.isdir(generated_folder):
        os.makedirs(generated_folder)
    return generated_folder

def create_pavast_file_option(modified_paths: List, mandatory_paths: List,
                              all_pavast_paths: List) -> str:
    """
    Creating a 'pavast_files.lst' which contain all the modified paths
    and new created path.
    """
    selected_paths = []
    selected_paths.extend(modified_paths)
    for path in mandatory_paths:
        if path not in selected_paths:
            selected_paths.append(path)

    filegroup = path_global_config(r'filegroup\src_lists')
    filename = os.path.join(str(filegroup + r"\pavast_files.lst").replace('/', '\\'))

    smb_pavast_file = new_pavast_file(selected_paths, all_pavast_paths)
    pavast_files = []
    pavast_files.extend(modified_paths)
    pavast_files.append(smb_pavast_file)

    with open(filename, 'w', encoding='utf-8') as file:
        for path in pavast_files:
            file.write(path + '\n')
    file.close()
    formated_name = filename.split(os.path.join(PATH.replace('/', '\\'), ''))[1]
    return formated_name

"""
SECTION 2: Configure option-file (*.opt).
"""

def opt_parse(path: str, keyword: str,
              pavast_files: str) -> (str,str):
    """
    --> get the .opt path
    --> change criteria parameter for smb run.
    """

    path_name = path.split('\\')[-1]
    parameter_check = ['--pavast_files', '--data_mcop_tmp_dir','--swb_data_log_dir'
                       '--swb_src_mcop_tmp_dir', '--swb_src_data_tmp_dir',
                       '--data_include_dir', '--data_tmp_dir', '--mcop_include_dir',
                       '--num_axispoints_list','--log', '--coregen_pavast_files',
                       '--os_auto_conf_sched_file']
    all_parameter = {}
    parameter_dict = {}
    created_dict = {}
    with open(path, 'r', encoding='utf-8') as file:
        for line in file.readlines():
            option = line.strip().split("\t")
            if len(option) > 1:
                for opt in option:
                    value = option[-1]
                    all_parameter[option[0]] = option[-1]
                    if opt in parameter_check:
                        parameter_dict[option[0]] = option[-1]
                    if value.split('/')[0].strip() == '_log':
                        parameter_dict[option[0]] = option[-1]
            else:
                all_parameter[option[0]] = ' '

    file.close()
    for parameter, value in parameter_dict.items():
        old_string = value.split('/')
        old_string.pop(0)
        old_string.insert(0, keyword)
        new_string = '/'.join(old_string)
        created_dict[parameter] = new_string
        if parameter == parameter_check[0]:
            new_string = pavast_files
            created_dict[parameter] = new_string

    with open(path.replace('_gen', '_smb'), 'w', encoding='utf-8') as file:
        for parameter, value in all_parameter.items():
            line = f"{parameter}" + "\t\t\t\t" + f"{value}" + '\n'
            for para, new_value in created_dict.items():
                if para == parameter:
                    line = f"{parameter}" + "\t\t\t\t" + f"{new_value}" + '\n'
            file.write(line)
    file.close()
    return os.path.splitext(path_name)[0], os.path.normpath(path.replace('_gen', '_smb'))

def modify_optionfile_switch(commands: List, opt_path: Dict)-> List:
    """
    Change the path in parameter --optionfile of current command.
    args:
        commands : List of command taken in All_commands.log
        opt_path (Dict) : all path of the saving *.opt file.
    """
    modified_command_list = []
    for command in commands:
        if '--optionsfile' in command:
            old_command = command.strip("\n").split(" ")
            index = old_command.index('--optionsfile')+1
            element = old_command.pop(index)
            replaced_element = os.path.splitext(element.split('/')[-1])
            old_command.insert(index, opt_path[replaced_element[0]])
            new_command = ' '.join(old_command)
            modified_command_list.append(new_command)
        else:
            modified_command_list.append(command.strip("\n"))
    return modified_command_list

def modify_project_root(commands: List, global_path: str = None)-> List:
    """
    Change the path in parameter --prj_root of current command.
    args:
        commands : List of command taken in All_commands.log
    """
    modified_command_list = []
    for command in commands:
        if '--prj_root' in command:
            old_command = command.strip("\n").split(" ")
            index = old_command.index('--prj_root')+1
            old_command.pop(index)
            old_command.insert(index, PATH or global_path)
            new_command = ' '.join(old_command)
            modified_command_list.append(new_command)
        else:
            modified_command_list.append(command.strip("\n"))
    return modified_command_list

"""
SECTION 3: Configure command to run damos tool.
"""

def get_original_command()->List:
    """
    read inside the all_commands.logs to get the command to run Damos tool
    ==> return the List of original commands without changing the arguments.
    """
    command_path = os.path.join(PATH, r'_log\swb\All_Commands.log')
    if not os.path.exists(command_path):
        # logger.info('No command to run.')
        return None
    all_command = []
    damos_command = []
    with open(command_path, 'r', encoding='utf-8') as file:
        for line in file.readlines():
            if '#' not in line and "cmd.exe /q /c call" in line:
                all_command.append(line)

            if '_gen/swb/module/data/' in line \
                    and ('damoskdo.exe' in line or 'dgs_ice.cmd' in line) \
                    and line not in damos_command:
                damos_command.append(line.strip())

    damos_command.sort(key=lambda i: all_command.index(i)
    if i in all_command else len(all_command) - 1)
    for command in damos_command:
        if 'cmd.exe /q /c call' not in command:
            index = damos_command.index(command)
            old_command = damos_command.pop(index)
            damos_command.insert(index, 'cmd.exe /q /c call '+ old_command)
    return damos_command


def get_all_pavast_file(current_pavast: List, opt_path: List) -> List:
    """
    get all the option file in data folder.

    """
    get_path = []
    pavast_path = []
    total_paths = []
    for path in opt_path:
        with open(path, 'r', encoding='utf-8') as file:
            options = [opt.strip() for opt in file.readlines()
                       if re.match(r'--\w+_pavast_files', opt.strip())]
            for option in options:
                get_path.append(os.path.join(PATH, option.split("\t")[-1].strip()))
    for path in get_path:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as file:
                pavast_path.extend([path.strip() for path in file.readlines()])

    current_pavast.extend(pavast_path)
    for path in current_pavast:
        config_path = os.path.join(PATH, path)
        if os.path.exists(config_path) and config_path not in total_paths:
            total_paths.append(config_path)
    return total_paths

def get_command(modified_paths: List,
                pavast_paths: List)-> (str, str):
    """
    get all the command to run the damos tools completely.
    args:
        modified_paths: all the *_pavast.xml file collected at current selected node.
        all_pavast_paths: all the *_pavast.xml inside the working PVER
    return
        all_command: List of all command.
        env: working environment
    """
    # initialize empty file for smb:
    list_command = []
    mandatory_paths = []
    env = PATH

    global_config = os.path.join(PATH, '_smb/damos')
    if not os.path.isdir(global_config):
        os.makedirs(global_config)

    # create folder for Damos tools
    path_global_config('module')
    path_global_config(r'module\data\opt')
    path_global_config(r'module\coreproc')
    makeware_path = WORKING_PATH + '/MakeWare'

    #TODO: consider empty axispoints.lst for this version
    if not os.path.exists(makeware_path):
        os.makedirs(makeware_path)
    axispoint_path = os.path.join(makeware_path, 'axispoints.lst')
    with open(axispoint_path, 'w', encoding='utf-8') as file:
        file.write("")
    file.close()

    # TODO: consider empty filelist_gen_pavast_xml for this version
    gen_pavast_path = os.path.join(PATH,
                       r'_gen\swb\module\coreproc\filelist_gen_pavast_xml.txt')
    with open(gen_pavast_path.replace('\_gen', '\_smb'), 'w',
              encoding='utf-8') as file:
        file.write("")
    file.close()

    # checking if the option file exist in PVER, if not abort!
    opt_dir = os.path.join(PATH, r'_gen\swb\module\data\opt')
    if not os.path.isdir(opt_dir):
        return None, env

    original_opt_list = [os.path.join(opt_dir, path) for path
                         in os.listdir(opt_dir) if '.opt' in path]
    original_command = get_original_command()
    if original_command is None:
        return None, env

    # Consider all Pavast files to run Damos tools.
    all_pavast_paths = get_all_pavast_file(pavast_paths, original_opt_list)

    # consider path in side the condsys_pavast_files.lst as mandatory files
    condsys_path = os.path.join(PATH,
                                r'_gen\swb\filegroup\src_lists\condsys_pavast_files.lst')
    with open(condsys_path, 'r', encoding='utf-8') as file:
        for line in file.readlines():
            mandatory_paths.append(line.strip())

    # Create a new pavast file (--pavast_file)
    pavast_files = create_pavast_file_option(modified_paths, mandatory_paths, all_pavast_paths)

    # Create a new .opt file (--optionfile)
    created_opt_file = {}
    for option in original_opt_list:
        switch, new_path = opt_parse(option, '_smb', pavast_files)
        created_opt_file[switch] = new_path
    # add initialize command in running command:
    if DICT_INIT_COMMAND:
        for _, init_command in DICT_INIT_COMMAND.items():
            list_command.append(init_command)

    # modified command :
    modified_command = modify_optionfile_switch(original_command, created_opt_file)
    new_command = modify_project_root(modified_command)
    list_command.extend(new_command)
    result = "cmd.exe /q /c call "+" && ".join(list_command)
    return result, env

if __name__ == '__main__':

    global PATH
    global WORKING_PATH

    # this will change when running GUI --> emit signal to damos tool
    DICT_INIT_COMMAND = {
    "damos" :"tini damos 5.8.15.2",
    "dgs_ice":"tini dgs_ice 2.2.1",
    "dgs_signature_keys":"tini dgs_signature_keys 1.0.0",
    "dgs_signature":"tini dgs_signature 1.1.8",
    }
    PATH = r'C:\sources\PVER\EVC1013P01C1929_XD50_EP'
    WORKING_PATH = r'C:\sources\PVER\EVC1013P01C1929_XD50_EP\_smb'
    all_pavast_paths = list()
    modified_paths = list()

    with open(os.getcwd()+r'\scripts\all_pavasts.lst', 'r') as f:
        for line in f.readlines():
            all_pavast_paths.append(line.strip())
    f.close()

    with open(os.getcwd()+r'\scripts\modified_pavast.lst', 'r') as f:
        for line in f.readlines():
            modified_paths.append(line.strip())
    f.close()
    new_command,env = get_command(modified_paths, all_pavast_paths)
    print(new_command)