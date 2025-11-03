import tkinter as tk
from tkinter import ttk

class SettingsDialog:
    def __init__(self, parent, section: dict, title="Settings"):
        self.parent = parent
        self.section = section
        self.result = None
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.entries = {}
        row = 0
        for k, v in self.section.items():
            ttk.Label(self.win, text=k).grid(row=row, column=0, sticky="w", padx=6, pady=4)
            e = ttk.Entry(self.win)
            e.insert(0, str(v))
            e.grid(row=row, column=1, sticky="ew", padx=6, pady=4)
            self.entries[k] = e
            row += 1
        btns = tk.Frame(self.win); btns.grid(row=row, column=0, columnspan=2, pady=8)
        ttk.Button(btns, text="OK", command=self.on_ok).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text="Cancel", command=self.win.destroy).pack(side=tk.LEFT, padx=4)
        self.win.columnconfigure(1, weight=1)
        self.win.grab_set()
    def on_ok(self):
        out = {}
        for k,e in self.entries.items():
            txt = e.get().strip()
            if txt.lower() in ("true","false"):
                out[k] = (txt.lower()=="true")
            else:
                try:
                    if "." in txt:
                        out[k] = float(txt)
                    else:
                        out[k] = int(txt)
                except Exception:
                    out[k] = txt
        self.result = out
        self.win.destroy()