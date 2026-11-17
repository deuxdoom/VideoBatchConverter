"""Debounced queue previews sharing completed samples with the batch preflight."""

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .profiles import validate_settings
from .queue_widgets import INFO_ROLE, STATE_ROLE, TIME_ESTIMATE_ROLE, ESTIMATE_ROLE
from .size_estimator import SizeEstimateWorker, estimate_key


class TimePreview(QObject):
    idle = pyqtSignal()

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.worker = None
        self.generation = 0
        self.requested = False
        self.failures = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self.start)

    def pause(self):
        self.timer.stop()
        self.requested = False
        self.generation += 1
        if self.worker is not None:
            self.worker.cancel()

    def schedule(self):
        self.pause()
        owner = self.owner
        if owner.converting or owner.scanning or owner.preflighting or owner._close_pending:
            return
        settings = owner.get_current_settings()
        error = validate_settings(settings)
        for path, item in owner.queue_items.items():
            if (item.data(INFO_ROLE) or {}).get('_scan_pending') or (item.data(INFO_ROLE) or {}).get('_extra_pending') or (item.data(INFO_ROLE) or {}).get('_scan_error'):
                continue
            result = {'state': 'pending'}
            try:
                if error:
                    raise ValueError(error)
                key = estimate_key(path, settings)
                cached = owner.estimate_cache.get(key, {})
                result = cached if cached.get('estimated_seconds') is not None else self.failures.get(key, result)
            except (OSError, ValueError) as exc:
                result = {'state': 'unknown', 'error': str(exc)}
            item.setData(TIME_ESTIMATE_ROLE, result)
            item.setData(ESTIMATE_ROLE, result)
            self.update_compatibility_state(item, result)
            owner.update_item_text(item)
        owner.update_time_summary()
        self.requested = any((item.data(TIME_ESTIMATE_ROLE) or {}).get('state') == 'pending'
                             for item in owner.queue_items.values())
        if self.requested:
            self.timer.start(700)

    def start(self):
        owner = self.owner
        if (not self.requested or self.worker is not None or owner.converting or owner.scanning
                or owner.preflighting or owner._close_pending):
            return
        jobs = [(path, item.data(INFO_ROLE)) for path, item in owner.queue_items.items()
                if (item.data(TIME_ESTIMATE_ROLE) or {}).get('state') == 'pending']
        if not jobs:
            return
        self.requested = False
        self.worker_generation = self.generation
        self.worker = SizeEstimateWorker(jobs, owner.get_current_settings(), owner.estimate_cache,
                                         self, skip_existing=False)
        self.worker.progress.connect(self.progress)
        self.worker.finished.connect(self.finished)
        self.worker.start()

    def progress(self, path, result, completed, total):
        owner = self.owner
        item = owner.queue_items.get(path)
        if item is None or self.worker_generation != self.generation:
            return
        if result.get('estimated_seconds') is None and result.get('state') != 'working':
            try:
                self.failures[estimate_key(path, self.worker.settings)] = dict(result)
            except OSError:
                pass
        item.setData(TIME_ESTIMATE_ROLE, result)
        item.setData(ESTIMATE_ROLE, result)
        self.update_compatibility_state(item, result)
        owner.update_item_text(item)
        owner.update_time_summary()

    def update_compatibility_state(self, item, result):
        from .queue_widgets import PATH_ROLE
        state = item.data(STATE_ROLE)
        if result.get('state') == 'blocked' and state == '대기':
            self.owner.set_item_state(item.data(PATH_ROLE), '설정 확인')
        elif result.get('state') != 'blocked' and state == '설정 확인':
            self.owner.set_item_state(item.data(PATH_ROLE), '대기')

    def finished(self):
        worker = self.worker
        # Completed samples remain useful even if a later setting change cancelled
        # the rest. Never repopulate a cache after its queue has been cleared.
        for result in worker.results:
            if result.get('path') in self.owner.queue_items and result.get('key') and result['state'] in ('safe', 'risk'):
                self.owner.estimate_cache[result['key']] = dict(result)
        self.worker = None
        worker.deleteLater()
        self.idle.emit()
        if self.requested and not self.timer.isActive():
            self.timer.start(0)
