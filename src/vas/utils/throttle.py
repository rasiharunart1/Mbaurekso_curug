import time
class Throttle:
    def __init__(self, interval):
        self.interval = interval
        self._last = 0
    def ready(self):
        now = time.time()
        if now - self._last >= self.interval:
            self._last = now
            return True
        return False