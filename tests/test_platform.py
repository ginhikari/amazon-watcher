import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from models import SafetyError
from state import StateStore


class PlatformTests(unittest.TestCase):
    def test_lock_across_processes_and_release(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / 'state.json')
            script = '''
import sys
from state import StateStore
from models import SafetyError
try:
    with StateStore(sys.argv[1]).exclusive():
        pass
except SafetyError:
    sys.exit(7)
'''
            with store.exclusive():
                result = subprocess.run([sys.executable, '-c', script, str(store.path)], capture_output=True)
                self.assertEqual(result.returncode, 7, result.stderr)
            result = subprocess.run([sys.executable, '-c', script, str(store.path)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_windows_lock_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / 'state.json')
            api = SimpleNamespace(locking=Mock(), LK_NBLCK=2, LK_UNLCK=0)
            with patch('state.os.name', 'nt'), patch.dict(sys.modules, msvcrt=api):
                with store.exclusive():
                    self.assertEqual(api.locking.call_count, 1)
            self.assertEqual([call.args[1:] for call in api.locking.call_args_list], [(2, 1), (0, 1)])
            self.assertEqual(Path(str(store.path) + '.lock').read_bytes(), b'\0')

    def test_windows_lock_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / 'state.json')
            api = SimpleNamespace(locking=Mock(side_effect=OSError('locked')), LK_NBLCK=2, LK_UNLCK=0)
            with patch('state.os.name', 'nt'), patch.dict(sys.modules, msvcrt=api):
                with self.assertRaises(SafetyError):
                    with store.exclusive():
                        self.fail('Lock failure must prevent entry')
            self.assertEqual(api.locking.call_count, 1)

    def test_failed_replace_preserves_state(self):
        with tempfile.TemporaryDirectory() as directory:
            store = StateStore(Path(directory) / 'state.json')
            store.mark_as_purchased('B012345678')
            previous = store.path.read_bytes()
            with patch('state.os.replace', side_effect=PermissionError('busy')):
                with self.assertRaises(PermissionError): store.mark_purchase_started()
            self.assertEqual(store.path.read_bytes(), previous)
            self.assertEqual(list(store.path.parent.glob('.state-*')), [])
