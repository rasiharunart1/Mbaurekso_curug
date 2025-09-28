import numpy as np
from PIL import ImageGrab
try:
    import mss
    HAS_MSS = True
except Exception:
    HAS_MSS = False

class ScreenCapturer:
    def __init__(self, use_mss=True):
        self.use_mss = use_mss and HAS_MSS
        self._sct = None
    def grab(self, region):
        if not region:
            return None
        l,t,r,b = region
        w,h = (r-l),(b-t)
        if self.use_mss:
            try:
                if self._sct is None:
                    self._sct = mss.mss()
                mon = {"left":l,"top":t,"width":w,"height":h}
                arr = np.array(self._sct.grab(mon))
                import cv2
                return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
            except Exception:
                self.use_mss = False
        im = ImageGrab.grab(bbox=(l,t,r,b))
        arr = np.array(im)
        import cv2
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)