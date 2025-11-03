import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog  # Add filedialog
import winsound  # Add this for sound

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

        # Sound settings
        self.alert_sound_enabled = ALERT_CONFIG.get("sound_enabled", True)
        self.alert_sound_type = ALERT_CONFIG.get("sound_type", "beep")
        self.alert_sound_file = ALERT_CONFIG.get("sound_file", "")
        self.sound_continuous = ALERT_CONFIG.get("sound_continuous", True)
        self.sound_interval = ALERT_CONFIG.get("sound_interval", 5.0)
        self.sound_cooldown = ALERT_CONFIG.get("sound_cooldown", 2.0)
        self.last_sound_time = 0
        
        # Continuous sound control
        self.sound_thread_running = False
        self.sound_thread = None
        
        # Blink settings (ADD THIS SECTION - MISSING!)
        self.blink_enabled = ALERT_CONFIG.get("blink_enabled", True)
        self.blink_interval = ALERT_CONFIG.get("blink_interval", 0.5)
        self.blink_color = ALERT_CONFIG.get("blink_color", "#FF0000")
        self.blink_thread_running = False
        self.blink_thread = None
        self.original_canvas_bg = "#111111"  # Store original background

        # DB
        self.db = DBManager(status_callback=self.on_db_status)

        # Runtime flags
        self.is_preview = False
        self.is_running = False

        # Frame buffer
        self.screen_cap = ScreenCapturer(RUNTIME_CONFIG.get("use_mss_screen_capture",True))
        self.frame = None
        self.frame_lock = threading.Lock()
        self.canvas_image_id = None
        self.photo = None    
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

        # Sound toggle button
        self.btn_sound = tk.Button(
            sec_ctrl, 
            text="Sound: ON" if self.alert_sound_enabled else "Sound: OFF",
            command=self.toggle_sound, 
            bg="#ff9800" if self.alert_sound_enabled else "#555555", 
            fg="white"
        )
        self.btn_sound.pack(fill=tk.X, pady=2)

        # Blink toggle button (NEW)
        self.btn_blink = tk.Button(
            sec_ctrl, 
            text="Blink: ON" if self.blink_enabled else "Blink: OFF",
            command=self.toggle_blink, 
            bg="#e91e63" if self.blink_enabled else "#555555", 
            fg="white"
        )
        self.btn_blink.pack(fill=tk.X, pady=2)

        tk.Button(sec_ctrl, text="Store to DB", command=self.store_db, bg="#0078d4", fg="white").pack(fill=tk.X, pady=4)
        tk.Button(sec_ctrl, text="Model Settings", command=self.model_settings, bg="#444", fg="white").pack(fill=tk.X, pady=2)
        tk.Button(sec_ctrl, text="DB Settings", command=self.db_settings, bg="#444", fg="white").pack(fill=tk.X, pady=2)
        tk.Button(sec_ctrl, text="Sound Settings", command=self.sound_settings, bg="#444", fg="white").pack(fill=tk.X, pady=2)

        # Blink Settings button (NEW)
        tk.Button(sec_ctrl, text="Blink Settings", command=self.blink_settings, bg="#444", fg="white").pack(fill=tk.X, pady=2)

        tk.Button(sec_ctrl, text="Reset", command=self.reset_state, bg="#444", fg="white").pack(fill=tk.X, pady=6)

        # *** ADD THIS LINE - Status label that was missing! ***
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
        self.lbl_sound_status = tk.Label(sec_stats, text="Sound: Idle", bg="#303030", fg="#888888", font=("Arial", 9))
        self.lbl_sound_status.pack(anchor="w", padx=6, pady=2)
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
        ALERT_CONFIG["sound_enabled"] = self.alert_sound_enabled
        ALERT_CONFIG["sound_type"] = self.alert_sound_type
        ALERT_CONFIG["sound_file"] = self.alert_sound_file
        ALERT_CONFIG["sound_continuous"] = self.sound_continuous
        ALERT_CONFIG["sound_interval"] = self.sound_interval
        ALERT_CONFIG["sound_cooldown"] = self.sound_cooldown
        ALERT_CONFIG["blink_enabled"] = self.blink_enabled        # NEW
        ALERT_CONFIG["blink_interval"] = self.blink_interval      # NEW
        ALERT_CONFIG["blink_color"] = self.blink_color            # NEW
        settings.save()
    def blink_settings(self):
        """Open blink settings dialog"""
        win = tk.Toplevel(self.root)
        win.title("Blink Settings")
        win.geometry("450x250")
        win.configure(bg="#252525")
        
        # Enable Blink Checkbox
        tk.Label(win, text="Enable Blink:", bg="#252525", fg="white").grid(row=0, column=0, sticky="w", padx=10, pady=10)
        var_blink_enabled = tk.BooleanVar(value=self.blink_enabled)
        chk_blink = tk.Checkbutton(
            win, 
            text="Flash screen when occupied", 
            variable=var_blink_enabled,
            bg="#252525", 
            fg="white", 
            selectcolor="#404040",
            activebackground="#252525",
            activeforeground="white"
        )
        chk_blink.grid(row=0, column=1, sticky="w", padx=10, pady=10)
        
        # Blink Interval
        tk.Label(win, text="Blink Interval (sec):", bg="#252525", fg="white").grid(row=1, column=0, sticky="w", padx=10, pady=10)
        var_interval = tk.DoubleVar(value=self.blink_interval)
        entry_interval = ttk.Entry(win, textvariable=var_interval, width=30)
        entry_interval.grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        tk.Label(win, text="(0.1 - 2.0 seconds)", bg="#252525", fg="#888888", font=("Arial", 8)).grid(row=1, column=2, sticky="w", padx=5)
        
        # Blink Color
        tk.Label(win, text="Blink Color:", bg="#252525", fg="white").grid(row=2, column=0, sticky="w", padx=10, pady=10)
        
        color_frame = tk.Frame(win, bg="#252525")
        color_frame.grid(row=2, column=1, sticky="w", padx=10, pady=10)
        
        var_color = tk.StringVar(value=self.blink_color)
        
        # Color preview
        color_preview = tk.Label(color_frame, text="     ", bg=self.blink_color, relief="solid", borderwidth=2)
        color_preview.pack(side=tk.LEFT, padx=(0, 10))
        
        def choose_color():
            from tkinter import colorchooser
            color = colorchooser.askcolor(initialcolor=var_color.get(), title="Choose Blink Color")
            if color[1]:  # color[1] is hex value
                var_color.set(color[1])
                color_preview.config(bg=color[1])
        
        tk.Button(color_frame, text="Choose Color", command=choose_color, bg="#444", fg="white").pack(side=tk.LEFT)
        
        # Preset colors
        tk.Label(win, text="Presets:", bg="#252525", fg="white").grid(row=3, column=0, sticky="w", padx=10, pady=10)
        preset_frame = tk.Frame(win, bg="#252525")
        preset_frame.grid(row=3, column=1, columnspan=2, sticky="w", padx=10, pady=10)
        
        preset_colors = [
            ("#FF0000", "Red"),
            ("#FF6600", "Orange"),
            ("#FFFF00", "Yellow"),
            ("#FF00FF", "Magenta"),
            ("#FFFFFF", "White")
        ]
        
        for color_hex, color_name in preset_colors:
            btn = tk.Button(
                preset_frame, 
                text=color_name, 
                bg=color_hex,
                fg="black" if color_hex in ["#FFFF00", "#FFFFFF"] else "white",
                width=8,
                command=lambda c=color_hex: [var_color.set(c), color_preview.config(bg=c)]
            )
            btn.pack(side=tk.LEFT, padx=2)
        
        # Test button
        def test_blink():
            # Quick test - blink 3 times
            original_enabled = self.blink_enabled
            original_color = self.blink_color
            original_interval = self.blink_interval
            
            self.blink_enabled = True
            self.blink_color = var_color.get()
            self.blink_interval = float(var_interval.get())
            
            def do_test():
                for i in range(6):  # 3 full blinks (on-off cycles)
                    if i % 2 == 0:
                        self.canvas.configure(bg=self.blink_color)
                    else:
                        self.canvas.configure(bg=self.original_canvas_bg)
                    time.sleep(self.blink_interval)
                self.canvas.configure(bg=self.original_canvas_bg)
                
                # Restore settings
                self.blink_enabled = original_enabled
                self.blink_color = original_color
                self.blink_interval = original_interval
            
            threading.Thread(target=do_test, daemon=True).start()
        
        tk.Button(win, text="Test Blink (3x)", command=test_blink, bg="#0078d4", fg="white", width=15).grid(row=4, column=0, columnspan=3, pady=15)
        
        # Save button
        def save():
            try:
                self.blink_enabled = var_blink_enabled.get()
                self.blink_interval = max(0.1, min(2.0, float(var_interval.get())))  # Clamp between 0.1-2.0
                self.blink_color = var_color.get()
                
                ALERT_CONFIG["blink_enabled"] = self.blink_enabled
                ALERT_CONFIG["blink_interval"] = self.blink_interval
                ALERT_CONFIG["blink_color"] = self.blink_color
                
                settings.save()
                
                # Update button state
                self.btn_blink.config(
                    text="Blink: ON" if self.blink_enabled else "Blink: OFF",
                    bg="#e91e63" if self.blink_enabled else "#555555"
                )
                
                messagebox.showinfo("Success", "Blink settings saved!")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {e}")
        
        tk.Button(win, text="Save", command=save, bg="#2e7d32", fg="white", width=15).grid(row=5, column=0, columnspan=3, pady=10)
        win.columnconfigure(1, weight=1)
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
        if self.input_type in ("webcam", "network"):
            if not self.open_video_source():
                messagebox.showerror("Error", "Tidak dapat membuka video source.")
                return
        
        fr = self.get_frame()
        if fr is None:
            messagebox.showerror("Error","Tidak dapat menangkap frame.")
            if self.input_type in ("webcam", "network"):
                self.close_video_source()
            return
        
        with self.frame_lock:
            self.frame = fr.copy()
        
        self.draw_frame()
        h,w = fr.shape[:2]
        self.lbl_status.config(text=f"Status: Source OK {w}x{h}")
        
        # Close video source after test if not in preview/run mode
        if self.input_type in ("webcam", "network") and not self.is_preview and not self.is_running:
            self.close_video_source()

    # ------------- AOI Drawing -------------
    def start_rect_aoi(self):
        # Check if we have a frame first
        if self.frame is None:
            messagebox.showwarning("AOI", "Please capture or preview a frame first (click 'Test Source' or 'Preview').")
            return
        
        self._drawing_rect = True
        self._rect_start = None
        self.aoi_mode = "rect"
        self.lbl_status.config(text="Status: Drawing Rectangle AOI...")
        messagebox.showinfo("AOI","Click & drag on canvas to draw rectangle AOI.")

    def start_poly_aoi(self):
        # Check if we have a frame first
        if self.frame is None:
            messagebox.showwarning("AOI", "Please capture or preview a frame first (click 'Test Source' or 'Preview').")
            return
        
        self._drawing_poly = True
        self._poly_canvas_pts = []
        self.aoi_mode = "poly"
        self.lbl_status.config(text="Status: Drawing Polygon AOI...")
        messagebox.showinfo("AOI","Click points on canvas; right-click to finish polygon.")

    def clear_aoi(self):
        self.aoi_rect = None
        self.aoi_poly = []
        self.aoi_mode = "rect"
        self.lbl_aoi.config(text="AOI: none")
        self.persist_settings()
        self.draw_frame()
        self.lbl_status.config(text="Status: AOI Cleared")

    def on_canvas_click(self, event):
        if self._drawing_rect:
            self._rect_start = (event.x, event.y)
        elif self._drawing_poly:
            self._poly_canvas_pts.append((event.x, event.y))
            self.draw_frame()
            # Draw all polygon points and lines so far
            self.canvas.delete("poly_preview")
            if len(self._poly_canvas_pts) > 0:
                # Draw points
                for px, py in self._poly_canvas_pts:
                    self.canvas.create_oval(px-3, py-3, px+3, py+3, fill="#ffcc00", tags="poly_preview")
                # Draw lines
                if len(self._poly_canvas_pts) > 1:
                    for i in range(1, len(self._poly_canvas_pts)):
                        p1 = self._poly_canvas_pts[i-1]
                        p2 = self._poly_canvas_pts[i]
                        self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#ffcc00", width=2, tags="poly_preview")

    def on_canvas_drag(self, event):
        if self._drawing_rect and self._rect_start:
            # Delete previous preview rectangle
            self.canvas.delete("preview_rect")
            
            # Draw new preview rectangle
            x0, y0 = self._rect_start
            self.canvas.create_rectangle(
                x0, y0, event.x, event.y, 
                outline="#ffcc00", 
                width=2, 
                tags="preview_rect"
            )

    def on_canvas_release(self, event):
        if self._drawing_rect and self._rect_start:
            x0, y0 = self._rect_start
            x1, y1 = event.x, event.y
            
            # Check minimum drag distance
            if abs(x1 - x0) > 10 and abs(y1 - y0) > 10:
                rect = self.canvas_to_frame_rect(x0, y0, x1, y1)
                if rect is not None:
                    self.aoi_rect = rect
                    self.lbl_aoi.config(text=f"AOI Rect: {self.aoi_rect}")
                    self.persist_settings()
                    self.lbl_status.config(text=f"Status: Rectangle AOI Set")
                    messagebox.showinfo("AOI", f"Rectangle AOI set: {self.aoi_rect}")
                else:
                    messagebox.showwarning("AOI", "Rectangle too small or invalid. Please try again.")
                    self.lbl_status.config(text="Status: AOI Setting Failed")
            else:
                messagebox.showwarning("AOI", "Rectangle too small. Please drag a larger area.")
                self.lbl_status.config(text="Status: AOI Too Small")
            
            self._drawing_rect = False
            self._rect_start = None
            self.canvas.delete("preview_rect")
            self.draw_frame()

    def on_canvas_right_click(self, event):
        if self._drawing_poly and len(self._poly_canvas_pts) >= 3:
            self.aoi_poly = [self.canvas_to_frame_point(px, py) for (px, py) in self._poly_canvas_pts]
            self.lbl_aoi.config(text=f"AOI Poly: {len(self.aoi_poly)} pts")
            self._drawing_poly = False
            self._poly_canvas_pts = []
            self.persist_settings()
            self.lbl_status.config(text=f"Status: Polygon AOI Set ({len(self.aoi_poly)} points)")
            self.canvas.delete("poly_preview")
            self.draw_frame()
            messagebox.showinfo("AOI", f"Polygon AOI set with {len(self.aoi_poly)} points")
        elif self._drawing_poly:
            messagebox.showwarning("AOI", "Need at least 3 points to create a polygon.")

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
                    messagebox.showerror("Error", "Failed to open video source.")
                    return
            self.lbl_status.config(text="Status: Previewing...")
            threading.Thread(target=self.preview_loop, daemon=True).start()
        else:
            self.lbl_status.config(text="Status: Preview Stopped")
            if not self.is_running and self.input_type in ("webcam","network"):
                self.close_video_source()

    def preview_loop(self):
        fps_cnt=0
        start=time.time()
        while self.is_preview and not self.is_running:
            fr = self.get_frame()
            if fr is not None:
                with self.frame_lock:
                    self.frame = fr.copy()
                # schedule draw on main thread
                try:
                    self.root.after(0, self.draw_frame)
                except Exception:
                    pass
            fps_cnt+=1
            if fps_cnt%10==0:
                now=time.time()
                fps=10/(now-start) if (now-start)>0 else 0.0
                start=now
                # schedule label update
                try:
                    self.root.after(0, lambda f=fps: self.lbl_fps.config(text=f"FPS: {f:.1f}"))
                except Exception:
                    pass
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
                    messagebox.showerror("Error", "Failed to open video source.")
                    return
            self.lbl_status.config(text="Status: Counting...")
            threading.Thread(target=self.run_loop, daemon=True).start()
        else:
            self.lbl_status.config(text="Status: Counting Stopped")
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
                time.sleep(0.01)
                continue

            run_det = (frame_idx % stride == 0)

            # Work on a local copy so we don't mutate shared state while UI reads it
            local_fr = fr.copy()

            if run_det:
                dets = detect_persons(self.model, local_fr)
                occ = self.count_in_aoi(dets, local_fr.shape[:2])
                self.occupancy = occ
                # draw boxes for visualization on local copy
                for d in dets:
                    x1,y1,x2,y2 = d["bbox"]
                    if self._inside_aoi(((x1+x2)//2,(y1+y2)//2), local_fr.shape[:2]):
                        cv2.rectangle(local_fr,(x1,y1),(x2,y2),(0,255,0),2)
                        # Add label
                        cv2.putText(local_fr, f"{d['confidence']:.2f}", (x1, y1-5), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
                    else:
                        cv2.rectangle(local_fr,(x1,y1),(x2,y2),(128,128,128),1)

            # draw AOI onto local frame
            self.draw_aoi(local_fr)

            # store frame thread-safely
            with self.frame_lock:
                self.frame = local_fr.copy()

            # schedule UI updates on main thread
            try:
                self.root.after(0, self.draw_frame)
                self.root.after(0, lambda occ=self.occupancy: self.lbl_occupancy.config(text=f"Occupancy: {occ}"))
                # update_alert_logic touches widgets (Listbox/Label) -> run in main thread
                self.root.after(0, self.update_alert_logic)
            except Exception:
                pass

            fps_cnt += 1
            if fps_cnt % 5 == 0:
                now=time.time()
                fps = 5/(now-start) if (now-start)>0 else 0.0
                start=now
                try:
                    self.root.after(0, lambda f=fps: self.lbl_fps.config(text=f"FPS: {f:.1f}"))
                except Exception:
                    pass

            frame_idx += 1
            # small sleep to yield CPU; keep low for smooth counting
            time.sleep(0.005)

    # ------------- AOI & Counting -------------
    def count_in_aoi(self, detections, shape):
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
            cv2.putText(frame, "AOI", (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
        elif self.aoi_poly and len(self.aoi_poly)>=3:
            pts = np.array(self.aoi_poly,dtype=np.int32)
            cv2.polylines(frame,[pts],True,(0,0,255),2)
            if len(self.aoi_poly) > 0:
                cv2.putText(frame, "AOI", tuple(self.aoi_poly[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
    def start_blink_effect(self):
        """Start screen blink effect while area is occupied"""
        if not self.blink_enabled:
            return
        
        if self.blink_thread_running:
            return  # Already running
        
        self.blink_thread_running = True
        self.blink_thread = threading.Thread(target=self._blink_loop, daemon=True)
        self.blink_thread.start()

    def stop_blink_effect(self):
        """Stop screen blink effect"""
        self.blink_thread_running = False
        if self.blink_thread:
            self.blink_thread = None
        
        # Restore original canvas background
        try:
            self.root.after(0, lambda: self.canvas.configure(bg=self.original_canvas_bg))
        except:
            pass

    def _blink_loop(self):
        """Worker thread for blink effect"""
        blink_state = False
        while self.blink_thread_running and self.is_running:
            # Check if still occupied
            if self.occupancy > 0 and self.alert_enabled and self.blink_enabled:
                # Toggle blink state
                blink_state = not blink_state
                
                if blink_state:
                    # Blink color
                    try:
                        self.root.after(0, lambda: self.canvas.configure(bg=self.blink_color))
                    except Exception as e:
                        print(f"[WARNING] Blink effect failed: {e}")
                else:
                    # Original color
                    try:
                        self.root.after(0, lambda: self.canvas.configure(bg=self.original_canvas_bg))
                    except:
                        pass
                
                # Wait for blink interval
                time.sleep(self.blink_interval)
            else:
                # If not occupied, stop the loop
                break
        
        self.blink_thread_running = False
        # Restore original color when stopped
        try:
            self.root.after(0, lambda: self.canvas.configure(bg=self.original_canvas_bg))
        except:
            pass
        print("[INFO] Blink effect stopped")

    def toggle_blink(self):
        """Toggle blink effect on/off"""
        self.blink_enabled = not self.blink_enabled
        self.btn_blink.config(
            text="Blink: ON" if self.blink_enabled else "Blink: OFF",
            bg="#e91e63" if self.blink_enabled else "#555555"
        )
        ALERT_CONFIG["blink_enabled"] = self.blink_enabled
        self.persist_settings()
        
        # Stop blink if disabled while running
        if not self.blink_enabled and self.blink_thread_running:
            self.stop_blink_effect()
    # ------------- Alert Logic -------------
    def toggle_alert(self):
        self.alert_enabled = not self.alert_enabled
        self.btn_alert.config(text="Alerts: ON" if self.alert_enabled else "Alerts: OFF",
                              bg="#ffa500" if self.alert_enabled else "#555555")
        self.persist_settings()
        self.last_alert_state = None  # reset agar state baru ditampilkan lagi
    def update_alert_logic(self):
        """Update alert state and manage continuous sound and blink"""
        if not self.alert_enabled:
            self.lbl_alert_state.config(text="Alert State: DISABLED", fg="#888888")
            # Stop continuous sound and blink if disabled
            if self.sound_thread_running:
                self.stop_continuous_sound()
            if self.blink_thread_running:
                self.stop_blink_effect()
            return
        
        if self.occupancy > 0:
            # Area is occupied
            if self.last_alert_state != "occupied":
                # First time detection
                self.alert_list.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] AREA OCCUPIED ({self.occupancy})")
                self.alert_list.yview_moveto(1.0)
                self.lbl_alert_state.config(text="Alert State: OCCUPIED", fg="#ff5555")
                self.last_alert_state = "occupied"
                
                # Start continuous sound if enabled
                if self.sound_continuous and self.alert_sound_enabled:
                    self.start_continuous_sound()
                else:
                    # Play single alert if continuous mode is off
                    self.play_alert_sound("occupied")
                
                # Start blink effect if enabled
                if self.blink_enabled:
                    self.start_blink_effect()
        else:
            # Area is clear
            if self.last_alert_state != "clear":
                # Just log, NO SOUND when clearing
                self.alert_list.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] AREA CLEAR")
                self.alert_list.yview_moveto(1.0)
                self.lbl_alert_state.config(text="Alert State: CLEAR", fg="#28a745")
                self.last_alert_state = "clear"
                
                # Stop continuous sound when area clears
                if self.sound_thread_running:
                    self.stop_continuous_sound()
                
                # Stop blink effect when area clears
                if self.blink_thread_running:
                    self.stop_blink_effect()
    # def update_alert_logic(self):
    #     if not self.alert_enabled:
    #         self.lbl_alert_state.config(text="Alert State: DISABLED", fg="#888888")
    #         return
    #     if self.occupancy > 0:
    #         if self.last_alert_state != "occupied":
    #             self.alert_list.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] AREA OCCUPIED ({self.occupancy})")
    #             self.alert_list.yview_moveto(1.0)
    #             self.lbl_alert_state.config(text="Alert State: OCCUPIED", fg="#ff5555")
    #             self.last_alert_state = "occupied"
    #     else:
    #         if self.last_alert_state != "clear":
    #             self.alert_list.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] AREA CLEAR")
    #             self.alert_list.yview_moveto(1.0)
    #             self.lbl_alert_state.config(text="Alert State: CLEAR", fg="#28a745")
    #             self.last_alert_state = "clear"

    


    def start_continuous_sound(self):
        """Start continuous sound loop while area is occupied"""
        if not self.sound_continuous:
            return
        
        if self.sound_thread_running:
            return  # Already running
        
        self.sound_thread_running = True
        self.sound_thread = threading.Thread(target=self._continuous_sound_loop, daemon=True)
        self.sound_thread.start()
        
        # Update UI indicator
        try:
            self.root.after(0, lambda: self.lbl_sound_status.config(
                text="Sound: Playing ♫", 
                fg="#ff9800"
            ))
        except:
            pass
    
    def stop_continuous_sound(self):
        """Stop continuous sound loop"""
        self.sound_thread_running = False
        if self.sound_thread:
            self.sound_thread = None
        
        # Update UI indicator
        try:
            self.root.after(0, lambda: self.lbl_sound_status.config(
                text="Sound: Idle", 
                fg="#888888"
            ))
        except:
            pass
    
    def _continuous_sound_loop(self):
        """Worker thread for continuous sound playback"""
        while self.sound_thread_running and self.is_running:
            # Check if still occupied
            if self.occupancy > 0 and self.alert_enabled and self.alert_sound_enabled:
                # Play sound
                try:
                    self._play_sound_worker("occupied")
                except Exception as e:
                    print(f"[WARNING] Continuous sound failed: {e}")
                
                # Wait for interval, but check periodically if we should stop
                elapsed = 0
                check_interval = 0.5  # Check every 0.5 seconds
                while elapsed < self.sound_interval and self.sound_thread_running:
                    time.sleep(check_interval)
                    elapsed += check_interval
                    
                    # If occupancy dropped to 0, exit immediately
                    if self.occupancy == 0:
                        break
            else:
                # If not occupied or sound disabled, stop the loop
                break
        
        self.sound_thread_running = False
        print("[INFO] Continuous sound loop stopped")
    def play_alert_sound(self, alert_type="occupied"):
        """Play alert sound based on configuration"""
        if not self.alert_sound_enabled:
            return
        
        # Check cooldown to prevent sound spam
        current_time = time.time()
        if current_time - self.last_sound_time < self.sound_cooldown:
            return
        
        self.last_sound_time = current_time
        
        # Play in separate thread to avoid blocking
        threading.Thread(target=self._play_sound_worker, args=(alert_type,), daemon=True).start()
    
    def _play_sound_worker(self, alert_type):
        """Worker thread for playing sound"""
        try:
            if self.alert_sound_type == "beep":
                # System beep (Windows)
                if alert_type == "occupied":
                    # Higher pitch for occupied (1000Hz for 300ms)
                    winsound.Beep(1000, 300)
                else:
                    # Lower pitch for clear (500Hz for 200ms)
                    winsound.Beep(500, 200)
            
            elif self.alert_sound_type == "system":
                # System sound (Windows)
                if alert_type == "occupied":
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                else:
                    winsound.MessageBeep(winsound.MB_OK)
            
            elif self.alert_sound_type == "file" and self.alert_sound_file:
                # Play custom WAV file
                import os
                if os.path.exists(self.alert_sound_file) and self.alert_sound_file.lower().endswith('.wav'):
                    winsound.PlaySound(self.alert_sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
        
        except Exception as e:
            print(f"[WARNING] Failed to play sound: {e}")
    
    def toggle_sound(self):
        """Toggle sound alerts on/off"""
        self.alert_sound_enabled = not self.alert_sound_enabled
        self.btn_sound.config(
            text="Sound: ON" if self.alert_sound_enabled else "Sound: OFF",
            bg="#ff9800" if self.alert_sound_enabled else "#555555"
        )
        ALERT_CONFIG["sound_enabled"] = self.alert_sound_enabled
        self.persist_settings()
        
        # Test sound when enabled
        if self.alert_sound_enabled:
            self.play_alert_sound("occupied")
    
    def sound_settings(self):
        """Open sound settings dialog"""
        win = tk.Toplevel(self.root)
        win.title("Sound Settings")
        win.geometry("520x320")
        win.configure(bg="#252525")
        
        # Sound Type
        tk.Label(win, text="Sound Type:", bg="#252525", fg="white").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        var_sound_type = tk.StringVar(value=self.alert_sound_type)
        combo = ttk.Combobox(win, textvariable=var_sound_type, values=["beep", "system", "file"], state="readonly", width=25)
        combo.grid(row=0, column=1, sticky="ew", padx=10, pady=8)
        
        # Sound File
        tk.Label(win, text="Sound File (WAV):", bg="#252525", fg="white").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        var_sound_file = tk.StringVar(value=self.alert_sound_file)
        entry_file = ttk.Entry(win, textvariable=var_sound_file, width=30)
        entry_file.grid(row=1, column=1, sticky="ew", padx=10, pady=8)
        
        def browse_file():
            filename = filedialog.askopenfilename(
                title="Select Sound File",
                filetypes=[("WAV files", "*.wav"), ("All files", "*.*")]
            )
            if filename:
                var_sound_file.set(filename)
        
        tk.Button(win, text="Browse", command=browse_file, bg="#444", fg="white").grid(row=1, column=2, padx=5, pady=8)
        
        # Continuous Sound Checkbox
        tk.Label(win, text="Continuous Sound:", bg="#252525", fg="white").grid(row=2, column=0, sticky="w", padx=10, pady=8)
        var_continuous = tk.BooleanVar(value=self.sound_continuous)
        chk_continuous = tk.Checkbutton(
            win, 
            text="Play repeatedly while occupied", 
            variable=var_continuous,
            bg="#252525", 
            fg="white", 
            selectcolor="#404040",
            activebackground="#252525",
            activeforeground="white"
        )
        chk_continuous.grid(row=2, column=1, sticky="w", padx=10, pady=8)
        
        # Sound Interval
        tk.Label(win, text="Sound Interval (sec):", bg="#252525", fg="white").grid(row=3, column=0, sticky="w", padx=10, pady=8)
        var_interval = tk.DoubleVar(value=self.sound_interval)
        entry_interval = ttk.Entry(win, textvariable=var_interval, width=30)
        entry_interval.grid(row=3, column=1, sticky="ew", padx=10, pady=8)
        tk.Label(win, text="(for continuous mode)", bg="#252525", fg="#888888", font=("Arial", 8)).grid(row=3, column=2, sticky="w", padx=5)
        
        # Sound Cooldown
        tk.Label(win, text="Sound Cooldown (sec):", bg="#252525", fg="white").grid(row=4, column=0, sticky="w", padx=10, pady=8)
        var_cooldown = tk.DoubleVar(value=self.sound_cooldown)
        entry_cooldown = ttk.Entry(win, textvariable=var_cooldown, width=30)
        entry_cooldown.grid(row=4, column=1, sticky="ew", padx=10, pady=8)
        tk.Label(win, text="(for single alerts)", bg="#252525", fg="#888888", font=("Arial", 8)).grid(row=4, column=2, sticky="w", padx=5)
        
        def test_sound():
            temp_type = self.alert_sound_type
            temp_file = self.alert_sound_file
            
            self.alert_sound_type = var_sound_type.get()
            self.alert_sound_file = var_sound_file.get()
            self.play_alert_sound("occupied")
            
            # Restore if not saved
            self.alert_sound_type = temp_type
            self.alert_sound_file = temp_file
        
        tk.Button(win, text="Test Sound", command=test_sound, bg="#0078d4", fg="white", width=15).grid(row=5, column=0, columnspan=3, pady=10)
        
        def save():
            try:
                self.alert_sound_type = var_sound_type.get()
                self.alert_sound_file = var_sound_file.get()
                self.sound_continuous = var_continuous.get()
                self.sound_interval = float(var_interval.get())
                self.sound_cooldown = float(var_cooldown.get())
                
                ALERT_CONFIG["sound_type"] = self.alert_sound_type
                ALERT_CONFIG["sound_file"] = self.alert_sound_file
                ALERT_CONFIG["sound_continuous"] = self.sound_continuous
                ALERT_CONFIG["sound_interval"] = self.sound_interval
                ALERT_CONFIG["sound_cooldown"] = self.sound_cooldown
                
                settings.save()
                messagebox.showinfo("Success", "Sound settings saved!")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {e}")
        
        tk.Button(win, text="Save", command=save, bg="#2e7d32", fg="white", width=15).grid(row=6, column=0, columnspan=3, pady=10)
        win.columnconfigure(1, weight=1)
    # ------------- Drawing / Canvas Transform -------------
    def draw_frame(self):
        """Draw frame on canvas with proper locking and scaling"""
        if self.frame is None:
            return
        
        # Get frame snapshot thread-safe
        with self.frame_lock:
            fr = self.frame.copy()

        img = cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)
        im = Image.fromarray(img)
        
        cw = self.canvas.winfo_width() or 1
        ch = self.canvas.winfo_height() or 1
        
        if cw < 10 or ch < 10:
            # Canvas not ready yet
            return
        
        iw, ih = im.size
        
        if ih == 0 or iw == 0:
            return
        
        ar = iw / ih
        car = cw / ch
        
        # Calculate new dimensions maintaining aspect ratio
        if ar > car:
            new_w = cw
            new_h = int(cw / ar)
        else:
            new_h = ch
            new_w = int(ch * ar)
        
        # Resize image
        im = im.resize((new_w, new_h), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(im)
        
        # Update or create canvas image
        if self.canvas_image_id is None:
            self.canvas_image_id = self.canvas.create_image(
                cw // 2, ch // 2, 
                image=self.photo, 
                anchor=tk.CENTER
            )
        else:
            self.canvas.itemconfig(self.canvas_image_id, image=self.photo)
            self.canvas.coords(self.canvas_image_id, cw // 2, ch // 2)
        
        # Draw polygon preview on top
        self.canvas.delete("poly_preview")
        if self._drawing_poly and self._poly_canvas_pts:
            # Draw points
            for px, py in self._poly_canvas_pts:
                self.canvas.create_oval(px-3, py-3, px+3, py+3, fill="#ffcc00", tags="poly_preview")
            # Draw lines
            if len(self._poly_canvas_pts) > 1:
                for i in range(1, len(self._poly_canvas_pts)):
                    p1 = self._poly_canvas_pts[i-1]
                    p2 = self._poly_canvas_pts[i]
                    self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#ffcc00", width=2, tags="poly_preview")
        
        # Clean up preview rectangle if not drawing
        if not self._drawing_rect:
            self.canvas.delete("preview_rect")

    def canvas_to_frame_point(self, cx, cy):
        """Convert canvas coordinates to frame coordinates with safeguards"""
        if self.frame is None:
            return (cx, cy)
        
        fh, fw = self.frame.shape[:2]
        cw = self.canvas.winfo_width() or 1
        ch = self.canvas.winfo_height() or 1
        
        # Prevent division by zero
        if fh == 0 or fw == 0:
            return (cx, cy)
        
        ar_f = fw / fh
        ar_c = cw / ch
        
        # Calculate scaling and offsets
        if ar_f > ar_c:
            # Frame is wider - fit to canvas width
            scale = cw / fw
            new_h = int(fh * scale)
            x_off = 0
            y_off = (ch - new_h) // 2
        else:
            # Frame is taller - fit to canvas height
            scale = ch / fh
            new_w = int(fw * scale)
            x_off = (cw - new_w) // 2
            y_off = 0
        
        # Adjust for offset
        x_adj = cx - x_off
        y_adj = cy - y_off
        
        # Convert to frame coordinates
        if scale > 0:
            fx = int(x_adj / scale)
            fy = int(y_adj / scale)
        else:
            fx, fy = 0, 0
        
        # Clamp to frame bounds
        fx = max(0, min(fw - 1, fx))
        fy = max(0, min(fh - 1, fy))
        
        return (fx, fy)

    def canvas_to_frame_rect(self, x0, y0, x1, y1):
        """Convert canvas rectangle to frame rectangle coordinates with validation"""
        if self.frame is None:
            return None
        
        p1 = self.canvas_to_frame_point(x0, y0)
        p2 = self.canvas_to_frame_point(x1, y1)
        
        # Ensure rect is valid (x1 < x2, y1 < y2)
        x_min = min(p1[0], p2[0])
        y_min = min(p1[1], p2[1])
        x_max = max(p1[0], p2[0])
        y_max = max(p1[1], p2[1])
        
        # Ensure minimum size (at least 10x10 pixels in frame coordinates)
        if (x_max - x_min) < 10 or (y_max - y_min) < 10:
            return None
        
        return (x_min, y_min, x_max, y_max)

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
        win = tk.Toplevel(self.root)
        win.title("Model Settings")
        win.geometry("400x200")
        win.configure(bg="#252525")
        
        tk.Label(win, text="Confidence Threshold", bg="#252525", fg="white").grid(row=0,column=0,sticky="w", padx=10, pady=5)
        var_conf = tk.DoubleVar(value=MODEL_CONFIG.get("confidence_threshold", 0.25))
        ttk.Entry(win, textvariable=var_conf).grid(row=0,column=1,sticky="ew", padx=10, pady=5)
        
        tk.Label(win, text="IoU Threshold", bg="#252525", fg="white").grid(row=1,column=0,sticky="w", padx=10, pady=5)
        var_iou = tk.DoubleVar(value=MODEL_CONFIG.get("iou_threshold", 0.45))
        ttk.Entry(win, textvariable=var_iou).grid(row=1,column=1,sticky="ew", padx=10, pady=5)
        
        tk.Label(win, text="Input Size", bg="#252525", fg="white").grid(row=2,column=0,sticky="w", padx=10, pady=5)
        var_imgsz = tk.IntVar(value=MODEL_CONFIG.get("input_size", 640))
        ttk.Entry(win, textvariable=var_imgsz).grid(row=2,column=1,sticky="ew", padx=10, pady=5)
        
        def save():
            try:
                MODEL_CONFIG["confidence_threshold"] = float(var_conf.get())
                MODEL_CONFIG["iou_threshold"] = float(var_iou.get())
                MODEL_CONFIG["input_size"] = int(var_imgsz.get())
                settings.save()
                messagebox.showinfo("Success", "Model settings saved!")
                win.destroy()
            except ValueError as e:
                messagebox.showerror("Error", f"Invalid value: {e}")
        
        tk.Button(win, text="Save", command=save, bg="#2e7d32", fg="white").grid(row=3,column=0,columnspan=2,pady=10)
        win.columnconfigure(1,weight=1)

    def db_settings(self):
        win = tk.Toplevel(self.root)
        win.title("DB Settings")
        win.geometry("450x300")
        win.configure(bg="#252525")
        
        entries={}
        for i,(k,v) in enumerate(DB_CONFIG.items()):
            tk.Label(win, text=k, bg="#252525", fg="white").grid(row=i,column=0,sticky="w", padx=10, pady=5)
            e=ttk.Entry(win)
            e.insert(0,str(v))
            e.grid(row=i,column=1,sticky="ew", padx=10, pady=5)
            entries[k]=e
        
        def save():
            try:
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
                messagebox.showinfo("Success", "DB settings saved!")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {e}")
        
        tk.Button(win, text="Save", command=save, bg="#2e7d32", fg="white").grid(row=len(entries),column=0,columnspan=2,pady=10)
        win.columnconfigure(1,weight=1)

    def reset_state(self):
        self.occupancy=0
        self.lbl_occupancy.config(text="Occupancy: 0")
        self.last_alert_state=None
        self.alert_list.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] RESET")
        self.alert_list.yview_moveto(1.0)
        self.lbl_status.config(text="Status: Reset Complete")

    def on_db_status(self, ok: bool):
        if ok:
            self.lbl_status.config(text="Status: DB Connected", fg="#28a745")
        else:
            self.lbl_status.config(text="Status: DB Disconnected", fg="#ff5555")

    # ------------- Close -------------
    def on_close(self):
        self.is_running = False
        self.is_preview = False
        
        # Stop continuous sound
        self.stop_continuous_sound()
        
        # Stop blink effect
        self.stop_blink_effect()
        
        time.sleep(0.1)  # Give threads time to finish
        
        with self.cap_lock:
            if self.cap:
                try: 
                    self.cap.release()
                except Exception: 
                    pass
                self.cap = None
        
        self.db.close()
        settings.save()
        self.root.destroy() 

def main():
    app = App()
    app.root.mainloop()

if __name__ == "__main__":
    main()