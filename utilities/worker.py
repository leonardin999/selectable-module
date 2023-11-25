"""

"""

import sys
import traceback

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread, supported signals:
        log
            str
        done
        error
            tuple (exec type, value, traceback.format_exc() )
        result
            object data returned from processing, anything
        progress
            int indicating % progress
    """

    finished = Signal(str)
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(int)
    log = Signal(str)


class Worker(QRunnable):
    """
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    """

    def __init__(self, function, *args, **kwargs):
        super().__init__()

        # Store constructor arguments (re-used for processing)
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        if "progress_callback" in self.kwargs:
            self.kwargs["progress_callback"] = self.signals.progress

    @Slot()
    def run(self):
        """Initialise the runner function with passed args, kwargs."""
        try:
            result = self.function(
                *self.args, **self.kwargs
            )
        except:
            traceback.print_exc()
            exec_type, value = sys.exc_info()[:2]
            # noinspection PyUnresolvedReferences
            self.signals.error.emit((exec_type, value, traceback.format_exc()))
        else:
            # noinspection PyUnresolvedReferences
            self.signals.result.emit(result)
        finally:
            # noinspection PyUnresolvedReferences
            self.signals.finished.emit()
