"""
Blueprint Endpoint REST API JSON HargaBekas (Edisi Inspeksi Kerusakan Foto & Valuasi).
Menyediakan endpoint:
- POST /api/analyze-photos (Validasi magic bytes, strip EXIF/GPS, analisis foto via Vision AI / Fallback)
- GET  /api/repair-rates   (Tabel referensi biaya perbaikan per bagian & tingkat keparahan)
- POST /api/predict        (Valuasi harga dasar normal - biaya perbaikan - diskon pasar + data Waterfall)
- POST /api/compare        (Perbandingan 2-3 kendaraan termasuk biaya perbaikan & 'Worth It Setelah Perbaikan')
- POST /api/credit         (Simulasi kredit Anuitas vs Bunga Flat + jadwal amortisasi)
- GET/POST/DELETE /api/history (Manajemen riwayat prediksi & foto di SQLite)
- GET  /api/catalog        (Data katalog kendaraan, kota, surat, dan tabel biaya perbaikan)
"""

import base64
import time
from typing import Dict, List
from flask import Blueprint, jsonify, request
from generate_dataset import CITY_FACTORS, CURRENT_YEAR, SURAT_FACTORS, VEHICLE_CATALOG
from models.credit import calculate_credit_simulation, validate_credit_payload
from models.damage_analyzer import (
    MAX_PHOTOS,
    analyze_vehicle_photos,
    load_repair_costs_table,
    sanitize_and_save_photo,
)
from models.database import clear_all_history, delete_history_item, get_history, save_prediction
from models.predictor import predict_vehicle_price, validate_prediction_payload

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Rate limiter sederhana di memori (per IP) untuk melindungi endpoint analisis foto
_RATE_LIMIT_WINDOW_SEC = 60
_MAX_ANALYZE_REQ_PER_MIN = 20
_ip_request_timestamps: Dict[str, List[float]] = {}


def _check_rate_limit(client_ip: str) -> bool:
    now = time.time()
    history = _ip_request_timestamps.get(client_ip, [])
    history = [ts for ts in history if now - ts < _RATE_LIMIT_WINDOW_SEC]
    if len(history) >= _MAX_ANALYZE_REQ_PER_MIN:
        _ip_request_timestamps[client_ip] = history
        return False
    history.append(now)
    _ip_request_timestamps[client_ip] = history
    return True


@api_bp.route("/catalog", methods=["GET"])
def api_catalog():
    """Mengembalikan katalog kendaraan, daftar kota, opsi surat, dan tabel biaya perbaikan."""
    return jsonify(
        {
            "status": "ok",
            "catalog": VEHICLE_CATALOG,
            "cities": list(CITY_FACTORS.keys()),
            "surat_options": list(SURAT_FACTORS.keys()),
            "repair_table": load_repair_costs_table(),
        }
    )


@api_bp.route("/repair-rates", methods=["GET"])
def api_repair_rates():
    """Mengembalikan isi tabel biaya perbaikan (`data/repair_costs.json`)."""
    return jsonify({"status": "ok", "data": load_repair_costs_table()})


@api_bp.route("/analyze-photos", methods=["POST"])
def api_analyze_photos():
    """
    Endpoint unggah & analisis foto kondisi kendaraan:
    - Menerima `multipart/form-data` atau JSON berisi gambar hasil kompresi klien (data URL base64).
    - Memvalidasi ukuran & magic bytes MIME, menghapus seluruh metadata EXIF/GPS, menyimpan dengan nama acak.
    - Menjalankan DamageAnalyzer (Claude Vision API atau Fallback Manual/Heuristik).
    """
    client_ip = request.remote_addr or "127.0.0.1"
    if not _check_rate_limit(client_ip):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Terlalu banyak permintaan analisis foto dalam 1 menit terakhir. Silakan tunggu beberapa detik.",
                }
            ),
            429,
        )

    processed_photos = []
    vehicle_context = {
        "jenis": "mobil",
        "merek": "Honda",
        "model": "Brio RS",
        "tahun": 2022,
    }

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        vehicle_context["jenis"] = str(payload.get("jenis", "mobil")).lower()
        vehicle_context["merek"] = str(payload.get("merek", "Honda"))
        vehicle_context["model"] = str(payload.get("model", "Brio RS"))
        vehicle_context["tahun"] = payload.get("tahun", 2022)

        raw_photos = payload.get("photos", [])
        if not isinstance(raw_photos, list) or len(raw_photos) == 0:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Belum ada foto yang diunggah. Silakan pilih minimal 1 foto kondisi kendaraan atau lanjut ke Mode Manual.",
                    }
                ),
                400,
            )
        if len(raw_photos) > MAX_PHOTOS:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Maksimal {MAX_PHOTOS} foto yang dapat dianalisis sekaligus.",
                    }
                ),
                400,
            )

        for idx, item in enumerate(raw_photos, start=1):
            data_url = item.get("data_url", "") if isinstance(item, dict) else ""
            slot = item.get("slot", f"foto_{idx}") if isinstance(item, dict) else f"foto_{idx}"
            if "," in data_url:
                data_url = data_url.split(",", 1)[1]
            try:
                raw_bytes = base64.b64decode(data_url)
            except Exception:
                return jsonify({"status": "error", "message": f"Data gambar #{idx} tidak valid."}), 400

            ok, err_msg, meta = sanitize_and_save_photo(raw_bytes, slot_label=slot)
            if not ok:
                return jsonify({"status": "error", "message": f"Foto #{idx}: {err_msg}"}), 400
            processed_photos.append(meta)
    else:
        vehicle_context["jenis"] = str(request.form.get("jenis", "mobil")).lower()
        vehicle_context["merek"] = str(request.form.get("merek", "Honda"))
        vehicle_context["model"] = str(request.form.get("model", "Brio RS"))
        vehicle_context["tahun"] = request.form.get("tahun", 2022)

        files = request.files.getlist("photos")
        slots = request.form.getlist("slots")
        if not files:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Tidak ada file foto yang diterima server.",
                    }
                ),
                400,
            )
        if len(files) > MAX_PHOTOS:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"Maksimal {MAX_PHOTOS} foto per inspeksi.",
                    }
                ),
                400,
            )

        for idx, file_storage in enumerate(files, start=1):
            raw_bytes = file_storage.read()
            slot_label = slots[idx - 1] if idx - 1 < len(slots) else f"foto_{idx}"
            ok, err_msg, meta = sanitize_and_save_photo(raw_bytes, slot_label=slot_label)
            if not ok:
                return jsonify({"status": "error", "message": f"Foto #{idx}: {err_msg}"}), 400
            processed_photos.append(meta)

    analysis_result = analyze_vehicle_photos(processed_photos, vehicle_context)

    # Jangan kirim kembali string base64_jpeg ke klien untuk menghemat bandwidth
    saved_photo_infos = [
        {
            "foto_ke": i,
            "url": p["url"],
            "slot": p["slot"],
            "width": p["width"],
            "height": p["height"],
            "quality_issues": p["quality_issues"],
        }
        for i, p in enumerate(processed_photos, start=1)
    ]

    return jsonify(
        {
            "status": "ok",
            "photos": saved_photo_infos,
            "analysis": analysis_result,
            "repair_table": load_repair_costs_table(),
        }
    )


@api_bp.route("/predict", methods=["POST"])
def api_predict():
    """
    Endpoint utama prediksi harga kendaraan bekas dengan kerusakan:
    harga_akhir = harga_dasar_kondisi_normal - estimasi_biaya_perbaikan - diskon_pasar_akibat_kerusakan
    """
    payload = request.get_json(silent=True) or {}
    is_valid, err_msg, cleaned = validate_prediction_payload(payload)
    if not is_valid:
        return jsonify({"status": "error", "message": err_msg}), 400

    result = predict_vehicle_price(cleaned)

    saved_id = None
    if payload.get("save_to_history", False):
        saved_id = save_prediction(
            {
                **cleaned,
                "body_type": result["body_type"],
                "harga_dasar_normal": result["harga_dasar_normal"],
                "estimasi_biaya_perbaikan": result["estimasi_biaya_perbaikan"],
                "diskon_pasar_rp": result["diskon_pasar_rp"],
                "has_structural_damage": result["has_structural_damage"],
                "itemized_repairs": result["itemized_repairs"],
                "photos": cleaned.get("photos", []),
                "harga_estimasi": result["harga_estimasi"],
                "harga_min": result["harga_min"],
                "harga_max": result["harga_max"],
                "confidence": result["confidence"],
                "factors": result["factors"],
            }
        )

    return jsonify(
        {
            "status": "ok",
            "saved_id": saved_id,
            "data": result,
        }
    )


@api_bp.route("/compare", methods=["POST"])
def api_compare():
    """
    Endpoint pembanding 2 hingga 3 kendaraan secara berdampingan lengkap dengan:
    - Rincian kerusakan & total biaya perbaikan masing-masing unit
    - Harga akhir apa adanya vs total akuisisi setelah perbaikan
    - Kesimpulan 'Mana yang lebih worth it setelah perbaikan?'
    """
    payload = request.get_json(silent=True) or {}
    vehicles = payload.get("vehicles", [])
    if not isinstance(vehicles, list) or len(vehicles) < 2 or len(vehicles) > 3:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Silakan pilih minimal 2 dan maksimal 3 kendaraan untuk dibandingkan.",
                }
            ),
            400,
        )

    compared_items = []
    for idx, v_input in enumerate(vehicles, start=1):
        is_valid, err_msg, cleaned = validate_prediction_payload(v_input)
        if not is_valid:
            return jsonify({"status": "error", "message": f"Unit #{idx}: {err_msg}"}), 400

        pred = predict_vehicle_price(cleaned)
        age = max(1, CURRENT_YEAR - cleaned["tahun"])
        km_per_year = int(round(cleaned["kilometer"] / age))

        # Total biaya akuisisi siap pakai = Harga beli unit (harga_estimasi) + biaya perbaikan bengkel
        total_cost_ready_to_use = pred["harga_estimasi"] + pred["estimasi_biaya_perbaikan"]
        net_equity_gain = pred["harga_dasar_normal"] - total_cost_ready_to_use

        # Skor dimensi (0-100) untuk Radar / Bar Chart
        repair_burden_ratio = pred["estimasi_biaya_perbaikan"] / max(pred["harga_dasar_normal"], 1)
        body_integrity_score = int(
            max(25, min(98, round(100 - (repair_burden_ratio * 240) - (25 if pred["has_structural_damage"] else 0))))
        )
        freshness_score = int(max(30, min(98, 100 - (age * 8))))
        mileage_efficiency_score = int(max(25, min(98, round(100 - (km_per_year / 350)))))
        depreciation_resistance_score = int(max(40, min(98, round(100 - (pred["annual_depreciation_pct"] * 6.5)))))

        value_score = round(
            0.34 * body_integrity_score
            + 0.22 * mileage_efficiency_score
            + 0.22 * depreciation_resistance_score
            + 0.22 * freshness_score,
            1,
        )

        compared_items.append(
            {
                "slot": idx,
                "title": f"{cleaned['merek']} {cleaned['model']} ({cleaned['tahun']})",
                "input": cleaned,
                "body_type": pred["body_type"],
                "harga_dasar_normal": pred["harga_dasar_normal"],
                "estimasi_biaya_perbaikan": pred["estimasi_biaya_perbaikan"],
                "diskon_pasar_rp": pred["diskon_pasar_rp"],
                "has_structural_damage": pred["has_structural_damage"],
                "itemized_repairs": pred["itemized_repairs"],
                "harga_estimasi": pred["harga_estimasi"],
                "total_siap_pakai": total_cost_ready_to_use,
                "selisih_hemat_dari_normal": net_equity_gain,
                "harga_min": pred["harga_min"],
                "harga_max": pred["harga_max"],
                "base_otr_price": pred["base_otr_price"],
                "annual_depreciation_pct": pred["annual_depreciation_pct"],
                "annual_depreciation_rp": int(round(pred["harga_estimasi"] * (pred["annual_depreciation_pct"] / 100.0))),
                "km_per_year": km_per_year,
                "confidence": pred["confidence"],
                "specs": pred["specs"],
                "scores": {
                    "Integritas Bodi": body_integrity_score,
                    "Efisiensi KM": mileage_efficiency_score,
                    "Ketahanan Harga": depreciation_resistance_score,
                    "Usia Muda": freshness_score,
                    "Keyakinan Inspeksi": pred["confidence"],
                },
                "value_score": value_score,
            }
        )

    best_highlights = {
        "lowest_price_slot": min(compared_items, key=lambda x: x["harga_estimasi"])["slot"],
        "lowest_repair_slot": min(compared_items, key=lambda x: x["estimasi_biaya_perbaikan"])["slot"],
        "lowest_ready_slot": min(compared_items, key=lambda x: x["total_siap_pakai"])["slot"],
        "lowest_depr_slot": min(compared_items, key=lambda x: x["annual_depreciation_pct"])["slot"],
        "lowest_km_slot": min(compared_items, key=lambda x: x["input"]["kilometer"])["slot"],
        "best_value_slot": max(compared_items, key=lambda x: x["value_score"])["slot"],
    }

    winner = max(compared_items, key=lambda x: x["value_score"])
    cheapest_ready = min(compared_items, key=lambda x: x["total_siap_pakai"])

    verdict_summary = (
        f"Setelah memperhitungkan biaya perbaikan bengkel sebesar Rp {winner['estimasi_biaya_perbaikan']:,.0f}, "
        f"{winner['title']} adalah pilihan paling worth it (Indeks {winner['value_score']}/100) dengan total modal siap pakai "
        f"Rp {winner['total_siap_pakai']:,.0f} (hemat Rp {max(0, winner['selisih_hemat_dari_normal']):,.0f} dari harga pasar normal Rp {winner['harga_dasar_normal']:,.0f})."
    ).replace(",", ".")

    if cheapest_ready["slot"] != winner["slot"]:
        selisih = winner["total_siap_pakai"] - cheapest_ready["total_siap_pakai"]
        verdict_summary += (
            f" Jika total dana siap pakai (beli + bengkel) menjadi batas utama, {cheapest_ready['title']} "
            f"lebih ringan Rp {selisih:,.0f}."
        ).replace(",", ".")

    return jsonify(
        {
            "status": "ok",
            "items": compared_items,
            "highlights": best_highlights,
            "verdict": {
                "winner_slot": winner["slot"],
                "winner_title": winner["title"],
                "winner_score": winner["value_score"],
                "summary": verdict_summary,
            },
        }
    )


@api_bp.route("/credit", methods=["POST"])
def api_credit():
    """Endpoint kalkulasi simulasi kredit (Anuitas & Flat beserta jadwal amortisasi)."""
    payload = request.get_json(silent=True) or {}
    is_valid, err_msg, cleaned = validate_credit_payload(payload)
    if not is_valid:
        return jsonify({"status": "error", "message": err_msg}), 400

    simulation = calculate_credit_simulation(cleaned)
    return jsonify({"status": "ok", "data": simulation})


@api_bp.route("/history", methods=["GET", "POST", "DELETE"])
def api_history():
    """Endpoint CRUD untuk menyimpan, mengambil, atau menghapus riwayat prediksi beserta foto."""
    if request.method == "GET":
        jenis = request.args.get("jenis", "").strip().lower()
        records = get_history(limit=50, jenis_filter=jenis if jenis in ("motor", "mobil") else None)
        return jsonify({"status": "ok", "records": records})

    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        is_valid, err_msg, cleaned = validate_prediction_payload(payload)
        if not is_valid:
            return jsonify({"status": "error", "message": err_msg}), 400
        pred = predict_vehicle_price(cleaned)
        row_id = save_prediction(
            {
                **cleaned,
                "body_type": pred["body_type"],
                "harga_dasar_normal": pred["harga_dasar_normal"],
                "estimasi_biaya_perbaikan": pred["estimasi_biaya_perbaikan"],
                "diskon_pasar_rp": pred["diskon_pasar_rp"],
                "has_structural_damage": pred["has_structural_damage"],
                "itemized_repairs": pred["itemized_repairs"],
                "photos": cleaned.get("photos", []),
                "harga_estimasi": pred["harga_estimasi"],
                "harga_min": pred["harga_min"],
                "harga_max": pred["harga_max"],
                "confidence": pred["confidence"],
                "factors": pred["factors"],
            }
        )
        return jsonify({"status": "ok", "saved_id": row_id, "message": "Laporan inspeksi & valuasi berhasil disimpan ke riwayat."})

    if request.method == "DELETE":
        item_id = request.args.get("id")
        if item_id:
            deleted = delete_history_item(int(item_id))
            return jsonify({"status": "ok", "deleted": deleted})
        count = clear_all_history()
        return jsonify({"status": "ok", "cleared_count": count})
