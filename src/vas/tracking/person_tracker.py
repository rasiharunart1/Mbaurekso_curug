import math
import time
from collections import deque
from typing import Dict, List, Any, Tuple
from ..config import TRACKING_CONFIG

def point_in_poly(pt, poly):
    if not poly:
        return False
    x,y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1,y1 = poly[i]
        x2,y2 = poly[(i+1)%n]
        cond = ((y1>y)!=(y2>y)) and (x < (x2 - x1)*(y - y1)/((y2 - y1) if (y2 - y1)!=0 else 1e-6) + x1)
        if cond:
            inside = not inside
    return inside

def point_in_rect(pt, rect):
    if not rect:
        return False
    x,y = pt
    x1,y1,x2,y2 = rect
    return (x1 <= x <= x2) and (y1 <= y <= y2)

class PersonTracker:
    """
    Tracking sederhana + occupancy + dwell.
    """
    def __init__(self):
        self.next_id = 1
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.unique_count = 0
        self._inside_ids = set()
        self._prev_inside_ids = set()

    def update(self, detections: List[Dict[str, Any]]):
        for tr in self.tracks.values():
            tr["age"] += 1
            tr["_updated"] = False

        used = set()
        for det in detections:
            x1,y1,x2,y2 = det["bbox"]
            cx,cy = (x1+x2)//2, (y1+y2)//2
            best_id = None
            best_dist = 1e9
            for tid,tr in self.tracks.items():
                if tid in used:
                    continue
                tx1,ty1,tx2,ty2 = tr["bbox"]
                tcx,tcy = (tx1+tx2)//2, (ty1+ty2)//2
                d = math.hypot(cx - tcx, cy - tcy)
                if d < best_dist and d <= TRACKING_CONFIG["max_match_distance"]:
                    best_dist = d
                    best_id = tid
            if best_id is None:
                tid = self.next_id; self.next_id += 1
                self.unique_count += 1
                self.tracks[tid] = {
                    "bbox": det["bbox"],
                    "class": det["class"],
                    "confidence": det["confidence"],
                    "path": deque(maxlen=64),
                    "age": 0,
                    "missed": 0,
                    "_updated": True,
                    "enter_time": None
                }
                self.tracks[tid]["path"].append((cx,cy))
                used.add(tid)
            else:
                tr = self.tracks[best_id]
                tr["bbox"] = det["bbox"]
                tr["class"] = det["class"]
                tr["confidence"] = det["confidence"]
                tr["age"] = 0
                tr["missed"] = 0
                tr["_updated"] = True
                tr["path"].append((cx,cy))
                used.add(best_id)

        stale = [tid for tid,tr in self.tracks.items() if tr["age"] > TRACKING_CONFIG["max_track_lost_frames"]]
        for tid in stale:
            self.tracks.pop(tid, None)

    def update_occupancy(self, rect=None, poly=None, dwell_exit_callback=None):
        self._prev_inside_ids = set(self._inside_ids)
        now = time.time()
        inside = set()
        for tid,tr in self.tracks.items():
            x1,y1,x2,y2 = tr["bbox"]
            cx,cy = (x1+x2)//2,(y1+y2)//2
            ins = False
            if poly and len(poly)>=3:
                ins = point_in_poly((cx,cy), poly)
            elif rect:
                ins = point_in_rect((cx,cy), rect)
            if ins:
                inside.add(tid)
                if tr.get("enter_time") is None:
                    tr["enter_time"] = now

        # Detect exit (untuk dwell session logging)
        exited = self._prev_inside_ids - inside
        if exited and dwell_exit_callback:
            for tid in exited:
                tr = self.tracks.get(tid)
                if tr and tr.get("enter_time"):
                    dwell_sec = int(now - tr["enter_time"])
                    dwell_exit_callback(tid, tr["enter_time"], now, dwell_sec)

        self._inside_ids = inside

    def get_current_occupancy(self):
        return len(self._inside_ids)

    def get_longest_dwell(self):
        now = time.time()
        longest = 0
        for tid in self._inside_ids:
            tr = self.tracks.get(tid)
            if tr and tr.get("enter_time"):
                d = int(now - tr["enter_time"])
                if d > longest:
                    longest = d
        return longest

    def get_summary(self):
        return {
            "unique": self.unique_count,
            "current": self.get_current_occupancy(),
            "longest_dwell": self.get_longest_dwell()
        }

    def get_tracks_status(self):
        now = time.time()
        out = {}
        for tid,tr in self.tracks.items():
            inside = (tid in self._inside_ids)
            dwell = 0
            if inside and tr.get("enter_time"):
                dwell = int(now - tr["enter_time"])
            out[tid] = {
                "bbox": tr["bbox"],
                "class": tr["class"],
                "confidence": tr["confidence"],
                "path": list(tr["path"]),
                "inside": inside,
                "dwell_sec": dwell
            }
        return out

    def reset(self):
        self.__init__()