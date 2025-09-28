


# 🧟‍♂️ Curug Watcher: Person Counter in a Haunted Waterfall

> “Di balik gemuruh air yang jatuh… ada sesuatu yang juga sedang mengamati.”  
> Aplikasi ini memantau keberadaan manusia di area wisata Curug—tetapi sekarang bergaya horror.  
> Di atas feed kamera, kamu bisa menambahkan sosok `Genderuwo` sebagai overlay (misal untuk hiburan / event malam).  

![download](https://github.com/user-attachments/assets/3be16855-9cf7-4fb3-8081-835dfae1f271)
---

## 🩸 Konsep Singkat

Curug Watcher menghitung jumlah orang (occupancy) yang berada di dalam Area of Interest (AOI) sebuah area curug (air terjun).  
Tidak ada tracking unik—hanya hitungan langsung per frame (siapa yang tertangkap di area).  
Sistem dapat memberikan “ALERT” ketika area mulai dihuni... atau tiba-tiba kosong—seolah ada sesuatu yang membuat mereka menghilang.

---

## 👁️ Fitur Utama (Versi Horror)

| Fitur | Deskripsi Mencekam |
|-------|--------------------|
| Deteksi Person (YOLO) | Mendeteksi siluet manusia yang “berani” mendekat ke area curug |
| AOI Rect / Polygon | Tandai batas area terlarang / “zona kabut” |
| Real-time Occupancy | Tahu berapa jiwa yang sedang berada “dalam lingkaran” |
| Alert Toggle | Nyala: sistem berbisik “AREA OCCUPIED” / “AREA CLEAR” hanya saat berubah |
| Manual DB Store | Simpan snapshot jumlah jiwa ke database (MySQL) |
| Screen / Webcam / Stream | Bisa pantau CCTV, rekaman sungai, atau RTSP hutan |
| Tanpa Tracking | Ringan—tidak menguntit tiap individu… (yang menguntit mungkin yang lain) |
| Gambar Genderuwo | Letakkan overlay PNG untuk efek gangguan supranatural |

---

## 🕯️ Arsitektur Gelap

```
[ Video Source ]
      ↓
 Screen / Cam / Stream
      ↓
YOLO Inference (person)
      ↓
Filter AOI (Rect / Polygon)
      ↓
 Instant Occupancy Count
      ↓
 Alert State (Occupied / Clear)
      ↓
 Manual DB Save (vas_person_counts)
```

---

## 🧪 Teknologi Ritual

- Python + Ultralytics YOLO
- OpenCV
- Tkinter GUI
- MySQL (opsional logging)
- MSS / PIL untuk screen capture
- Tanpa pelacakan ID (agar roh berjalan bebas)

---

## ⚙️ Konfigurasi (settings.json Contoh)

```json
{
  "model": {
    "model_path": "yolov8n.pt",
    "confidence_threshold": 0.35,
    "iou_threshold": 0.5,
    "detection_confidence": 0.3,
    "device": "auto"
  },
  "runtime": {
    "imgsz": 640,
    "use_half": true,
    "detection_stride": 1,
    "flush_frames": 2,
    "use_mss_screen_capture": true
  },
  "input": {
    "type": "screen",
    "webcam_index": 0,
    "stream_url": "",
    "screen_region": null
  },
  "aoi": {
    "mode": "rect",
    "rect": null,
    "polygon": []
  },
  "alerts": {
    "enabled": true
  },
  "database": {
    "enable": false,
    "type": "mysql",
    "host": "localhost",
    "port": 3306,
    "user": "vas_user",
    "password": "your_password_here",
    "name": "vas_db"
  }
}
```

---

## 🔧 Instalasi

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

(Opsional, jika pakai layout `src/` + pyproject)
```bash
pip install -e .
```

Unduh model (sekali):
```bash
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

---

## ▶️ Menjalankan

```bash
python -m vas.main
```

Jika tidak install editable:
```bash
set PYTHONPATH=%CD%\\src
python -m vas.main
```

---

## 🩻 Operasional GUI

1. Pilih sumber input (Screen / Webcam / Network).
2. Jika Screen → Select Region atau Full Screen.
3. Bentuk AOI:  
   - Rect: tombol “Set Rect” (klik & drag).  
   - Polygon: “Draw Polygon” (klik titik-titik → klik kanan untuk selesai).
4. Preview → cek.
5. Start Counting.
6. Toggle Alerts (ON = log saat status berubah).
7. Store to DB → catat occupancy.
8. Tambah overlay genderuwo di canvas (modifikasi di kode: setelah frame, sebelum tampil).

---

## 🧛 Mekanisme Alert

| Keadaan | Pesan | Warna |
|---------|-------|-------|
| Awal ada orang | `AREA OCCUPIED (N)` | Merah |
| Berubah jadi kosong | `AREA CLEAR` | Hijau |
| Alert dimatikan | Tidak ada transisi baru | Abu-abu |

> Tidak ada spam—hanya di-trigger saat perubahan status (makhluk masuk / keluar).

---

## 💾 Database (Opsional)

Buat tabel:
```sql
CREATE TABLE IF NOT EXISTS vas_person_counts (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  occupancy INT NOT NULL,
  note VARCHAR(255) NULL
) ENGINE=InnoDB;
```

Set di `settings.json`:
```json
"database": { "enable": true, ... }
```

---

## 👻 Menambahkan Overlay Genderuwo

Letakkan file:
```
assets/images/genderuwo.png
```

Di dalam kode (misal di `main.py`, setelah frame diubah ke PIL Image):
```python
overlay = Image.open("assets/images/genderuwo.png").convert("RGBA")
img_rgba = img.convert("RGBA")
img_rgba.alpha_composite(overlay.resize((w_overlay, h_overlay)), (x_pos, y_pos))
img = img_rgba.convert("RGB")
```

---

## 🧟 Ide Pengembangan Lanjutan

| Ide | Efek Horror |
|-----|-------------|
| Random hallucination overlay | Genderuwo muncul saat occupancy turun drastis |
| Slow fade filter | Simulasikan kabut lembab di malam hari |
| Auto snapshot interval | Simpan histori “keberadaan jiwa” |
| Telegram Bot | Kirim pesan “Ada yang masuk area terlarang” |
| Heatmap | Jejak intensitas kehadiran (energi spiritual?) |
| Mode Night Inference | Adjust gamma / CLAHE sebelum deteksi |

---

## ⚠️ Batasan

| Hal | Status |
|-----|-------|
| Unique person counting | ❌ |
| Masuk / keluar jalur | ❌ |
| Dwell time | ❌ |
| Multi-AOI | ❌ (bisa ditambah list AOI) |
| Anti duplikasi bounding noise | Partial (bisa tambah filtering ukuran) |

Jika butuh semua itu → harus aktifkan kembali tracking.

---

## 🕯️ Etika & Catatan

- Jangan gunakan untuk menakut-nakuti pengunjung tanpa izin.
- Overlay mitologi (Genderuwo) bersifat hiburan / tema event.
- Pastikan mematuhi privasi pengunjung (tidak menyimpan wajah).

---

## 📝 Lisensi

Tambahkan LICENSE (disarankan MIT) bila akan dipublikasikan.

---

## 🤝 Kontribusi

PR: tambah efek horror, mode malam, atau integrasi sensor kabut?  
Silakan kirim—“Semakin gelap, semakin hidup.”

---

## 🩶 Penutup

> “Kalau counter menunjukkan 0 tapi kamu masih merasa ada yang berdiri di belakang… mungkin sistem belum sempat mendeteksi.”

Selamat menjaga Curug. 🌫️
