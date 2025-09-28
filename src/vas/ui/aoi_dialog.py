import tkinter as tk
from tkinter import ttk

class AOIModeDialog:
    def __init__(self, parent, current: str):
        self.parent = parent
        self.result = None
        self.win = tk.Toplevel(parent)
        self.win.title("AOI Mode")
        self.var_mode = tk.StringVar(value=current)
        ttk.Label(self.win, text="Pilih AOI Mode:").pack(padx=12, pady=(12,4))
        ttk.Combobox(self.win, textvariable=self.var_mode,
                     values=["rect","poly"], state="readonly").pack(padx=12, pady=4)
        frm = tk.Frame(self.win); frm.pack(pady=12)
        ttk.Button(frm, text="OK", command=self.on_ok).pack(side=tk.LEFT, padx=6)
        ttk.Button(frm, text="Cancel", command=self.win.destroy).pack(side=tk.LEFT, padx=6)
        self.win.grab_set()
    def on_ok(self):
        self.result = self.var_mode.get()
        self.win.destroy()