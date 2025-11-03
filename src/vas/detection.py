"""
Fungsi deteksi sederhana: kembalikan list bbox person.
Tanpa tracking.
"""
from typing import List, Dict
from .config import MODEL_CONFIG, RUNTIME_CONFIG, CLASS_PERSON
def detect_persons(model, frame):
    from .config import MODEL_CONFIG
    conf = MODEL_CONFIG.get("confidence_threshold", 0.25)
    iou = MODEL_CONFIG.get("iou_threshold", 0.45)
    imgsz = MODEL_CONFIG.get("input_size", 640)
    
    # Don't pass half parameter - let model use its loaded precision
    results = model(frame, conf=conf, iou=iou, imgsz=imgsz, verbose=False)
    
    detections = []
    if results and len(results) > 0:
        for det in results[0].boxes:
            cls = int(det.cls[0])
            if cls == 0:  # person class
                bbox = det.xyxy[0].cpu().numpy().astype(int)
                detections.append({
                    "bbox": tuple(bbox),
                    "confidence": float(det.conf[0])
                })
    return detections