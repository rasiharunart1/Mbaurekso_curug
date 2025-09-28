import time
from typing import Dict, List, Any, Optional

class AlertManager:
    def __init__(self, cfg: dict, db=None):
        self.cfg = cfg
        self.db = db
        self.last_fire: Dict[str, float] = {}
        self.occupancy_history: List[tuple] = []
        self.alerts: List[Dict[str, Any]] = []
        self.keep_max = 120

    def _cooldown_ok(self, key: str) -> bool:
        cd = self.cfg.get("cooldown_sec", 30)
        now = time.time()
        last = self.last_fire.get(key, 0)
        if now - last >= cd:
            self.last_fire[key] = now
            return True
        return False

    def add_alert(self, atype: str, msg: str, occupancy: Optional[int] = None, meta: Optional[dict] = None):
        a = {
            "time": time.strftime("%H:%M:%S"),
            "type": atype,
            "message": msg,
            "meta": meta or {},
            "occupancy": occupancy
        }
        self.alerts.append(a)
        if len(self.alerts) > self.keep_max:
            self.alerts.pop(0)
        if self.db:
            try:
                self.db.insert_alert(atype, msg, occupancy, meta)
            except Exception:
                pass
        return a

    def record_occ(self, occ: int):
        now = time.time()
        self.occupancy_history.append((now, occ))
        self.occupancy_history = [x for x in self.occupancy_history if now - x[0] <= 600]

    def check_capacity(self, occ: int):
        cap = self.cfg.get("capacity_threshold", -1)
        if cap > 0 and occ > cap and self._cooldown_ok("capacity"):
            self.add_alert("CAPACITY", f"Occupancy {occ} > {cap}", occupancy=occ)

    def check_surge(self):
        need = self.cfg.get("surge_count", 0)
        interval = self.cfg.get("surge_interval_sec", 60)
        if need <= 0 or not self.occupancy_history:
            return
        now = time.time()
        current = self.occupancy_history[-1][1]
        baseline = None
        for t,o in reversed(self.occupancy_history):
            if now - t >= interval:
                baseline = o
                break
        if baseline is None:
            return
        delta = current - baseline
        if delta >= need and self._cooldown_ok("surge"):
            self.add_alert("SURGE", f"+{delta} in {interval}s", occupancy=current, meta={"delta": delta})

    def check_dwell(self, tracks: dict):
        th = self.cfg.get("dwell_time_sec", 0)
        if th <= 0:
            return
        for tid,tr in tracks.items():
            if tr["inside"] and tr["dwell_sec"] >= th:
                key = f"dwell_{tid}"
                if self._cooldown_ok(key):
                    self.add_alert("DWELL", f"Track {tid} {tr['dwell_sec']}s >= {th}", meta={"track_id": tid})

    def evaluate(self, occ: int, tracks: dict, summary: dict, snapshot_cb=None):
        self.record_occ(occ)
        self.check_capacity(occ)
        self.check_surge()
        self.check_dwell(tracks)
        if snapshot_cb:
            snapshot_cb(summary)

    def recent(self, last_n=30):
        return self.alerts[-last_n:]

    def clear(self):
        self.alerts.clear()