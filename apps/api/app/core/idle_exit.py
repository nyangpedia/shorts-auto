"""Stop the server once the browser window is gone (the double-click launcher sets SHORTS_AUTO_EXIT=1).

The page pings /api/heartbeat while it is open. The server exits when the pings stop for IDLE_SECONDS and no
request is still being worked on (a render keeps going even if the window was closed). It never exits before
the first ping, so servers started by hand or by tests stay up.
"""
from __future__ import annotations

import os
import threading
import time

IDLE_SECONDS = 900  # browsers throttle or put hidden tabs to sleep (3 minutes was too short: the server died under an open page)
CHECK_SECONDS = 10
STRIKES = 3  # idle on three checks in a row, so a PC just back from sleep gets a moment to ping


class IdleExit:
    def __init__(self, enabled: bool, idle_seconds: float = IDLE_SECONDS, exit=os._exit, clock=time.monotonic):
        self.enabled, self.idle_seconds, self._exit, self._clock = enabled, idle_seconds, exit, clock
        self._lock = threading.Lock()
        self._last: float | None = None
        self._inflight = 0
        self._strikes = 0

    def beat(self) -> None:
        self._last = self._clock()

    def begin(self) -> None:
        with self._lock:
            self._inflight += 1

    def end(self) -> None:
        with self._lock:
            self._inflight -= 1
        self._last = self._clock()  # the idle countdown starts when the work finishes

    def idle(self) -> bool:
        return self._last is not None and self._inflight == 0 and self._clock() - self._last > self.idle_seconds

    def check(self) -> None:
        self._strikes = self._strikes + 1 if self.idle() else 0
        if self._strikes >= STRIKES:
            self._exit(0)

    def watch(self) -> None:
        def loop():
            while True:
                time.sleep(CHECK_SECONDS)
                self.check()
        threading.Thread(target=loop, daemon=True, name="idle-exit").start()
