"""
TODO: insert docstring
"""
import cProfile
import os.path
import pstats
from functools import wraps
from typing import Callable
from PySide6.QtCore import QObject, Signal

from utilities.log import get_logger

logger = get_logger(__name__)


class SyncSignal(QObject):
    """
    SyncSignal is a QObject that allows the MainWindow to emit signals
    """
    sync = Signal(str)


PATH = ""


def sync(path):
    """
    Sync the Profiling path
    """
    global PATH
    PATH = path


profiler_signal = SyncSignal()
profiler_signal.sync.connect(sync)


def profiling(
        output_file: str = None, sort_by: str = "cumulative",
        lines_to_print: int = None, strip_dirs: bool = False
) -> Callable:
    """Profiler Decorator , which can be used to profile a function.

    Args:
        output_file(str, optional): The file to write the profiling results to.
        If only name of the file is given, it's saved in the current directory.
        If it's None, the name of the decorated function is used, Defaults to None.

        sort_by: Sorting criteria for the Stats object.
        For a list of valid string and SortKey refer to:
            https://docs.python.org/3/library/profile.html#pstats.Stats.sort_stats.
            Defaults to "cumulative".

        lines_to_print(int, optional): The number of lines to print from the profiling results.
        Default (None) is for all the lines. This is useful in reducing the size of the printout,
         especially that sorting by 'cumulative', the time consuming operations are printed toward
         the top of the file. Defaults to None.

        strip_dirs(bool, optional): Whether to strip the directories from the profiling results.
        This is also useful inreducing the size of the printout. Defaults to False.

    Returns:
        None: Profile of the decorated function
    """

    def inner(func):
        """
        Args:
            func: The function to be profiled.
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            """
            Args:
                args: The positional arguments of the function.
                kwargs: The keyword arguments of the function.
            """
            logger.critical(f"Profiling {func.__name__}")
            _output_file = output_file or func.__name__ + ".prof"
            profile = cProfile.Profile()
            profile.enable()
            return_value = func(*args, **kwargs)
            profile.disable()
            _output_dir = os.path.join(PATH, 'profs')
            if not os.path.isdir(_output_dir):
                os.makedirs(_output_dir)
            _output_path = os.path.join(_output_dir, _output_file)
            profile.dump_stats(_output_path)

            with open(_output_path, "w", encoding='utf-8') as file:
                ps = pstats.Stats(profile, stream=file)
                if strip_dirs:
                    ps.strip_dirs()
                if isinstance(sort_by, (tuple, list)):
                    ps.sort_stats(*sort_by)
                else:
                    ps.sort_stats(sort_by)
                ps.print_stats(lines_to_print)
            return return_value

        return wrapper

    return inner
