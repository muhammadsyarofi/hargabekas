"""
Modul Database SQLite untuk menyimpan dan mengelola Riwayat Prediksi & Inspeksi Foto HargaBekas.
Saat riwayat dihapus, file foto hasil unggahan pengguna yang terkait juga ikut dihapus dari server.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "hargabekas.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "inspections")


def get_db_connection() -> sqlite3.Connection:
    """Membuka koneksi SQLite dengan row_factory sqlite3.Row."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Menginisialisasi tabel riwayat prediksi beserta kolom inspeksi kerusakan dan migrasi otomatis."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS prediction_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jenis TEXT NOT NULL,
            merek TEXT NOT NULL,
            model TEXT NOT NULL,
            body_type TEXT NOT NULL,
            tahun INTEGER NOT NULL,
            kilometer INTEGER NOT NULL,
            transmisi TEXT NOT NULL,
            bahan_bakar TEXT NOT NULL,
            kondisi INTEGER NOT NULL,
            kondisi_detail TEXT DEFAULT '',
            surat TEXT DEFAULT 'Lengkap (STNK + BPKB + Faktur)',
            kota TEXT NOT NULL,
            warna TEXT DEFAULT '#D9381E',
            harga_dasar_normal INTEGER DEFAULT 0,
            total_biaya_perbaikan INTEGER DEFAULT 0,
            diskon_pasar_rp INTEGER DEFAULT 0,
            has_structural_damage INTEGER DEFAULT 0,
            damages_json TEXT DEFAULT '[]',
            photos_json TEXT DEFAULT '[]',
            harga_estimasi INTEGER NOT NULL,
            harga_min INTEGER NOT NULL,
            harga_max INTEGER NOT NULL,
            confidence INTEGER NOT NULL,
            factors_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

    # Migrasi aman untuk database yang sudah ada sebelumnya
    cursor.execute("PRAGMA table_info(prediction_history)")
    existing_cols = {row["name"] for row in cursor.fetchall()}
    migrations = [
        ("kondisi_detail", "TEXT DEFAULT ''"),
        ("surat", "TEXT DEFAULT 'Lengkap (STNK + BPKB + Faktur)'"),
        ("harga_dasar_normal", "INTEGER DEFAULT 0"),
        ("total_biaya_perbaikan", "INTEGER DEFAULT 0"),
        ("diskon_pasar_rp", "INTEGER DEFAULT 0"),
        ("has_structural_damage", "INTEGER DEFAULT 0"),
        ("damages_json", "TEXT DEFAULT '[]'"),
        ("photos_json", "TEXT DEFAULT '[]'"),
    ]
    for col_name, col_def in migrations:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE prediction_history ADD COLUMN {col_name} {col_def}")
    conn.commit()

    cursor.execute("SELECT COUNT(*) as total FROM prediction_history")
    count = cursor.fetchone()["total"]
    if count == 0:
        sample_records = [
            (
                "mobil",
                "Honda",
                "Brio RS",
                "hatchback",
                2022,
                28500,
                "Otomatis",
                "Bensin",
                4,
                "Cat & Bodi Orisinil, Mesin Kering & Halus",
                "Lengkap (STNK + BPKB + Faktur)",
                "Jakarta",
                "#D9381E",
                210500000,
                2150000,
                3500000,
                0,
                json.dumps(
                    [
                        {
                            "no": 1,
                            "bagian": "bumper_depan",
                            "bagian_label": "Bumper Depan",
                            "jenis": "goresan_dalam",
                            "jenis_label": "Goresan Dalam (Tembus Cat Dasar)",
                            "keparahan": 2,
                            "estimasi_biaya": 900000,
                        },
                        {
                            "no": 2,
                            "bagian": "pintu_kiri",
                            "bagian_label": "Panel Pintu Samping Kiri",
                            "jenis": "penyok",
                            "jenis_label": "Penyok / Deformasi Panel (Dent)",
                            "keparahan": 2,
                            "estimasi_biaya": 1250000,
                        },
                    ]
                ),
                json.dumps(["/static/img/vehicles/honda-brio-rs.webp"]),
                204850000,
                196500000,
                213000000,
                93,
                json.dumps([]),
                "2025-02-12 14:20 WIB",
            ),
            (
                "motor",
                "Yamaha",
                "NMAX 155",
                "matic",
                2023,
                14200,
                "Otomatis",
                "Bensin",
                4,
                "Servis Rutin Resmi",
                "Lengkap (STNK + BPKB + Faktur)",
                "Bandung",
                "#D9381E",
                28200000,
                450000,
                200000,
                0,
                json.dumps(
                    [
                        {
                            "no": 1,
                            "bagian": "cover_body",
                            "bagian_label": "Fairing / Cover Body Samping Motor",
                            "jenis": "lecet_ringan",
                            "jenis_label": "Lecet Ringan / Swirl / Baret Halus",
                            "keparahan": 1,
                            "estimasi_biaya": 450000,
                        }
                    ]
                ),
                json.dumps(["/static/img/vehicles/yamaha-nmax-155.webp"]),
                27550000,
                26400000,
                28700000,
                94,
                json.dumps([]),
                "2025-02-13 09:45 WIB",
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO prediction_history (
                jenis, merek, model, body_type, tahun, kilometer, transmisi,
                bahan_bakar, kondisi, kondisi_detail, surat, kota, warna,
                harga_dasar_normal, total_biaya_perbaikan, diskon_pasar_rp, has_structural_damage,
                damages_json, photos_json, harga_estimasi, harga_min, harga_max,
                confidence, factors_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sample_records,
        )
        conn.commit()
    conn.close()


def save_prediction(record: Dict) -> int:
    """Menyimpan satu hasil prediksi beserta rincian kerusakan & path foto ke SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M WIB")
    cursor.execute(
        """
        INSERT INTO prediction_history (
            jenis, merek, model, body_type, tahun, kilometer, transmisi,
            bahan_bakar, kondisi, kondisi_detail, surat, kota, warna,
            harga_dasar_normal, total_biaya_perbaikan, diskon_pasar_rp, has_structural_damage,
            damages_json, photos_json, harga_estimasi, harga_min,
            harga_max, confidence, factors_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["jenis"],
            record["merek"],
            record["model"],
            record.get("body_type", "sedan"),
            int(record["tahun"]),
            int(record["kilometer"]),
            record["transmisi"],
            record["bahan_bakar"],
            int(record.get("kondisi", 4)),
            record.get("kondisi_detail", ""),
            record.get("surat", "Lengkap (STNK + BPKB + Faktur)"),
            record["kota"],
            record.get("warna", "#D9381E"),
            int(record.get("harga_dasar_normal", record["harga_estimasi"])),
            int(record.get("estimasi_biaya_perbaikan", 0)),
            int(record.get("diskon_pasar_rp", 0)),
            1 if record.get("has_structural_damage") else 0,
            json.dumps(record.get("itemized_repairs", []), ensure_ascii=False),
            json.dumps(record.get("photos", []), ensure_ascii=False),
            int(record["harga_estimasi"]),
            int(record["harga_min"]),
            int(record["harga_max"]),
            int(record["confidence"]),
            json.dumps(record.get("factors", []), ensure_ascii=False),
            created_at,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def get_history(limit: int = 50, jenis_filter: Optional[str] = None) -> List[Dict]:
    """Mengambil daftar riwayat prediksi terbaru dari SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if jenis_filter in ("motor", "mobil"):
        cursor.execute(
            "SELECT * FROM prediction_history WHERE jenis = ? ORDER BY id DESC LIMIT ?",
            (jenis_filter, limit),
        )
    else:
        cursor.execute("SELECT * FROM prediction_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        item = dict(row)
        try:
            item["factors"] = json.loads(item.get("factors_json") or "[]")
        except Exception:
            item["factors"] = []
        try:
            item["damages"] = json.loads(item.get("damages_json") or "[]")
        except Exception:
            item["damages"] = []
        try:
            item["photos"] = json.loads(item.get("photos_json") or "[]")
        except Exception:
            item["photos"] = []
        if not item.get("harga_dasar_normal"):
            item["harga_dasar_normal"] = item["harga_estimasi"]
        results.append(item)
    return results


def _remove_uploaded_photos(photos_json_str: str) -> None:
    """Menghapus file foto di folder `static/uploads/inspections/` yang terkait dengan riwayat."""
    try:
        photo_urls = json.loads(photos_json_str or "[]")
    except Exception:
        photo_urls = []
    for url in photo_urls:
        if isinstance(url, str) and "/static/uploads/inspections/" in url:
            fname = os.path.basename(url)
            if fname.startswith("insp_"):
                fpath = os.path.join(UPLOAD_DIR, fname)
                if os.path.exists(fpath):
                    try:
                        os.remove(fpath)
                    except OSError:
                        pass


def delete_history_item(item_id: int) -> bool:
    """Menghapus satu riwayat prediksi berdasarkan ID beserta file foto fisiknya."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT photos_json FROM prediction_history WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    if row and row["photos_json"]:
        _remove_uploaded_photos(row["photos_json"])

    cursor.execute("DELETE FROM prediction_history WHERE id = ?", (item_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def clear_all_history() -> int:
    """Menghapus seluruh riwayat prediksi beserta seluruh foto unggahan terkait."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT photos_json FROM prediction_history")
    for row in cursor.fetchall():
        if row["photos_json"]:
            _remove_uploaded_photos(row["photos_json"])

    cursor.execute("DELETE FROM prediction_history")
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count
