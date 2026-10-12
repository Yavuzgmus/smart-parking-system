# 🅿️ Smart Parking System

A parking management system that **automatically reads Turkish license plates** from a camera feed, logs vehicle entries and exits, assigns each vehicle a free parking spot and **calculates the fee** based on how long it stayed.

![Parking map](docs/ekran_harita.png)

> The user interface is in Turkish.

## Features

- **License plate recognition:** a YOLO model trained on Roboflow locates the plate, and EasyOCR reads the characters.
- **Turkish plate validation:** the text is checked against Turkish plate rules (province code, letters, digits). Common OCR mix-ups such as `O/0`, `I/1` and `B/8` are corrected automatically.
- **Automatic entry and exit:** a vehicle that is not inside gets an entry record and a random free spot. When the same vehicle is read again, it is checked out and its fee is calculated.
- **Desktop dashboard (PyQt6):**
  - Live camera feed with a colored box around the detected plate
  - Live parking map with 3 floors × 10 spots
  - Cards for occupancy, vehicles inside, today's entries and today's revenue
  - Plate search that highlights matching spots on the map
  - Vehicle log table with filtering and CSV (Excel) export
  - Plate reading from a photo, manual plate entry and manual checkout
- **Protection against mistakes:** if the same plate is read again within 10 seconds, the read is ignored. When the lot is full, the vehicle is not let in.

![Vehicle log](docs/ekran_kayitlar.png)

## Tech stack

| Area | Technology |
|---|---|
| Plate detection | Roboflow `inference`, YOLO model (`turkish-license-plate/8`) |
| Character recognition | EasyOCR |
| Image processing | OpenCV, NumPy |
| User interface | PyQt6 |
| Database | SQLite (WAL mode) |

## Installation

**Requirement:** Python 3.10 or newer

```bash
git clone https://github.com/Yavuzgmus/akilli-otopark.git
cd akilli-otopark
pip install -r requirements.txt
```

Set your Roboflow API key: copy `.env.example` in the project root to a file named `.env` and fill in your key.

```
ROBOFLOW_API_KEY=your_api_key_here
```

> `.env` is listed in `.gitignore`, so it is never pushed to GitHub.

## Usage

```bash
python src/otopark_arayuz.py
```

The database (`otopark.db`) is created automatically on first launch.

| Shortcut | Action |
|---|---|
| `Space` | Read the plate in the camera view |
| `Ctrl+F` | Search for a plate |
| `F5` | Refresh data |
| Right-click an occupied spot | Check the vehicle out manually |
| Right-click a row in the log table | Delete the record |

### Other scripts

```bash
python src/canli_kamera.py                          # Console mode with a simple OpenCV window
python src/yolo_plaka_tanima.py photo.jpg           # Read a plate from a photo and record it
python src/yolo_plaka_tanima.py photo.jpg --kaydetme # Read only, do not write to the database
python src/veritabani_kurulum.py                    # Set up / migrate the database manually
python src/kayit_sil.py --id 7                      # Delete a single record
python src/kayit_sil.py --hepsi                     # Delete all records
```

## Project structure

```
akilli-otopark/
├── src/
│   ├── otopark_arayuz.py      # Main desktop application (PyQt6)
│   ├── plaka_okuma.py         # Plate detection + OCR + Turkish plate validation
│   ├── veritabani.py          # SQLite layer: entry/exit, spots, statistics
│   ├── ayarlar.py             # All settings (floors, spots, pricing, model, camera)
│   ├── canli_kamera.py        # Console mode
│   ├── yolo_plaka_tanima.py   # Read plates from a photo
│   ├── kayit_sil.py           # Record deletion tool
│   └── veritabani_kurulum.py  # Database setup
├── docs/                      # Screenshots
├── .env.example               # Example settings file
├── requirements.txt
└── README.md
```

`.env` and `otopark.db` live in the project root, so run the commands from the root folder.

## Configuration

The number of floors and spots, the pricing and the detection threshold are defined in [`src/ayarlar.py`](src/ayarlar.py). The following values can also be set in `.env` or as environment variables:

| Variable | Description | Default |
|---|---|---|
| `ROBOFLOW_API_KEY` | Roboflow API key | — (required) |
| `OTOPARK_DB` | Path to the database file | `./otopark.db` |
| `OTOPARK_KAMERA` | Camera index | `0` |

**Pricing:** a 20 ₺ entry fee plus 0.10 ₺ for every second parked. This is a demo rate and can be changed in `src/ayarlar.py`.

## Database schema

**`arac_kayitlari`** (vehicle log): `id`, `plaka` (plate), `giris_zamani` (entry time), `cikis_zamani` (exit time), `ucret` (fee), `durum` (status: `İçeride` = inside / `Çıkış Yaptı` = checked out), `slot_no`

**`otopark_slotlari`** (parking spots): `slot_id`, `kat` (floor), `kat_slot_no` (spot number on the floor), `slot_etiketi` (label, e.g. `K2-S5`), `durum` (status: `Boş` = free / `Dolu` = occupied), `park_eden_plaka` (plate of the parked vehicle)
