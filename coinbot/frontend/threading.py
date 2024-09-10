import sys
import traceback

from PyQt5.QtCore import *


class SeparateThreadWorker(QRunnable):
    """ The SeparateThreadWorker class makes it convenient to run some functions in a separate threat so as not to
    block, for example, the main GUI threat. An instance of this class gets constructed by providing it with a
    function, and possibly some args or kwargs.

    EXAMPLE:

        def get_data(object):
            data = object.long_function_that_gets_data()
        return data

        threadpool = QThreadPool.globalInstance()
        worker = SeparateThreadWorker(fn=get_data, object=object_instance)
        worker.signals.result.connect(lambda res: print(res))
        worker.signals.error.connect(lambda err: print(err))
        threadpool.start(worker)

    """

    class WorkerSignals(QObject):
        result = pyqtSignal(object)
        finished = pyqtSignal()
        error = pyqtSignal(tuple)

    def __init__(self, fn, *args, **kwargs):
        """ Initialize a worker by providing it with the function to be executed, and possibly args and kwargs that
        get passed onto the offloaded function. """
        super(SeparateThreadWorker, self).__init__()

        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = SeparateThreadWorker.WorkerSignals()

    @pyqtSlot()
    def run(self):
        """ Run the function with it's specified args and kwargs in a separate thread. Different signals with possibly
        some data can be emitted by the thread runner. """
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
