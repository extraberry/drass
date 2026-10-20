"""Run blocking API calls off the UI thread."""
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

_live: set = set()


class Bus(QObject):
    session_expired = Signal()


bus = Bus()


class _Job(QObject):
    ok = Signal(object)
    err = Signal(object)
    progress = Signal(int)

    def __init__(self, on_ok, on_err, on_progress):
        super().__init__()
        self._ok, self._err = on_ok, on_err
        self.ok.connect(self._handle_ok)
        self.err.connect(self._handle_err)
        if on_progress:
            self.progress.connect(on_progress)

    @Slot(object)
    def _handle_ok(self, result):
        _live.discard(self)
        if self._ok:
            self._ok(result)

    @Slot(object)
    def _handle_err(self, exc):
        _live.discard(self)
        if getattr(exc, "code", "") == "SESSION_EXPIRED":
            bus.session_expired.emit()
            return
        if self._err:
            self._err(exc)


class _Task(QRunnable):
    def __init__(self, job, fn, with_progress):
        super().__init__()
        self.job, self.fn, self.with_progress = job, fn, with_progress

    def run(self):
        try:
            res = self.fn(self.job.progress.emit) if self.with_progress else self.fn()
            self.job.ok.emit(res)
        except Exception as exc:   # noqa: BLE001
            self.job.err.emit(exc)


def run_async(fn, on_ok=None, on_err=None, on_progress=None):
    """fn() runs in a worker thread; on_ok/on_err run in the UI thread. If on_progress is given, fn(report)."""
    job = _Job(on_ok, on_err, on_progress)
    _live.add(job)
    QThreadPool.globalInstance().start(_Task(job, fn, on_progress is not None))
