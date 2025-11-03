import json
from pathlib import Path

SETTINGS_FILE = Path("settings.json")

DEFAULT_SETTINGS = {
    "model": {
        "model_path": "vas//models/yolov8n.pt",
        "confidence_threshold": 0.35,
        "iou_threshold": 0.50,
        "detection_confidence": 0.30,
        "device": "auto"
    },
    "runtime": {
        "imgsz": 640,
        "use_half": True,
        "detection_stride": 1,
        "flush_frames": 2,
        "use_mss_screen_capture": True
    },
    "input": {
        "type": "screen",       # screen | webcam | network
        "webcam_index": 0,
        "stream_url": "",
        "screen_region": None
    },
    "aoi": {
        "mode": "rect",         # rect | poly
        "rect": None,           # [x1,y1,x2,y2]
        "polygon": []           # [[x,y],...]
    },
    "alerts": {
        "enabled": True         # toggle dari UI
    },
    "database": {
        "enable": False,
        "type": "mysql",
        "host": "localhost",
        "port": 3306,
        "user": "vas_user",
        "password": "your_password_here",
        "name": "vas_db"
    }
}

def deep_update(base, new):
    for k,v in new.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            deep_update(base[k], v)
        else:
            base[k] = v

class Settings:
    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULT_SETTINGS))
        self._load()
    def _load(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    disk = json.load(f)
                deep_update(self.data, disk)
            except Exception:
                pass
    def save(self):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass

settings = Settings()

MODEL_CONFIG = settings.data["model"]
RUNTIME_CONFIG = settings.data["runtime"]
INPUT_CONFIG = settings.data["input"]
AOI_CONFIG = settings.data["aoi"]
ALERT_CONFIG = settings.data["alerts"]
DB_CONFIG = settings.data["database"]

CLASS_PERSON = 0