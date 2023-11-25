"""
TODO: Write docstring
"""
import os
import ctypes  # For simple message box
from os import path
from subprocess import getoutput as go  # To fetch windows specific information
from lxml import etree
from utilities.log import get_logger

logger = get_logger(__name__)


def is_environment_compatible() -> bool:
    """
    Checking the current environment of operating Systems.
    Current compatibility with only Windows. Fully tested in Microsoft Windows 10 Enterprise
    and Microsoft Windows Server 2016 Standard
    """

    try:
        # Get the current operating system information
        version = go("wmic os get Caption /value").strip()[8:]
        logger.debug("The operation system: " + version)
        # Check if os is Windows
        if not version.startswith("Microsoft Windows"):
            logger.error("Not a valid Windows Operating System. "
                         "Tool run not possible.")
            msg = "Does not seem to be a valid Windows Operating System." \
                  "\n\nTool run not possible."
            ctypes.windll.user32.MessageBoxW(0, msg, "Unknown Environment", 0)
            return False
        elif version != "Microsoft Windows 10 Enterprise" \
                and version != "Microsoft Windows Server 2016 Standard":
            logger.warning("Detect Untested Environment")
            rc = ctypes.windll.user32.MessageBoxW(
                0,
                f"Untested {version} detected.\nTool might not function properly."
                f"\n\nDo you want to proceed?",
                f"Untested Environment",
                4)
            if rc != 6:
                return False
    except Exception as exception:
        logger.error("Unable to determine the operating system environment. "
                    "Tool cannot proceed..")
        logger.error(f"Details: \n{exception}")
        ctypes.windll.user32.MessageBoxW(0,
                                         "Error while checking environment,"
                                         " see logs for more details.",
                                         "Check environment failed",
                                         0)
        return False
    return True


def check_pver_is_built(pver_root) -> bool:
    """Check if a pver is built or not.\
    Generally, we can check for existence .hex file and .a2l file in _bin/swb/*.hex
    and _bin/swb/*.a2l.\n However if we dont them in above folders,
     we can try checking in _gen/swb/module/hexmod/*.hex and _gen/swb/module/*.a2l.
    """
    import glob

    # there will be some .hex or .a2l files having these suffix. Simply ignore them.
    excluded_suffix = ["clean", "internal", "tmp", "src"]

    def check_hex_bin(name) -> bool:
        """Check for existence of .hex in _bin"""
        swb_folder = path.join(bin_folder, "swb")

        logger.debug("Searching hex file in _bin..")

        if not path.isdir(swb_folder):
            logger.error(r"_bin\swb folder not found. PVER not valid")
            return False

        # check for either test_PVER.hex or PVER.hex
        hex_files = glob.glob1(swb_folder, f"*{name}*.hex")

        # remove all invalid suffix
        for f in hex_files:
            for suffix in excluded_suffix:
                if suffix in f:
                    hex_files.remove(f)

        if len(hex_files) == 0:
            logger.error("No .hex found in _bin")
            return False
        else:
            # there should only be 1 hex file. Or there will be test_PVER.hex and PVER.hex.
            # In that case take any is fine
            hex_file = os.path.join(swb_folder, hex_files[0])

        if not path.isfile(hex_file):
            logger.error("No .hex found in _bin")
            return False

        return True

    def check_hex_gen(name) -> bool:
        """Check for existence of .hex in _gen"""
        hexmod_folder = path.join(gen_folder, "swb", "module", "hexmod")

        logger.critical("Try searching in _gen..")

        if not path.isdir(hexmod_folder):
            logger.error(r"_gen\swb\module\hexmod folder not found. PVER not valid")
            return False

        # check for either test_PVER.hex or PVER.hex
        hex_files = glob.glob1(hexmod_folder, f"*{name}*.hex")

        # remove all invalid suffix
        for f in hex_files:
            for suffix in excluded_suffix:
                if suffix in f:
                    hex_files.remove(f)

        if len(hex_files) == 0:
            logger.error("No .hex found in _gen")
            return False
        else:
            # there should only be 1 hex file. Or there will be test_PVER.hex and PVER.hex.
            # In that case take any is fine
            hex_file = os.path.join(hexmod_folder, hex_files[0])

        if not path.isfile(hex_file):
            logger.error("No .hex found in _gen")
            return False

        return True

    def check_a2l_bin(name) -> bool:
        """Check for existence of .a2l in _bin"""
        swb_folder = path.join(bin_folder, "swb")
        logger.debug("Searching .a2l file in _bin")

        # if PVER is a CB PVER, .a2l wont exist
        if name.upper().startswith("CB"):
            logger.error(" *** This is a CB PVER, .a2l wont exist ***")
            return True

        if not path.isdir(swb_folder):
            logger.error(r"_bin\swb folder not found. PVER not valid")
            return False

        # check for either test_PVER.a2l or PVER.a2l
        a2l_files = glob.glob1(swb_folder, f"*{name}*.a2l")

        # remove all invalid suffix
        for f in a2l_files:
            for suffix in excluded_suffix:
                if suffix in f:
                    a2l_files.remove(f)

        if len(a2l_files) == 0:
            logger.info("No .a2l found in _bin..")
            return False
        else:
            # there should only be 1 hex file. Or there will be test_PVER.hex and PVER.hex.
            # In that case take any is fine
            a2l_file = os.path.join(swb_folder, a2l_files[0])

        if not path.isfile(a2l_file):
            logger.error("No .a2l found in _bin..")
            return False

        return True

    def check_a2l_gen(name) -> bool:
        """Check for existence of .a2l in _gen"""
        asap2_folder = path.join(gen_folder, "swb", "module", "asap2")
        logger.critical("Try searching in _gen..")

        if not path.isdir(asap2_folder):
            logger.error(r"_gen\swb\module\asap2 folder not found. PVER not valid")
            return False

        # check for either test_PVER.a2l or PVER.a2l
        a2l_files = glob.glob1(asap2_folder, f"*{name}*.a2l")

        # remove all invalid suffix
        for f in a2l_files:
            for suffix in excluded_suffix:
                if suffix in f:
                    a2l_files.remove(f)

        if len(a2l_files) == 0:
            logger.error("No .a2l found in _gen..")
            return False
        else:
            # there should only be 1 hex file. Or there will be test_PVER.hex and PVER.hex.
            # In that case take any is fine
            a2l_file = os.path.join(asap2_folder, a2l_files[0])

        if not path.isfile(a2l_file):
            logger.error("No .a2l found in _gen..")
            return False

        return True

    if not path.isdir(pver_root):
        return False

    gen_folder = path.join(pver_root, "_gen")
    bin_folder = path.join(pver_root, "_bin")
    out_folder = path.join(pver_root, "_out")
    sw_config = path.join(pver_root, "MAK", "MakeWare", "swbuild_config.xml")

    if not path.isdir(out_folder) or not path.isdir(bin_folder):
        # if _out or _bin not exist, PVER definitely not built
        logger.error("_out or _bin folder not exist, this PVER is not built")
        return False

    if not path.isfile(sw_config):
        logger.error("swbuild_config.xml not found, check if this is a valid PVER")
        return False

    pver_name = pver_root.replace("\\", "/").split("/")[-1]

    tree = etree.parse(sw_config)
    root = tree.getroot()
    prj_name_node = root.xpath(
        "//ABLOCKS//ABLOCK//SDGS//SDG[@GID='SWBProjectConfiguration']//SD[@GID='PRJ_NAME']")[0]
    if prj_name_node is not None and prj_name_node.text is not None \
            and len(prj_name_node.text.strip()) > 0:
        pver_name = prj_name_node.text
        logger.debug("Project name is set in swbuild_config.xml")
    logger.debug("Project name: " + pver_name)

    if not check_hex_bin(pver_name):
        if not check_hex_gen(pver_name):
            logger.error(" => This PVER has no hex file, hence it is not a built PVER")
            return False

    if not check_a2l_bin(pver_name):
        if not check_a2l_gen(pver_name):
            logger.error(" =>This PVER has no a2l file, hence it is not a built PVER")
            return False
    logger.debug("=> This is a built PVER")
    return True

def is_modified(modified_path, size, crc):
    """
    Check the if the file is modified.
    """

    def check_md5(file, md5):
        """
        Compare md5 hash of file with provided MD5.
        """
        import hashlib
        return hashlib.md5(file).hexdigest().upper() == md5

    try:
        file_size = os.path.getsize(modified_path)
        if file_size != int(size):
            return True
    except FileNotFoundError:
        logger.warning("File not found: " + modified_path)
        raise FileNotFoundError("File not found: " + modified_path)
    except ValueError:
        logger.warning("Size of " + modified_path + ":\"" + size + "\" is not an integer")
        return False

    with open(modified_path, "rb") as file:
        check = file.read()
    res = check_md5(check, crc)
    return False if res else True


if __name__ == "__main__":
    pass
    # b, d = trigger_tealeaves(
    #     r"C:\Users\PHB6HC\Desktop\selectable_module_build\test\EVC1013P01C1929_XD50_EP",
    #      version="0.9.4.1")
    # print(d)
