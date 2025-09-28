from ultralytics import YOLO
from .config import MODEL_CONFIG, RUNTIME_CONFIG
import torch

def resolve_device():
    dev = MODEL_CONFIG.get("device", "auto")
    if dev == "auto":
        try:
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"
    return dev

def load_model():
    m = YOLO(MODEL_CONFIG["model_path"])
    device = resolve_device()
    m.to(device)
    if device.startswith("cuda") and RUNTIME_CONFIG.get("use_half", True):
        try:
            m.model.half()
        except Exception:
            pass
    MODEL_CONFIG["device"] = device
    return m