from typing import List, Dict, Any
from .config import MODEL_CONFIG, RUNTIME_CONFIG, TRACKING_CONFIG, PERSON_CLASSES

def run_inference(model, frame):
    conf = MODEL_CONFIG["confidence_threshold"]
    iou = MODEL_CONFIG["iou_threshold"]
    imgsz = RUNTIME_CONFIG["imgsz"]
    half = (MODEL_CONFIG.get("device","cpu").startswith("cuda") and RUNTIME_CONFIG.get("use_half", True))
    results = model(frame, conf=conf, iou=iou, imgsz=imgsz, half=half, verbose=False)
    detections: List[Dict[str, Any]] = []
    for r in results:
        boxes = getattr(r, "boxes", None)
        if boxes is None:
            continue
        for box in boxes:
            cls = int(box.cls[0])
            if cls not in PERSON_CLASSES:
                continue
            cconf = float(box.conf[0])
            if cconf < MODEL_CONFIG["detection_confidence"]:
                continue
            x1,y1,x2,y2 = box.xyxy[0].cpu().numpy()
            w,h = (x2-x1),(y2-y1)
            if w < TRACKING_CONFIG["min_detection_size"] or h < TRACKING_CONFIG["min_detection_size"]:
                continue
            detections.append({
                "bbox": [int(x1), int(y1), int(x2), int(y2)],
                "class": cls,
                "confidence": cconf
            })
    return detections