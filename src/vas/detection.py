"""
Fungsi deteksi sederhana: kembalikan list bbox person.
Tanpa tracking.
"""
from typing import List, Dict
from .config import MODEL_CONFIG, RUNTIME_CONFIG, CLASS_PERSON

def detect_persons(model, frame):
    conf = MODEL_CONFIG["confidence_threshold"]
    iou = MODEL_CONFIG["iou_threshold"]
    imgsz = RUNTIME_CONFIG["imgsz"]
    half = (MODEL_CONFIG.get("device","cpu").startswith("cuda") and RUNTIME_CONFIG.get("use_half", True))
    results = model(frame, conf=conf, iou=iou, imgsz=imgsz, half=half, verbose=False)
    detections: List[Dict] = []
    for r in results:
        boxes = getattr(r, "boxes", None)
        if boxes is None: 
            continue
        for box in boxes:
            cls = int(box.cls[0])
            if cls != CLASS_PERSON:
                continue
            score = float(box.conf[0])
            if score < MODEL_CONFIG["detection_confidence"]:
                continue
            x1,y1,x2,y2 = box.xyxy[0].cpu().numpy()
            detections.append({
                "bbox":[int(x1),int(y1),int(x2),int(y2)],
                "conf":score
            })
    return detections