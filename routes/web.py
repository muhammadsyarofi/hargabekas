"""
Blueprint Rute Halaman Web (HTML) HargaBekas.
Menyajikan 6 halaman utama: Beranda, Prediksi (Inspeksi 5 Langkah), Bandingkan, Simulasi Kredit, Riwayat, dan Tentang.
"""

from flask import Blueprint, render_template, request
from generate_dataset import CITY_FACTORS, SURAT_FACTORS, VEHICLE_CATALOG
from models.damage_analyzer import load_repair_costs_table
from models.database import get_history
from models.predictor import ensure_model_loaded, predict_vehicle_price

web_bp = Blueprint("web", __name__)


def get_popular_showcase():
    """Menyusun contoh kasus inspeksi nyata (unit dengan temuan kerusakan spesifik) untuk Beranda."""
    showcase_cases = [
        {
            "jenis": "mobil",
            "merek": "Honda",
            "model": "Brio RS",
            "tahun": 2022,
            "kilometer": 28500,
            "transmisi": "Otomatis",
            "bahan_bakar": "Bensin",
            "kondisi": 4,
            "kota": "Jakarta",
            "surat": "Lengkap (STNK + BPKB + Faktur)",
            "kerusakan": [
                {"bagian": "bumper_depan", "jenis": "goresan_dalam", "keparahan": 2, "perkiraan_luas_persen": 20},
                {"bagian": "pintu_kiri", "jenis": "penyok", "keparahan": 2, "perkiraan_luas_persen": 15},
            ],
        },
        {
            "mobil_or_motor": "mobil",
            "jenis": "mobil",
            "merek": "Toyota",
            "model": "Innova Zenix",
            "tahun": 2023,
            "kilometer": 19000,
            "transmisi": "Otomatis",
            "bahan_bakar": "Hybrid",
            "kondisi": 5,
            "kota": "Jakarta",
            "surat": "Lengkap (STNK + BPKB + Faktur)",
            "kerusakan": [
                {"bagian": "bumper_belakang", "jenis": "lecet_ringan", "keparahan": 1, "perkiraan_luas_persen": 10},
            ],
        },
        {
            "jenis": "mobil",
            "merek": "Mitsubishi",
            "model": "Pajero Sport Dakar",
            "tahun": 2021,
            "kilometer": 48000,
            "transmisi": "Otomatis",
            "bahan_bakar": "Diesel",
            "kondisi": 4,
            "kota": "Surabaya",
            "surat": "Lengkap (STNK + BPKB + Faktur)",
            "kerusakan": [
                {"bagian": "fender_depan", "jenis": "penyok", "keparahan": 2, "perkiraan_luas_persen": 25},
                {"bagian": "spion", "jenis": "retak", "keparahan": 2, "perkiraan_luas_persen": 30},
            ],
        },
        {
            "jenis": "motor",
            "merek": "Yamaha",
            "model": "NMAX 155",
            "tahun": 2023,
            "kilometer": 12000,
            "transmisi": "Otomatis",
            "bahan_bakar": "Bensin",
            "kondisi": 4,
            "kota": "Bandung",
            "surat": "Lengkap (STNK + BPKB + Faktur)",
            "kerusakan": [
                {"bagian": "cover_body", "jenis": "lecet_ringan", "keparahan": 1, "perkiraan_luas_persen": 15},
            ],
        },
        {
            "jenis": "motor",
            "merek": "Kawasaki",
            "model": "Ninja ZX-25R",
            "tahun": 2022,
            "kilometer": 9500,
            "transmisi": "Manual",
            "bahan_bakar": "Bensin",
            "kondisi": 4,
            "kota": "Jakarta",
            "surat": "Lengkap (STNK + BPKB + Faktur)",
            "kerusakan": [
                {"bagian": "cover_body", "jenis": "goresan_dalam", "keparahan": 2, "perkiraan_luas_persen": 20},
                {"bagian": "knalpot", "jenis": "lecet_ringan", "keparahan": 1, "perkiraan_luas_persen": 15},
            ],
        },
        {
            "jenis": "mobil",
            "merek": "Hyundai",
            "model": "Ioniq 5 Signature",
            "tahun": 2023,
            "kilometer": 15000,
            "transmisi": "Otomatis",
            "bahan_bakar": "Listrik (EV)",
            "kondisi": 5,
            "kota": "Jakarta",
            "surat": "Lengkap (STNK + BPKB + Faktur)",
            "kerusakan": [
                {"bagian": "velg_ban", "jenis": "lecet_ringan", "keparahan": 1, "perkiraan_luas_persen": 15},
            ],
        },
    ]
    results = []
    for cfg in showcase_cases:
        pred = predict_vehicle_price(cfg)
        results.append(
            {
                **cfg,
                "body_type": pred["body_type"],
                "harga_dasar_normal": pred["harga_dasar_normal"],
                "estimasi_biaya_perbaikan": pred["estimasi_biaya_perbaikan"],
                "diskon_pasar_rp": pred["diskon_pasar_rp"],
                "itemized_repairs": pred["itemized_repairs"],
                "harga_estimasi": pred["harga_estimasi"],
                "harga_min": pred["harga_min"],
                "harga_max": pred["harga_max"],
                "confidence": pred["confidence"],
                "annual_depr": pred["annual_depreciation_pct"],
            }
        )
    return results


@web_bp.route("/")
def index():
    """Halaman 1: Beranda (Demo Alur Foto -> Temuan Kerusakan -> Harga Akhir + Kasus Inspeksi)."""
    _, metadata = ensure_model_loaded()
    popular_vehicles = get_popular_showcase()
    return render_template(
        "index.html",
        active_page="beranda",
        catalog=VEHICLE_CATALOG,
        cities=list(CITY_FACTORS.keys()),
        surat_options=list(SURAT_FACTORS.keys()),
        repair_table=load_repair_costs_table(),
        popular_vehicles=popular_vehicles,
        metadata=metadata,
    )


@web_bp.route("/prediksi")
def prediksi():
    """Halaman 2: Prediksi Harga (Stepper 5 Langkah: Data Unit -> Unggah Foto -> Analisis -> Tinjau Temuan -> Hasil Waterfall)."""
    _, metadata = ensure_model_loaded()
    return render_template(
        "prediksi.html",
        active_page="prediksi",
        catalog=VEHICLE_CATALOG,
        cities=list(CITY_FACTORS.keys()),
        surat_options=list(SURAT_FACTORS.keys()),
        repair_table=load_repair_costs_table(),
        metadata=metadata,
    )


@web_bp.route("/bandingkan")
def bandingkan():
    """Halaman 3: Pembanding Harga (2-3 unit beserta temuan kerusakan & mana yang lebih worth it setelah perbaikan)."""
    return render_template(
        "bandingkan.html",
        active_page="bandingkan",
        catalog=VEHICLE_CATALOG,
        cities=list(CITY_FACTORS.keys()),
        surat_options=list(SURAT_FACTORS.keys()),
        repair_table=load_repair_costs_table(),
    )


@web_bp.route("/kredit")
def kredit():
    """Halaman 4: Simulasi Kredit (Anuitas vs Flat + peringatan leasing untuk unit dengan kerusakan struktural/berat)."""
    return render_template(
        "kredit.html",
        active_page="kredit",
    )


@web_bp.route("/riwayat")
def riwayat():
    """Halaman 5: Riwayat Prediksi (Kartu per prediksi dengan thumbnail foto, ringkasan kerusakan, dan hapus foto)."""
    jenis_filter = request.args.get("jenis", "").strip().lower()
    records = get_history(limit=50, jenis_filter=jenis_filter if jenis_filter in ("motor", "mobil") else None)
    return render_template(
        "riwayat.html",
        active_page="riwayat",
        records=records,
        jenis_filter=jenis_filter,
    )


@web_bp.route("/tentang")
def tentang():
    """Halaman 6: Tentang Model (Arsitektur 2 tahap: ML Harga Dasar + Vision Damage Analyzer + Tabel Biaya Perbaikan)."""
    _, metadata = ensure_model_loaded()
    return render_template(
        "tentang.html",
        active_page="tentang",
        metadata=metadata,
        catalog=VEHICLE_CATALOG,
        repair_table=load_repair_costs_table(),
    )
