import tkinter as tk

class AlertPanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.listbox = tk.Listbox(self, bg="#1b1b1b", fg="#ff6666", height=20)
        self.listbox.pack(fill=tk.BOTH, expand=True)
    def set_alerts(self, alerts):
        self.listbox.delete(0, tk.END)
        for a in alerts:
            self.listbox.insert(tk.END, f"[{a['time']}] {a['type']} - {a['message']}")
    def clear(self):
        self.listbox.delete(0, tk.END)