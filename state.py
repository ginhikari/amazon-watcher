import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from models import PurchaseState, SafetyError

class StateStore:
    def __init__(self, path):
        self.path = Path(path)

    def load_state(self):
        if not self.path.exists():
            return PurchaseState()
        try:
            data = json.loads(self.path.read_text())
            if set(data) != {'purchased_asins', 'attempting_purchase'}:
                raise ValueError('Unexpected state fields')
            if not isinstance(data['purchased_asins'], list) or any(not isinstance(x, str) for x in data['purchased_asins']):
                raise ValueError('Invalid ASIN list')
            if type(data['attempting_purchase']) is not bool:
                raise ValueError('Invalid purchase flag')
            return PurchaseState(**data)
        except (ValueError, TypeError, OSError) as exc:
            raise SafetyError('Cannot read purchase state; manual review required') from exc

    def save_state(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix='.state-')
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(vars(state), stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def already_purchased(self, asin):
        return asin in self.load_state().purchased_asins

    def guard(self, asin):
        state = self.load_state()
        if asin in state.purchased_asins:
            raise SafetyError('Target has already been purchased.')
        if state.attempting_purchase:
            raise SafetyError('Previous execution stopped during a purchase attempt. Manual review required.')

    def mark_purchase_started(self):
        state = self.load_state()
        if state.attempting_purchase:
            raise SafetyError('Purchase already in progress')
        state.attempting_purchase = True
        self.save_state(state)

    def mark_purchase_finished(self):
        state = self.load_state()
        state.attempting_purchase = False
        self.save_state(state)

    def mark_as_purchased(self, asin):
        state = self.load_state()
        if asin not in state.purchased_asins:
            state.purchased_asins.append(asin)
        state.attempting_purchase = False
        self.save_state(state)

    @contextmanager
    def exclusive(self):
        # Kernel lock is released on process exit; do not delete its inode.
        import fcntl
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(self.path) + '.lock', 'a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise SafetyError('Another watcher is running') from exc
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
