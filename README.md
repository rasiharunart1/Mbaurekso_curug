<img width="1920" height="1080" alt="image" src="https://github.com/user-attachments/assets/mbaurekso.jpg" />


# Person AOI Counter

Sistem ringan untuk menghitung jumlah orang (class `person`) yang berada di dalam Area of Interest (AOI) pada sumber video (screen capture, webcam, atau stream).  
Fokus: real-time occupancy (bukan tracking orang unik), toggle alert sederhana, dan penyimpanan snapshot manual ke MySQL.

---

## ✨ Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| Deteksi Person | Menggunakan YOLO (Ultralytics) – hanya class `person` (COCO id=0) |
| AOI Rectangle / Polygon | Hitung hanya bbox (titik tengah) yang berada di dalam AOI |
| Occupancy Real-time | Jumlah orang yang terlihat dalam AOI pada frame saat ini |
| Alert Toggle | Tombol ON/OFF – menulis log “AREA OCCUPIED” atau “AREA CLEAR” ketika status berubah |
| Manual DB Store | Tombol “Store to DB” menyimpan `occupancy` + timestamp ke tabel `vas_person_counts` |
| Screen / Webcam / Network | Sumber input fleksibel (desktop region, kamera USB, RTSP/HTTP stream) |
| Tanpa Tracking | Sederhana & cepat; tidak ada perhitungan masuk/keluar atau unique visitors |
| Konfigurasi Persisten | `settings.json` otomatis terbuat & disimpan setiap perubahan UI |
| MySQL Opsional | Dapat dimatikan melalui konfigurasi |

---

## 🧱 Arsitektur Sederhana

```
+------------------+
|  Video Source    |  (Screen / Webcam / Network)
+---------+--------+
          |
          v
   Frame Capture
          |
          v
   YOLO Inference (person only)
          |
          v
  Filter by AOI  ---> Occupancy Count ---> Alert State (if enabled)
          |
   (Manual) Store to DB (snapshot)
```

---

## 📂 Struktur Direktori (Model "src layout")

```
project_root/
├─ pyproject.toml
├─ requirements.txt
├─ settings.json          # (otomatis dibuat saat runtime, bisa diedit manual)
└─ src/
   └─ vas/
      ├─ __init__.py
      ├─ main.py
      ├─ config.py
      ├─ detection.py
      ├─ db_manager.py
      └─ utils/
         └─ screen_capture.py
```

> Jika ingin struktur sederhana tanpa `src/`, letakkan folder `vas/` langsung di root dan jalankan `python -m vas.main`.

---

## 🛠️ Instalasi

### 1. Siapkan Lingkungan Virtual

Windows (CMD / PowerShell):
```bash
python -m venv .venv
.venv\Scripts\activate
```

Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependensi

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. (Opsional) Editable Install

Jika menggunakan `pyproject.toml` + layout `src/`:
```bash
pip install -e .
```

### 4. Download / Siapkan Weights YOLO

Default memakai nama `yolov8n.pt`.  
Jika belum ada, jalankan sekali (Ultralytics akan otomatis unduh):

```bash
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

Atau ganti `model_path` di `settings.json`.

---

## ▶️ Menjalankan Aplikasi

```bash
python -m vas.main
```

Jika tidak pakai editable install + layout `src/`:
```bash
set PYTHONPATH=%CD%\src     # Windows
export PYTHONPATH=$PWD/src  # Linux/macOS
python -m vas.main
```

---

## ⚙️ Konfigurasi (settings.json)

Contoh (akan dibuat otomatis saat pertama kali jalan):

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

## 🟥 Database (Opsional)

### Skema Tabel

```sql
CREATE DATABASE IF NOT EXISTS vas_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE vas_db;

CREATE TABLE IF NOT EXISTS vas_person_counts (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  occupancy INT NOT NULL,
  note VARCHAR(255) NULL
) ENGINE=InnoDB;
```

### User Khusus (Disarankan)

```sql
CREATE USER 'vas_user'@'%' IDENTIFIED BY 'your_password_here';
GRANT ALL PRIVILEGES ON vas_db.* TO 'vas_user'@'%';
FLUSH PRIVILEGES;
```

### Menyimpan Snapshot

Klik tombol `Store to DB` → Insert satu baris (occupancy & note).

---

## 🖱️ Operasional UI

| Langkah | Aksi |
|---------|------|
| 1 | Pilih Input Source (screen / webcam / network) |
| 2 | Jika screen: pilih region (Select Region / Full Screen) |
| 3 | (Opsional) Tentukan AOI: Set Rect atau Draw Polygon |
| 4 | Klik Preview (cek framing) |
| 5 | Klik Start Counting |
| 6 | Toggle Alerts (On/Off) sesuai kebutuhan |
| 7 | Tekan Store to DB untuk menyimpan snapshot manual |
| 8 | Clear AOI jika ingin ganti area |

---

## 🔔 Mekanisme Alert

| Kondisi | Log Ditulis | State Label |
|---------|-------------|-------------|
| Occupancy > 0 (berubah dari kosong) | `[HH:MM:SS] AREA OCCUPIED (N)` | OCCUPIED (Merah) |
| Occupancy == 0 (berubah dari ada orang) | `[HH:MM:SS] AREA CLEAR` | CLEAR (Hijau) |
| Alerts OFF | Tidak ada transisi baru | DISABLED (Abu-abu) |

---

## 🚫 Keterbatasan (Tanpa Tracking)

| Hal | Status |
|-----|--------|
| Hitung unik orang | ❌ Tidak didukung |
| Arah masuk / keluar | ❌ |
| Dwell time (lama tinggal) | ❌ |
| Filtering blur/small | ⚠️ Bisa tambahkan logika tambahan jika perlu |
| Smoothing occupancy | ❌ (bisa ditambah moving average) |

Jika Anda membutuhkan hal-hal di atas → perlu integrasi tracker (ByteTrack / StrongSORT) dan state manajemen tambahan.

---

## 🧪 Troubleshooting

| Masalah | Penyebab Umum | Solusi |
|---------|---------------|--------|
| `ModuleNotFoundError: vas` | Belum install editable / PYTHONPATH belum diset | `pip install -e .` atau set PYTHONPATH |
| FPS rendah | GPU tidak dipakai / model besar | Pakai `yolov8n.pt`, set `device` ke `cuda` |
| Tidak ada bounding box | Model_path salah / threshold terlalu tinggi | Cek file model & turunkan `confidence_threshold` |
| DB Store gagal | DB disabled / kredensial salah | Set `"enable": true` dan cek user/password |
| AOI tidak terdeteksi | Lupa klik kanan untuk akhiri polygon | Selesaikan polygon (≥3 titik) |

---

## 🚀 Roadmap (Opsional)

| Prioritas | Fitur |
|-----------|-------|
| Medium | Smoothing occupancy (EMA / median) |
| Medium | Auto snapshot interval ke DB |
| High | Mode tracking untuk unique & dwell |
| Low | Notifikasi Telegram (Webhook) |
| Low | Ekspor CSV dari DB UI sederhana |
| Low | Packaging PyInstaller |

---

## 🔐 Keamanan

- Jalankan hanya model terpercaya.
- Jika network stream → pertimbangkan enkripsi (RTSP over TLS).
- User DB terpisah dengan hak terbatas.

---

## 🧾 Lisensi

Silakan tentukan (MIT / Apache-2.0 / GPL-3.0).  
Tambahkan file `LICENSE` bila dipublikasikan.

---

## 🙋 Dukungan / Pengembangan

Butuh:
- Tracking & dwell time?
- Notifikasi otomatis?
- Heatmap kepadatan?

Tinggal ajukan permintaan fitur berikutnya.

Selamat menggunakan Person AOI Counter! 🎉
