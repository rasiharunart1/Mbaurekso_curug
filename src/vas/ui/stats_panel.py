import tkinter as tk

class StatsPanel(tk.Frame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.lbl_unique = tk.Label(self, text="Unique: 0", anchor="w", fg="#ffffff", bg=self["bg"])
        self.lbl_current = tk.Label(self, text="Occupancy: 0", anchor="w", fg="#28a745", bg=self["bg"])
        self.lbl_longest = tk.Label(self, text="Longest Dwell: 0s", anchor="w", fg="#ffaa00", bg=self["bg"])
        self.lbl_unique.pack(fill=tk.X, pady=2)
        self.lbl_current.pack(fill=tk.X, pady=2)
        self.lbl_longest.pack(fill=tk.X, pady=2)
    def update_stats(self, summary):
        self.lbl_unique.config(text=f"Unique: {summary['unique']}")
        self.lbl_current.config(text=f"Occupancy: {summary['current']}")
        self.lbl_longest.config(text=f"Longest Dwell: {summary['longest_dwell']}s")