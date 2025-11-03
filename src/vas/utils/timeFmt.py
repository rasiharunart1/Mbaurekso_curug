def fmt_hms(seconds: int):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h>0: return f"{h}h {m}m {s}s"
    if m>0: return f"{m}m {s}s"
    return f"{s}s"