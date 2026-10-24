"""The loop that reads the queue every NOTIFY_POLL_SECONDS, in a thread of the service's own process.

It needs the process to keep running and to have CPU between requests: on Cloud Run, at least one instance with
CPU always allocated (README, "What the owner sets up"). Two instances reading at once push nothing twice, because
each push takes its mark first (store.py).
"""

import logging
import threading

log = logging.getLogger(__name__)


class Poller:
    def __init__(self, notifier, interval_s):
        self.notifier = notifier
        self.interval_s = interval_s
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="notify-poller", daemon=True)
            self._thread.start()
        return self

    def stop(self, timeout=None):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self):
        while not self._stop.is_set():
            try:
                self.notifier.tick()
            except Exception:  # one bad read must not end the loop
                log.exception("a read of the queue failed")
            self._stop.wait(self.interval_s)
