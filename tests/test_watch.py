import threading
import time
import unittest

from ai_docs.cli_watch import _Debouncer


class WatchDebouncerTests(unittest.TestCase):
    def test_events_during_running_regen_schedule_one_followup_without_overlap(self):
        lock = threading.Lock()
        first_started = threading.Event()
        release_first = threading.Event()
        second_done = threading.Event()
        errors = []
        calls = 0
        active = 0
        peak_active = 0

        def regenerate():
            nonlocal calls, active, peak_active
            with lock:
                calls += 1
                call_no = calls
                active += 1
                peak_active = max(peak_active, active)
            try:
                if call_no == 1:
                    first_started.set()
                    if not release_first.wait(2.0):
                        errors.append("first regeneration was not released")
                else:
                    second_done.set()
            finally:
                with lock:
                    active -= 1

        debouncer = _Debouncer(0.01, regenerate)
        try:
            debouncer.bump()
            self.assertTrue(first_started.wait(1.0))
            debouncer.bump()
            debouncer.bump()
            debouncer.bump()
            time.sleep(0.03)
            release_first.set()
            self.assertTrue(second_done.wait(1.0))
            time.sleep(0.05)
        finally:
            debouncer.cancel()

        self.assertEqual(errors, [])
        with lock:
            self.assertEqual(calls, 2)
            self.assertEqual(peak_active, 1)


if __name__ == "__main__":
    unittest.main()
