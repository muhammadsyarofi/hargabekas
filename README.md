# HargaBekas — Sistem Inspeksi Foto Kerusakan & Valuasi Kendaraan Bekas

**HargaBekas** adalah aplikasi web full-stack berdesain *Katalog Otomotif Editorial* yang memprediksi harga motor dan mobil bekas berdasarkan **data spesifikasi unit + analisis foto kerusakan fisik (lecet, penyok, retak, karat, dll.)**.

$$\text{Harga Akhir} = \text{Harga Dasar Kondisi Normal} - \text{Estimasi Biaya Perbaikan} - \text{Diskon Pasar Akibat Kerusakan}$$

---

## 1. Ringkasan Perubahan Struktur Folder

```text
hargabekas/
├── .env.example                      # [BARU] Template konfigurasi ANTHROPIC_API_KEY & mode analyzer
├── app.py                            # Entry point Flask
├── generate_dataset.py               # Generator dataset 1.800 baris (15 merek, 47 model mobil & motor)
├── train_model.py                    # Pipeline pelatihan ML (Gradient Boosting + Random Forest)
├── build_vehicle_photos.py           # Pembuat 141 aset foto studio 3-sudut (.webp)
├── requirements.txt                  # [DIUBAH] Tambah Pillow, python-dotenv, requests
├── README.md                         # [DIUBAH] Panduan API key, edit tabel biaya, & pengujian
├── data/
│   ├── repair_costs.json             # [BARU] Tabel biaya perbaikan per bagian, jenis, & keparahan (mudah diedit)
│   ├── vehicles_dataset.csv          # Dataset harga dasar kendaraan
│   └── hargabekas.db                 # Database SQLite (menyimpan unit, temuan JSON, path foto, & harga)
├── models/
│   ├── damage_analyzer.py            # [BARU] Pluggable Damage Analyzer (Claude Vision API + Fallback + YOLO Stub)
│   ├── predictor.py                  # [DIUBAH] Kalkulasi harga dasar - biaya perbaikan - diskon pasar + Waterfall
│   ├── database.py                   # [DIUBAH] Simpan/hapus riwayat beserta penghapusan file foto fisik
│   ├── credit.py                     # Kalkulator kredit Anuitas vs Bunga Flat + jadwal amortisasi
│   ├── price_model.joblib            # Artefak model scikit-learn
│   └── model_metadata.json           # Metrik evaluasi model (R², MAE, RMSE, MAPE)
├── routes/
│   ├── web.py                        # [DIUBAH] Rute halaman HTML dengan data tabel perbaikan
│   └── api.py                        # [DIUBAH] Tambah POST /api/analyze-photos, GET /api/repair-rates, rate limit
├── static/
│   ├── css/style.css                 # [DIUBAH] Gaya laporan inspeksi, BBox overlay, & peta SVG 2D interaktif
│   ├── js/vehicles.js                # [DIUBAH] Tambah renderInteractiveDamageMap (SVG 2D zona bodi mobil & motor)
│   ├── js/app.js                     # [DIUBAH] Stepper 5 langkah, kompresi foto klien, koreksi real-time, Waterfall
│   ├── img/vehicles/                 # 141 foto studio referensi (.webp)
│   └── uploads/inspections/          # [BARU] Folder terisolasi untuk foto unggahan pengguna (nama acak, tanpa EXIF)
├── templates/
│   ├── base.html                     # Layout utama + injeksi HB_REPAIR_TABLE
│   ├── index.html                    # [DIUBAH] Hero demo nyata "Foto -> Temuan -> Harga Akhir"
│   ├── prediksi.html                 # [DIUBAH] Stepper 5 langkah + Peta Kerusakan SVG 2D + Grafik Waterfall
│   ├── bandingkan.html               # [DIUBAH] Komparasi 2-3 unit + biaya perbaikan + "Mana lebih worth it?"
│   ├── kredit.html                   # [DIUBAH] Simulasi kredit + peringatan leasing untuk unit rusak berat
│   ├── riwayat.html                  # [DIUBAH] Kartu riwayat dengan thumbnail foto & badge kerusakan
│   └── tentang.html                  # [DIUBAH] Penjelasan arsitektur 2 tahap, keterbatasan jujur, & tabel tarif
└── tests/
    └── test_valuation_and_parser.py  # [BARU] Unit test parser JSON Vision, validasi magic bytes, & rumus harga
```

---

## 2. Instalasi & Cara Menjalankan

### Langkah 1: Instal Dependensi
```powershell
cd C:\Users\lenovo\.gemini\antigravity\scratch\hargabekas
pip install -r requirements.txt
```

### Langkah 2: Konfigurasi API Key (`.env`)
Salin `.env.example` menjadi `.env`:
```powershell
copy .env.example .env
```
Buka file `.env` dan isi `ANTHROPIC_API_KEY` Anda:
```env
DAMAGE_ANALYZER_MODE=claude
ANTHROPIC_API_KEY=sk-ant-api03-xxxx...
CLAUDE_VISION_MODEL=claude-3-5-sonnet-20241022
```
> **Catatan Mode Fallback/Offline:** Jika `ANTHROPIC_API_KEY` dikosongkan atau terjadi gangguan jaringan, sistem secara otomatis beralih dengan ramah ke **Mode Inspeksi Terbantu / Manual** sehingga aplikasi tetap berjalan penuh.

### Langkah 3: Melatih Model Harga Dasar (Opsional, model sudah tersedia)
```powershell
python generate_dataset.py
python train_model.py
```

### Langkah 4: Menjalankan Unit Test
```powershell
python -m unittest tests/test_valuation_and_parser.py
```

### Langkah 5: Menjalankan Server Aplikasi
```powershell
python app.py
```
Buka **`http://127.0.0.1:5000`** di browser Anda.

---

## 3. Cara Mengedit Tabel Biaya Perbaikan (`data/repair_costs.json`)
Seluruh tarif bengkel disimpan di `data/repair_costs.json` agar dapat diubah kapan saja tanpa perlu mengubah kode Python atau melatih ulang model ML:
- **`parts`**: Ubah `base_cost_mobil` atau `base_cost_motor` (dalam Rupiah) untuk mengatur biaya dasar per panel (`bumper_depan`, `pintu_kiri`, `kap_mesin`, `cover_body`, `rangka_sasis`, dll.).
- **`damage_types`**: Ubah `cost_factor` dan `action_label` untuk tiap jenis kerusakan (`lecet_ringan`, `goresan_dalam`, `penyok`, `retak`, `pecah`, `karat`, dll.).
- **`severity_multipliers`**: Ubah pengali biaya (`multiplier`) dan penalti pasar (`market_penalty_pct`) untuk skala keparahan `1` sampai `4`.
