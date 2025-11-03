import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
import numpy as np
from PIL import Image, ImageTk
import pyautogui

from .config import (
    settings, MODEL_CONFIG, RUNTIME_CONFIG, INPUT_CONFIG,
    AOI_CONFIG, ALERT_CONFIG, DB_CONFIG
)
from .model_loader import load_model
from .detection import detect_persons
from .utils.screen_capture import ScreenCapturer
from .db_manager import DBManager

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Person Counter (AOI Only)")
        self.root.geometry("1200x800")
        self.root.configure(bg="#252525")

        self.model = load_model()

        # Input
        self.capture_region = INPUT_CONFIG.get("screen_region")
        self.input_type = INPUT_CONFIG.get("type","screen")
        self.webcam_index = INPUT_CONFIG.get("webcam_index",0)
        self.stream_url = INPUT_CONFIG.get("stream_url","")
        self.cap = None
        self.cap_lock = threading.Lock()

        # AOI
        self.aoi_mode = AOI_CONFIG.get("mode","rect")
        self.aoi_rect = AOI_CONFIG.get("rect")
        self.aoi_poly = AOI_CONFIG.get("polygon",[])
        self._drawing_rect = False
        self._rect_start = None
        self._drawing_poly = False
        self._poly_canvas_pts = []

        # Alert
        self.alert_enabled = ALERT_CONFIG.get("enabled", True)
        self.last_alert_state = None  # None | occupied | clear

        # DB
        self.db = DBManager(status_callback=self.on_db_status)

        # Runtime flags
        self.is_preview = False
        self.is_running = False

        # Frame buffer
        self.screen_cap = ScreenCapturer(RUNTIME_CONFIG.get("use_mss_screen_capture",True))
        self.frame = None
        self.occupancy = 0

        self.build_ui()
        self.bind_canvas()
        self.update_preview_button_state()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------- UI -------------
    def build_ui(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left = tk.Frame(self.root, bg="#303030", width=250)
        left.grid(row=0, column=0, sticky="ns")
        left.grid_propagate(False)

        mid = tk.Frame(self.root, bg="#1e1e1e")
        mid.grid(row=0, column=1, sticky="nsew")
        mid.rowconfigure(0, weight=1)
        mid.columnconfigure(0, weight=1)

        right = tk.Frame(self.root, bg="#303030", width=280)
        right.grid(row=0, column=2, sticky="ns")
        right.grid_propagate(False)

        # Left: Input
        sec_input = tk.LabelFrame(left, text="Input", bg="#303030", fg="white")
        sec_input.pack(fill=tk.X, padx=8, pady=8)
        tk.Label(sec_input, text="Type:", bg="#303030", fg="white").pack(anchor="w")
        self.var_input = tk.StringVar(value=self.input_type)
        cb = ttk.Combobox(sec_input, textvariable=self.var_input, values=["screen","webcam","network"], state="readonly")
        cb.pack(fill=tk.X, pady=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self.on_input_change())

        self.row_webcam = tk.Frame(sec_input, bg="#303030")
        tk.Label(self.row_webcam, text="Index:", bg="#303030", fg="white").pack(side=tk.LEFT)
        self.var_cam_index = tk.IntVar(value=self.webcam_index)
        ttk.Spinbox(self.row_webcam, from_=0, to=10, textvariable=self.var_cam_index, width=5).pack(side=tk.LEFT, padx=4)

        self.row_net = tk.Frame(sec_input, bg="#303030")
        tk.Label(self.row_net, text="URL:", bg="#303030", fg="white").pack(side=tk.LEFT)
        self.var_url = tk.StringVar(value=self.stream_url)
        ttk.Entry(self.row_net, textvariable=self.var_url, width=18).pack(side=tk.LEFT, padx=4)

        tk.Button(sec_input, text="Select Region", command=self.select_region, bg="#5050a0", fg="white").pack(fill=tk.X, pady=4)
        tk.Button(sec_input, text="Full Screen", command=self.full_screen_region, bg="#5050a0", fg="white").pack(fill=tk.X, pady=2)
        tk.Button(sec_input, text="Test Source", command=self.test_source, bg="#444", fg="white").pack(fill=tk.X, pady=6)

        # AOI
        sec_aoi = tk.LabelFrame(left, text="AOI", bg="#303030", fg="white")
        sec_aoi.pack(fill=tk.X, padx=8, pady=8)
        tk.Button(sec_aoi, text="Set Rect", command=self.start_rect_aoi, bg="#607d8b", fg="white").pack(fill=tk.X, pady=2)
        tk.Button(sec_aoi, text="Draw Polygon", command=self.start_poly_aoi, bg="#607d8b", fg="white").pack(fill=tk.X, pady=2)
        tk.Button(sec_aoi, text="Clear AOI", command=self.clear_aoi, bg="#d9534f", fg="white").pack(fill=tk.X, pady=4)
        tk.Label(sec_aoi, text="Mode (rect/poly) diambil otomatis dari aksi", bg="#303030", fg="#cccccc", wraplength=200).pack(fill=tk.X)

        # Control
        sec_ctrl = tk.LabelFrame(left, text="Control", bg="#303030", fg="white")
        sec_ctrl.pack(fill=tk.X, padx=8, pady=8)
        self.btn_preview = tk.Button(sec_ctrl, text="Preview", command=self.toggle_preview, bg="#2e7d32", fg="white")
        self.btn_preview.pack(fill=tk.X, pady=2)
        self.btn_run = tk.Button(sec_ctrl, text="Start Counting", command=self.toggle_run, bg="#2e7d32", fg="white")
        self.btn_run.pack(fill=tk.X, pady=2)
        self.btn_alert = tk.Button(sec_ctrl, text="Alerts: ON" if self.alert_enabled else "Alerts: OFF",
                                   command=self.toggle_alert, bg="#ffa500" if self.alert_enabled else "#555555", fg="black")
        self.btn_alert.pack(fill=tk.X, pady=4)
        tk.Button(sec_ctrl, text="Store to DB", command=self.store_db, bg="#0078d4", fg="white").pack(fill=tk.X, pady=4)
        tk.Button(sec_ctrl, text="Model Settings", command=self.model_settings, bg="#444", fg="white").pack(fill=tk.X, pady=2)
        tk.Button(sec_ctrl, text="DB Settings", command=self.db_settings, bg="#444", fg="white").pack(fill=tk.X, pady=2)
        tk.Button(sec_ctrl, text="Reset", command=self.reset_state, bg="#444", fg="white").pack(fill=tk.X, pady=6)

        self.lbl_status = tk.Label(left, text="Status: Idle", bg="#303030", fg="#00d4ff")
        self.lbl_status.pack(fill=tk.X, padx=8, pady=(4,8))

        # Mid: canvas
        self.canvas = tk.Canvas(mid, bg="#111111", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Right: stats / alerts
        sec_stats = tk.LabelFrame(right, text="Stats", bg="#303030", fg="white")
        sec_stats.pack(fill=tk.X, padx=8, pady=8)
        self.lbl_occupancy = tk.Label(sec_stats, text="Occupancy: 0", bg="#303030", fg="#28a745", font=("Arial",14,"bold"))
        self.lbl_occupancy.pack(anchor="w", padx=6, pady=4)
        self.lbl_aoi = tk.Label(sec_stats, text="AOI: none", bg="#303030", fg="white")
        self.lbl_aoi.pack(anchor="w", padx=6, pady=2)
        self.lbl_alert_state = tk.Label(sec_stats, text="Alert State: -", bg="#303030", fg="#ffaa00")
        self.lbl_alert_state.pack(anchor="w", padx=6, pady=2)
        self.lbl_fps = tk.Label(sec_stats, text="FPS: 0.0", bg="#303030", fg="#00d4ff")
        self.lbl_fps.pack(anchor="w", padx=6, pady=6)

        sec_alert_log = tk.LabelFrame(right, text="Alert Log", bg="#303030", fg="white")
        sec_alert_log.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.alert_list = tk.Listbox(sec_alert_log, bg="#1b1b1b", fg="#ff6666")
        self.alert_list.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        tk.Button(sec_alert_log, text="Clear Log", command=lambda:self.alert_list.delete(0,tk.END),
                  bg="#444", fg="white").pack(fill=tk.X, pady=4)

    def bind_canvas(self):
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Button-3>", self.on_canvas_right_click)

    # ------------- Input Management -------------
    def on_input_change(self):
        t = self.var_input.get()
        self.input_type = t
        if t == "webcam":
            self.row_webcam.pack(fill=tk.X, pady=2)
            self.row_net.forget()
        elif t == "network":
            self.row_net.pack(fill=tk.X, pady=2)
            self.row_webcam.forget()
        else:
            self.row_net.forget()
            self.row_webcam.forget()
        self.update_preview_button_state()
        self.persist_settings()

    def update_preview_button_state(self):
        if self.input_type == "screen":
            self.btn_preview.config(state="normal" if self.capture_region else "disabled")
        elif self.input_type == "network":
            self.btn_preview.config(state="normal" if self.var_url.get().strip() else "disabled")
        else:
            self.btn_preview.config(state="normal")

    def persist_settings(self):
        INPUT_CONFIG["type"] = self.input_type
        INPUT_CONFIG["webcam_index"] = int(self.var_cam_index.get())
        INPUT_CONFIG["stream_url"] = self.var_url.get().strip()
        if self.capture_region:
            INPUT_CONFIG["screen_region"] = list(self.capture_region)
        AOI_CONFIG["mode"] = self.aoi_mode
        AOI_CONFIG["rect"] = self.aoi_rect
        AOI_CONFIG["polygon"] = self.aoi_poly
        ALERT_CONFIG["enabled"] = self.alert_enabled
        settings.save()

    def select_region(self):
        if self.input_type != "screen":
            messagebox.showinfo("Info","Hanya untuk mode screen.")
            return
        self.root.withdraw()
        time.sleep(0.3)
        top = tk.Toplevel()
        top.attributes("-fullscreen", True)
        try: top.attributes("-alpha", 0.3)
        except Exception: pass
        top.configure(bg="black")
        top.attributes("-topmost", True)
        canv = tk.Canvas(top, bg="black", highlightthickness=0, cursor="cross")
        canv.pack(fill=tk.BOTH, expand=True)
        canv.create_text(top.winfo_screenwidth()//2, 40, text="Drag area (ESC batal)", fill="#00d4ff", font=("Arial",24,"bold"))
        rect_id = {"id":None}
        start = {"x":None,"y":None}

        def m_down(e):
            start["x"],start["y"]=e.x,e.y
            if rect_id["id"]: canv.delete(rect_id["id"])
            rect_id["id"]=canv.create_rectangle(e.x,e.y,e.x,e.y,outline="#00d4ff",width=3)
        def m_drag(e):
            if start["x"] is not None:
                canv.coords(rect_id["id"], start["x"], start["y"], e.x, e.y)
        def m_up(e):
            x1,y1,x2,y2 = start["x"],start["y"],e.x,e.y
            top.destroy(); self.root.deiconify()
            if None in (x1,y1,x2,y2):
                return
            w,h = abs(x2-x1), abs(y2-y1)
            if w>50 and h>50:
                l,t_ = min(x1,x2), min(y1,y2)
                self.capture_region = (l,t_, l+w, t_+h)
                self.update_preview_button_state()
                self.persist_settings()
            else:
                messagebox.showwarning("Warn","Area terlalu kecil.")
        def cancel(e):
            top.destroy(); self.root.deiconify()

        canv.bind("<Button-1>", m_down)
        canv.bind("<B1-Motion>", m_drag)
        canv.bind("<ButtonRelease-1>", m_up)
        top.bind("<Escape>", cancel)

    def full_screen_region(self):
        if self.input_type != "screen":
            return
        w,h = pyautogui.size()
        self.capture_region = (0,0,w,h)
        self.update_preview_button_state()
        self.persist_settings()

    def open_video_source(self):
        self.close_video_source()
        if self.input_type == "webcam":
            idx = int(self.var_cam_index.get())
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        elif self.input_type == "network":
            url = self.var_url.get().strip()
            if not url:
                return False
            cap = cv2.VideoCapture(url)
        else:
            return True
        if not cap or not cap.isOpened():
            return False
        with self.cap_lock:
            self.cap = cap
        return True

    def close_video_source(self):
        with self.cap_lock:
            if self.cap:
                try: self.cap.release()
                except Exception: pass
                self.cap = None

    def get_frame(self):
        if self.input_type == "screen":
            if not self.capture_region:
                return None
            return self.screen_cap.grab(self.capture_region)
        with self.cap_lock:
            cap = self.cap
        if cap is None: return None
        flush_n = max(1, int(RUNTIME_CONFIG.get("flush_frames",2)))
        for _ in range(flush_n-1):
            try: cap.grab()
            except Exception: break
        ret, fr = cap.read()
        return fr if ret else None

    def test_source(self):
        fr = self.get_frame()
        if fr is None:
            messagebox.showerror("Error","Tidak dapat menangkap frame.")
            return
        self.frame = fr
        self.draw_frame()
        h,w = fr.shape[:2]
        self.lbl_status.config(text=f"Status: Source OK {w}x{h}")

    # ------------- AOI Drawing -------------
    def start_rect_aoi(self):
        self._drawing_rect = True
        self._rect_start = None
        self.aoi_mode = "rect"
        messagebox.showinfo("AOI","Klik & drag di canvas.")

    def start_poly_aoi(self):
        self._drawing_poly = True
        self._poly_canvas_pts = []
        self.aoi_mode = "poly"
        messagebox.showinfo("AOI","Klik titik-titik; klik kanan untuk selesai.")

    def clear_aoi(self):
        self.aoi_rect = None
        self.aoi_poly = []
        self.lbl_aoi.config(text="AOI: none")
        self.persist_settings()
        self.draw_frame()

    def on_canvas_click(self, event):
        if self._drawing_rect:
            self._rect_start = (event.x, event.y)
        elif self._drawing_poly:
            self._poly_canvas_pts.append((event.x, event.y))
            self.draw_frame()

    def on_canvas_drag(self, event):
        if self._drawing_rect and self._rect_start:
            self.draw_frame()
            x0,y0 = self._rect_start
            self.canvas.create_rectangle(x0,y0,event.x,event.y,outline="#ffcc00",width=2)

    def on_canvas_release(self, event):
        if self._drawing_rect and self._rect_start:
            x0,y0 = self._rect_start
            x1,y1 = event.x,event.y
            if abs(x1-x0)>10 and abs(y1-y0)>10:
                self.aoi_rect = self.canvas_to_frame_rect(x0,y0,x1,y1)
                self.lbl_aoi.config(text=f"AOI Rect: {self.aoi_rect}")
                self.persist_settings()
            self._drawing_rect = False
            self._rect_start = None
            self.draw_frame()

    def on_canvas_right_click(self, event):
        if self._drawing_poly and len(self._poly_canvas_pts)>=3:
            self.aoi_poly = [self.canvas_to_frame_point(px,py) for (px,py) in self._poly_canvas_pts]
            self.lbl_aoi.config(text=f"AOI Poly: {len(self.aoi_poly)} pts")
            self._drawing_poly=False
            self._poly_canvas_pts=[]
            self.persist_settings()
            self.draw_frame()

    # ------------- Preview -------------
    def toggle_preview(self):
        if self.input_type=="screen" and not self.capture_region:
            messagebox.showwarning("Warn","Pilih region dulu."); return
        if self.input_type=="network" and not self.var_url.get().strip():
            messagebox.showwarning("Warn","Isi URL stream."); return
        self.is_preview = not self.is_preview
        self.btn_preview.config(text="Stop Preview" if self.is_preview else "Preview")
        if self.is_preview:
            if self.input_type in ("webcam","network"):
                if not self.open_video_source():
                    self.is_preview=False
                    self.btn_preview.config(text="Preview")
                    return
            threading.Thread(target=self.preview_loop, daemon=True).start()
        else:
            if not self.is_running and self.input_type in ("webcam","network"):
                self.close_video_source()

    def preview_loop(self):
        fps_cnt=0
        start=time.time()
        while self.is_preview and not self.is_running:
            fr = self.get_frame()
            if fr is not None:
                self.frame = fr
                self.draw_frame()
            fps_cnt+=1
            if fps_cnt%10==0:
                now=time.time()
                fps=10/(now-start)
                start=now
                self.lbl_fps.config(text=f"FPS: {fps:.1f}")
            time.sleep(0.03)

    # ------------- Run Counting -------------
    def toggle_run(self):
        if self.input_type=="screen" and not self.capture_region:
            messagebox.showwarning("Warn","Pilih region screen."); return
        if self.input_type=="network" and not self.var_url.get().strip():
            messagebox.showwarning("Warn","Isi URL stream."); return
        self.is_running = not self.is_running
        self.btn_run.config(text="Stop" if self.is_running else "Start Counting")
        if self.is_running:
            if self.is_preview:
                self.is_preview=False
                self.btn_preview.config(text="Preview")
            if self.input_type in ("webcam","network"):
                if not self.open_video_source():
                    self.is_running=False
                    self.btn_run.config(text="Start Counting")
                    return
            threading.Thread(target=self.run_loop, daemon=True).start()
        else:
            if self.input_type in ("webcam","network") and not self.is_preview:
                self.close_video_source()

    def run_loop(self):
        stride = max(1, int(RUNTIME_CONFIG.get("detection_stride",1)))
        frame_idx=0
        fps_cnt=0
        start=time.time()
        while self.is_running:
            fr = self.get_frame()
            if fr is None:
                time.sleep(0.01); continue
            run_det = (frame_idx % stride == 0)
            if run_det:
                dets = detect_persons(self.model, fr)
                occ = self.count_in_aoi(dets, fr.shape[:2])
                self.occupancy = occ
                self.update_alert_logic()
                # Draw boxes for visualization (optional)
                for d in dets:
                    x1,y1,x2,y2 = d["bbox"]
                    if self._inside_aoi(((x1+x2)//2,(y1+y2)//2), fr.shape[:2]):
                        cv2.rectangle(fr,(x1,y1),(x2,y2),(0,255,0),2)
                    else:
                        cv2.rectangle(fr,(x1,y1),(x2,y2),(128,128,128),1)

            self.draw_aoi(fr)
            self.frame = fr
            self.draw_frame()
            self.lbl_occupancy.config(text=f"Occupancy: {self.occupancy}")

            fps_cnt+=1
            if fps_cnt%5==0:
                now=time.time()
                fps=5/(now-start)
                start=now
                self.lbl_fps.config(text=f"FPS: {fps:.1f}")

            frame_idx+=1
            time.sleep(0.005)

    # ------------- AOI & Counting -------------
    def count_in_aoi(self, detections, shape):
        h,w = shape
        c = 0
        for d in detections:
            x1,y1,x2,y2 = d["bbox"]
            cx,cy = (x1+x2)//2,(y1+y2)//2
            if self._inside_aoi((cx,cy), shape):
                c+=1
        return c

    def _inside_aoi(self, pt, shape):
        if self.aoi_mode == "poly" and self.aoi_poly and len(self.aoi_poly)>=3:
            return self._point_in_poly(pt, self.aoi_poly)
        if self.aoi_rect:
            x1,y1,x2,y2 = self.aoi_rect
            return x1 <= pt[0] <= x2 and y1 <= pt[1] <= y2
        # Jika AOI belum ditentukan → semua dihitung
        return True

    def _point_in_poly(self, p, poly):
        x,y=p
        inside=False
        n=len(poly)
        for i in range(n):
            x1,y1=poly[i]; x2,y2=poly[(i+1)%n]
            cond=((y1>y)!=(y2>y)) and (x < (x2-x1)*(y-y1)/((y2-y1) if (y2-y1)!=0 else 1e-6) + x1)
            if cond: inside=not inside
        return inside

    def draw_aoi(self, frame):
        if self.aoi_rect:
            x1,y1,x2,y2 = self.aoi_rect
            cv2.rectangle(frame,(x1,y1),(x2,y2),(0,0,255),2)
        elif self.aoi_poly and len(self.aoi_poly)>=3:
            pts = np.array(self.aoi_poly,dtype=np.int32)
            cv2.polylines(frame,[pts],True,(0,0,255),2)

    # ------------- Alert Logic -------------
    def toggle_alert(self):
        self.alert_enabled = not self.alert_enabled
        self.btn_alert.config(text="Alerts: ON" if self.alert_enabled else "Alerts: OFF",
                              bg="#ffa500" if self.alert_enabled else "#555555")
        self.persist_settings()
        self.last_alert_state = None  # reset agar state baru ditampilkan lagi

    def update_alert_logic(self):
        if not self.alert_enabled:
            self.lbl_alert_state.config(text="Alert State: DISABLED", fg="#888888")
            return
        if self.occupancy > 0:
            if self.last_alert_state != "occupied":
                self.alert_list.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] AREA OCCUPIED ({self.occupancy})")
                self.alert_list.yview_moveto(1.0)
                self.lbl_alert_state.config(text="Alert State: OCCUPIED", fg="#ff5555")
                self.last_alert_state = "occupied"
        else:
            if self.last_alert_state != "clear":
                self.alert_list.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] AREA CLEAR")
                self.alert_list.yview_moveto(1.0)
                self.lbl_alert_state.config(text="Alert State: CLEAR", fg="#28a745")
                self.last_alert_state = "clear"

    # ------------- Drawing / Canvas Transform -------------
    def draw_frame(self):
        if self.frame is None:
            return
        img = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)
        im = Image.fromarray(img)
        cw = self.canvas.winfo_width() or 1
        ch = self.canvas.winfo_height() or 1
        iw,ih = im.size
        ar=iw/ih; car=cw/ch
        if ar>car:
            new_w=cw; new_h=int(cw/ar)
        else:
            new_h=ch; new_w=int(ch*ar)
        im=im.resize((new_w,new_h), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(im)
        self.canvas.delete("all")
        self.canvas.create_image(cw//2, ch//2, image=self.photo, anchor=tk.CENTER)
        # poly preview
        if self._drawing_poly and self._poly_canvas_pts:
            for i in range(1,len(self._poly_canvas_pts)):
                p1=self._poly_canvas_pts[i-1]; p2=self._poly_canvas_pts[i]
                self.canvas.create_line(p1[0],p1[1],p2[0],p2[1],fill="#ffcc00",width=2)

    def canvas_to_frame_point(self, cx, cy):
        if self.frame is None:
            return (cx,cy)
        fh,fw = self.frame.shape[:2]
        cw = self.canvas.winfo_width() or 1
        ch = self.canvas.winfo_height() or 1
        ar_f = fw/fh; ar_c = cw/ch
        if ar_f>ar_c:
            scale = cw/fw
            new_h=int(fh*scale)
            y_off=(ch-new_h)//2; x_off=0
        else:
            scale = ch/fh
            new_w=int(fw*scale)
            x_off=(cw-new_w)//2; y_off=0
        x_adj = cx - x_off
        y_adj = cy - y_off
        fx = int(x_adj/scale); fy=int(y_adj/scale)
        fx=max(0,min(fw-1,fx)); fy=max(0,min(fh-1,fy))
        return (fx,fy)

    def canvas_to_frame_rect(self,x0,y0,x1,y1):
        p1=self.canvas_to_frame_point(x0,y0)
        p2=self.canvas_to_frame_point(x1,y1)
        return (min(p1[0],p2[0]), min(p1[1],p2[1]), max(p1[0],p2[0]), max(p1[1],p2[1]))

    # ------------- DB & Settings Dialog -------------
    def store_db(self):
        if not DB_CONFIG.get("enable"):
            messagebox.showwarning("DB","Database disabled di settings.json.")
            return
        ok = self.db.insert_person_snapshot(self.occupancy, note="manual store")
        if ok:
            self.alert_list.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] DB STORE OK (occ={self.occupancy})")
        else:
            self.alert_list.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] DB STORE FAILED")
        self.alert_list.yview_moveto(1.0)

    def model_settings(self):
        # Minimal contoh: ubah threshold saja
        win = tk.Toplevel(self.root); win.title("Model Settings")
        tk.Label(win, text="Confidence Threshold").grid(row=0,column=0,sticky="w")
        var_conf = tk.DoubleVar(value=MODEL_CONFIG["confidence_threshold"])
        ttk.Entry(win, textvariable=var_conf).grid(row=0,column=1,sticky="ew")
        tk.Label(win, text="IoU Threshold").grid(row=1,column=0,sticky="w")
        var_iou = tk.DoubleVar(value=MODEL_CONFIG["iou_threshold"])
        ttk.Entry(win, textvariable=var_iou).grid(row=1,column=1,sticky="ew")
        def save():
            MODEL_CONFIG["confidence_threshold"] = float(var_conf.get())
            MODEL_CONFIG["iou_threshold"] = float(var_iou.get())
            settings.save()
            win.destroy()
        ttk.Button(win,text="Save",command=save).grid(row=2,column=0,columnspan=2,pady=6)
        win.columnconfigure(1,weight=1)

    def db_settings(self):
        win = tk.Toplevel(self.root); win.title("DB Settings")
        entries={}
        for i,(k,v) in enumerate(DB_CONFIG.items()):
            tk.Label(win, text=k).grid(row=i,column=0,sticky="w")
            e=ttk.Entry(win); e.insert(0,str(v)); e.grid(row=i,column=1,sticky="ew")
            entries[k]=e
        def save():
            for k,e in entries.items():
                val=e.get().strip()
                if k=="enable":
                    DB_CONFIG[k] = val.lower() in ("1","true","yes","on")
                elif k in ("port",):
                    DB_CONFIG[k] = int(val)
                else:
                    DB_CONFIG[k] = val
            settings.save()
            if DB_CONFIG.get("enable"):
                self.db.connect()
            else:
                self.db.close()
            win.destroy()
        ttk.Button(win,text="Save",command=save).grid(row=len(entries),column=0,columnspan=2,pady=6)
        win.columnconfigure(1,weight=1)

    def reset_state(self):
        self.occupancy=0
        self.lbl_occupancy.config(text="Occupancy: 0")
        self.last_alert_state=None
        self.alert_list.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] RESET")
        self.alert_list.yview_moveto(1.0)

    # ------------- Alert toggle UI -------------
    def toggle_alert(self):
        self.alert_enabled = not self.alert_enabled
        self.btn_alert.config(text="Alerts: ON" if self.alert_enabled else "Alerts: OFF",
                              bg="#ffa500" if self.alert_enabled else "#555555")
        self.persist_settings()
        self.last_alert_state=None

    def on_db_status(self, ok: bool):
        if ok:
            self.lbl_status.config(text="Status: DB Connected", fg="#28a745")
        else:
            self.lbl_status.config(text="Status: DB Disconnected", fg="#ff5555")

    # ------------- Close -------------
    def on_close(self):
        self.is_running=False
        self.is_preview=False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.db.close()
        settings.save()
        self.root.destroy()

def main():
    app = App()
    app.root.mainloop()

if __name__ == "__main__":
    main()