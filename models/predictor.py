"""
Layanan Prediksi Harga Kendaraan Bekas Berbasis Inspeksi Foto Kerusakan & Machine Learning.

Rumus Utama Valuasi:
    harga_akhir = harga_dasar_kondisi_normal - estimasi_biaya_perbaikan - diskon_pasar_akibat_kerusakan

Menyediakan:
- Prediksi `harga_dasar_kondisi_normal` dari ensemble Gradient Boosting + Random Forest (scikit-learn).
- Kalkulasi `estimasi_biaya_perbaikan` per titik kerusakan dari `data/repair_costs.json`.
- Kalkulasi `diskon_pasar_akibat_kerusakan` (penalti likuiditas pasar, terutama untuk indikasi struktural).
- Analisis perbandingan "Harga Jual Apa Adanya (As-Is)" vs "Harga Jika Diperbaiki Dulu".
- Data grafik Waterfall untuk visualisasi pemotongan harga secara transparan.
"""

import json
import os
from typing import Any, Dict, List, Tuple
import joblib
import numpy as np
import pandas as pd

from generate_dataset import CITY_FACTORS, CONDITION_FACTORS, CURRENT_YEAR, SURAT_FACTORS, VEHICLE_CATALOG
from models.damage_analyzer import load_repair_costs_table
from train_model import METADATA_PATH, MODEL_PATH, train_and_save_model

_MODEL_BUNDLE = None
_METADATA = None


def ensure_model_loaded() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Memastikan model ML dan metadata sudah dimuat ke memori (otomatis latih ulang jika versi berbeda)."""
    global _MODEL_BUNDLE, _METADATA
    if _MODEL_BUNDLE is None or _METADATA is None:
        if not os.path.exists(MODEL_PATH) or not os.path.exists(METADATA_PATH):
            train_and_save_model()
        try:
            _MODEL_BUNDLE = joblib.load(MODEL_PATH)
        except Exception:
            train_and_save_model()
            _MODEL_BUNDLE = joblib.load(MODEL_PATH)
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            _METADATA = json.load(f)
    return _MODEL_BUNDLE, _METADATA


def get_catalog_item(merek: str, model_name: str) -> Dict[str, Any]:
    """Mencari entri katalog kendaraan berdasarkan merek dan nama model."""
    for item in VEHICLE_CATALOG:
        if item["merek"].lower() == merek.lower() and item["model"].lower() == model_name.lower():
            return item
    return VEHICLE_CATALOG[0]


def validate_prediction_payload(payload: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """Memvalidasi payload input prediksi (data unit + daftar kerusakan hasil koreksi)."""
    required_fields = [
        "jenis",
        "merek",
        "model",
        "tahun",
        "kilometer",
        "kota",
    ]
    for field in required_fields:
        if field not in payload or payload[field] in (None, ""):
            return False, f"Kolom '{field}' wajib diisi sebelum melakukan estimasi harga.", {}

    jenis = str(payload["jenis"]).strip().lower()
    if jenis not in ("motor", "mobil"):
        return False, "Jenis kendaraan harus berupa 'motor' atau 'mobil'.", {}

    try:
        tahun = int(payload["tahun"])
    except ValueError:
        return False, "Tahun produksi harus berupa angka tahun yang valid (contoh: 2022).", {}

    if tahun < 2010 or tahun > CURRENT_YEAR:
        return False, f"Tahun kendaraan harus berada di rentang 2010 hingga {CURRENT_YEAR}.", {}

    try:
        kilometer = int(float(payload["kilometer"]))
    except ValueError:
        return False, "Jarak tempuh (kilometer) harus berupa angka positif.", {}

    if kilometer < 0 or kilometer > 600_000:
        return False, "Jarak tempuh harus antara 0 km hingga 600.000 km.", {}

    kota = str(payload["kota"]).strip()
    if kota not in CITY_FACTORS:
        return False, f"Kota '{kota}' belum terdaftar dalam cakupan indeks pasar kami.", {}

    surat = str(payload.get("surat", "Lengkap (STNK + BPKB + Faktur)")).strip()
    if surat not in SURAT_FACTORS:
        return False, f"Pilihan kelengkapan surat '{surat}' tidak dikenali.", {}

    catalog_item = get_catalog_item(str(payload["merek"]).strip(), str(payload["model"]).strip())
    transmisi = str(payload.get("transmisi") or catalog_item["transmisi_opts"][0]).strip()
    bahan_bakar = str(payload.get("bahan_bakar") or catalog_item["bbm_opts"][0]).strip()

    try:
        kondisi = int(payload.get("kondisi", 4))
    except (TypeError, ValueError):
        kondisi = 4
    kondisi = max(1, min(5, kondisi))

    raw_detail = payload.get("kondisi_detail", "")
    if isinstance(raw_detail, list):
        kondisi_detail = ", ".join(str(x).strip() for x in raw_detail if str(x).strip())
    else:
        kondisi_detail = str(raw_detail).strip()

    kerusakan = payload.get("kerusakan", [])
    if not isinstance(kerusakan, list):
        kerusakan = []

    indikasi_struktural = payload.get("indikasi_struktural", {"ada": False, "alasan": ""})
    if not isinstance(indikasi_struktural, dict):
        indikasi_struktural = {"ada": False, "alasan": ""}

    kualitas_foto = payload.get("kualitas_foto", {"cukup": True, "masalah": []})
    if not isinstance(kualitas_foto, dict):
        kualitas_foto = {"cukup": True, "masalah": []}

    photos = payload.get("photos", [])
    if not isinstance(photos, list):
        photos = []

    cleaned = {
        "jenis": jenis,
        "merek": str(payload["merek"]).strip(),
        "model": str(payload["model"]).strip(),
        "tahun": tahun,
        "kilometer": kilometer,
        "transmisi": transmisi,
        "bahan_bakar": bahan_bakar,
        "kondisi": kondisi,
        "kondisi_detail": kondisi_detail,
        "surat": surat,
        "kota": kota,
        "warna": str(payload.get("warna", "#D9381E")).strip(),
        "kerusakan": kerusakan,
        "indikasi_struktural": indikasi_struktural,
        "kualitas_foto": kualitas_foto,
        "photos": photos,
    }
    return True, "", cleaned


def calculate_damage_deductions(
    kerusakan_list: List[Dict[str, Any]],
    indikasi_struktural: Dict[str, Any],
    jenis_kendaraan: str,
    base_otr_price: int,
    harga_dasar_normal: int,
) -> Dict[str, Any]:
    """
    Menghitung rincian biaya perbaikan per bagian dan diskon pasar akibat kerusakan:
        harga_akhir = harga_dasar_kondisi_normal - estimasi_biaya_perbaikan - diskon_pasar_akibat_kerusakan
    """
    repair_table = load_repair_costs_table()
    parts_cfg = repair_table["parts"]
    types_cfg = repair_table["damage_types"]
    sev_cfg = repair_table["severity_multipliers"]
    disc_rules = repair_table["market_discount_rules"]

    # Indeks kelas kendaraan: biaya pengecatan/part mobil premium (>Rp 600 jt) lebih tinggi dari LCGC
    if jenis_kendaraan == "motor":
        segment_multiplier = max(0.85, min(1.85, base_otr_price / 30_000_000.0))
        cost_round_unit = 25_000
        price_round_unit = 100_000
    else:
        segment_multiplier = max(0.85, min(2.25, base_otr_price / 280_000_000.0))
        cost_round_unit = 50_000
        price_round_unit = 500_000

    itemized_repairs: List[Dict[str, Any]] = []
    total_repair_cost = 0
    accumulated_market_penalty_pct = 0.0
    has_structural_damage = bool(indikasi_struktural.get("ada", False))

    for idx, dmg in enumerate(kerusakan_list, start=1):
        if not isinstance(dmg, dict):
            continue
        bagian_key = str(dmg.get("bagian", "bumper_depan" if jenis_kendaraan == "mobil" else "cover_body")).lower()
        if bagian_key not in parts_cfg:
            bagian_key = "bumper_depan" if jenis_kendaraan == "mobil" else "cover_body"

        jenis_key = str(dmg.get("jenis", "lecet_ringan")).lower()
        if jenis_key not in types_cfg:
            jenis_key = "lecet_ringan"

        try:
            keparahan = max(1, min(4, int(dmg.get("keparahan", 1))))
        except (TypeError, ValueError):
            keparahan = 1

        try:
            luas_persen = max(1, min(100, int(dmg.get("perkiraan_luas_persen", 20))))
        except (TypeError, ValueError):
            luas_persen = 20

        try:
            keyakinan = round(max(0.1, min(1.0, float(dmg.get("keyakinan", 0.85)))), 2)
        except (TypeError, ValueError):
            keyakinan = 0.85

        part_info = parts_cfg[bagian_key]
        type_info = types_cfg[jenis_key]
        sev_info = sev_cfg[str(keparahan)]

        if part_info.get("is_structural") or keparahan >= 4:
            has_structural_damage = True

        base_part_cost = (
            part_info["base_cost_motor"] if jenis_kendaraan == "motor" else part_info["base_cost_mobil"]
        )
        area_factor = 0.78 + 0.44 * (luas_persen / 100.0)

        raw_item_cost = (
            base_part_cost
            * type_info["cost_factor"]
            * sev_info["multiplier"]
            * area_factor
            * segment_multiplier
        )
        item_cost = int(round(raw_item_cost / cost_round_unit) * cost_round_unit)
        total_repair_cost += item_cost

        # Penalti pasar per kerusakan (kerusakan ke-4 dst yang bersifat ringan mengalami diminishing return)
        weight = 1.0 if (idx <= 3 or keparahan >= 3) else 0.55
        accumulated_market_penalty_pct += float(sev_info["market_penalty_pct"]) * weight

        itemized_repairs.append(
            {
                "no": idx,
                "bagian": bagian_key,
                "bagian_label": part_info["label"],
                "jenis": jenis_key,
                "jenis_label": type_info["label"],
                "tindakan": type_info["action_label"],
                "keparahan": keparahan,
                "keparahan_label": sev_info["label"],
                "perkiraan_luas_persen": luas_persen,
                "estimasi_biaya": item_cost,
                "bbox": dmg.get("bbox", [0.25, 0.35, 0.25, 0.22]),
                "foto_ke": int(dmg.get("foto_ke", 1)),
                "keyakinan": keyakinan,
                "catatan": dmg.get("catatan", f"{type_info['label']} pada {part_info['label']}"),
            }
        )

    if has_structural_damage:
        accumulated_market_penalty_pct += float(disc_rules["structural_flag_extra_pct"])

    max_disc_pct = float(disc_rules["max_total_market_discount_pct"])
    final_market_discount_pct = round(min(max_disc_pct, accumulated_market_penalty_pct), 2)
    diskon_pasar_rp = int(
        round((harga_dasar_normal * (final_market_discount_pct / 100.0)) / price_round_unit) * price_round_unit
    )

    # Batas lantai harga minimal 25% dari harga dasar normal agar tidak pernah negatif
    min_floor_price = int(round((harga_dasar_normal * 0.25) / price_round_unit) * price_round_unit)
    harga_akhir = max(min_floor_price, harga_dasar_normal - total_repair_cost - diskon_pasar_rp)

    # Analisis Keputusan: "Harga Jika Diperbaiki Terlebih Dahulu" vs "Harga Jual Apa Adanya"
    # Jika diperbaiki secara rapi sebelum dijual:
    # - Unit tanpa cacat struktural kembali mendekati harga_dasar_normal (hanya penyesuaian kecil 1% bekas cat ulang).
    # - Unit dengan cacat struktural masih menyisakan diskon riwayat tabrakan (sekitar 8%).
    residual_penalty_after_repair_pct = 8.0 if has_structural_damage else (1.0 if itemized_repairs else 0.0)
    harga_jual_setelah_diperbaiki = int(
        round((harga_dasar_normal * (1.0 - residual_penalty_after_repair_pct / 100.0)) / price_round_unit)
        * price_round_unit
    )
    nilai_bersih_setelah_biaya_bengkel = harga_jual_setelah_diperbaiki - total_repair_cost
    selisih_untung_perbaikan = nilai_bersih_setelah_biaya_bengkel - harga_akhir

    if not itemized_repairs and not has_structural_damage:
        rekomendasi_perbaikan = "Kondisi bodi prima tanpa pengurangan biaya perbaikan. Unit siap dipasarkan langsung pada harga normal."
    elif has_structural_damage:
        rekomendasi_perbaikan = (
            "Terdeteksi indikasi kerusakan struktural/berat. Disarankan menjual apa adanya dengan transparansi penuh "
            "atau melakukan perbaikan di bengkel sasis bersertifikat sebelum transaksi."
        )
    elif selisih_untung_perbaikan > 0:
        rekomendasi_perbaikan = (
            f"Lebih untung diperbaiki dulu sebelum dijual: dengan modal bengkel Rp {total_repair_cost:,.0f}, "
            f"Anda menghindari diskon pasar pembeli dan berpotensi meraih nilai bersih lebih tinggi sekitar Rp {selisih_untung_perbaikan:,.0f}."
        ).replace(",", ".")
    else:
        rekomendasi_perbaikan = (
            "Lebih praktis dijual apa adanya (As-Is): biaya perbaikan bengkel hampir setara dengan kenaikan harga jualnya."
        )

    return {
        "itemized_repairs": itemized_repairs,
        "total_biaya_perbaikan": total_repair_cost,
        "diskon_pasar_pct": final_market_discount_pct,
        "diskon_pasar_rp": diskon_pasar_rp,
        "has_structural_damage": has_structural_damage,
        "harga_akhir": harga_akhir,
        "perbandingan_keputusan": {
            "harga_jual_apa_adanya": harga_akhir,
            "estimasi_biaya_perbaikan": total_repair_cost,
            "harga_jika_diperbaiki": harga_jual_setelah_diperbaiki,
            "nilai_bersih_jika_diperbaiki": nilai_bersih_setelah_biaya_bengkel,
            "selisih_keuntungan_perbaikan": selisih_untung_perbaikan,
            "rekomendasi": rekomendasi_perbaikan,
        },
    }


def predict_vehicle_price(cleaned_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Menjalankan prediksi harga lengkap:
    1. Menghitung `harga_dasar_kondisi_normal` dari model ML (asumsi kondisi standar normal = 4).
    2. Mengurangi `estimasi_biaya_perbaikan` dan `diskon_pasar_akibat_kerusakan` berdasarkan temuan foto.
    3. Menyusun data grafik Waterfall, rentang harga (min-estimasi-maks), tingkat keyakinan, & penjelasan faktor.
    """
    bundle, _ = ensure_model_loaded()
    primary_model = bundle["primary_model"]
    rf_model = bundle["rf_model"]
    feature_cols = bundle["feature_cols"]

    cleaned_input = dict(cleaned_input)
    cleaned_input.setdefault("surat", "Lengkap (STNK + BPKB + Faktur)")
    cleaned_input.setdefault("kerusakan", [])
    cleaned_input.setdefault("indikasi_struktural", {"ada": False, "alasan": ""})
    cleaned_input.setdefault("kualitas_foto", {"cukup": True, "masalah": []})

    # Prediksi Harga Dasar Normal selalu menggunakan asumsi kondisi standar normal (4/5)
    # agar tidak terjadi pemotongan ganda dengan pengurangan biaya kerusakan spesifik dari foto
    baseline_row = {col: cleaned_input.get(col) for col in feature_cols}
    baseline_row["kondisi"] = 4
    baseline_row["surat"] = "Lengkap (STNK + BPKB + Faktur)"
    df_base = pd.DataFrame([baseline_row])

    pred_gbr_base = float(primary_model.predict(df_base)[0])
    pred_rf_base = float(rf_model.predict(df_base)[0])
    surat_factor = SURAT_FACTORS.get(cleaned_input["surat"], 1.0)

    raw_normal_price = (0.70 * pred_gbr_base + 0.30 * pred_rf_base) * surat_factor

    # Penyesuaian faktor tambahan opsional (servis resmi, ban tebal, pajak STNK)
    detail_lower = str(cleaned_input.get("kondisi_detail", "")).lower()
    pajak_mati = "pajak mati" in detail_lower or "pajak terlambat" in detail_lower or "pajak stnk mati" in detail_lower
    servis_resmi = "servis rutin" in detail_lower or "servis resmi" in detail_lower
    ban_tebal = "ban tebal" in detail_lower

    optional_adj_factor = 1.0
    if pajak_mati:
        optional_adj_factor -= 0.035
    if servis_resmi:
        optional_adj_factor += 0.012
    if ban_tebal:
        optional_adj_factor += 0.008

    raw_normal_price *= optional_adj_factor
    rounding_unit = 100_000 if cleaned_input["jenis"] == "motor" else 500_000
    harga_dasar_normal = int(round(raw_normal_price / rounding_unit) * rounding_unit)

    catalog_item = get_catalog_item(cleaned_input["merek"], cleaned_input["model"])
    base_otr = catalog_item["base_price"]

    # Hitung potongan biaya perbaikan & diskon pasar dari temuan kerusakan
    damage_calc = calculate_damage_deductions(
        kerusakan_list=cleaned_input["kerusakan"],
        indikasi_struktural=cleaned_input["indikasi_struktural"],
        jenis_kendaraan=cleaned_input["jenis"],
        base_otr_price=base_otr,
        harga_dasar_normal=harga_dasar_normal,
    )

    harga_estimasi = damage_calc["harga_akhir"]

    # Hitung standar deviasi antar pohon di Random Forest untuk lebar rentang harga
    X_transformed = rf_model.named_steps["preprocessor"].transform(df_base)
    tree_preds = np.array([tree.predict(X_transformed)[0] for tree in rf_model.named_steps["regressor"].estimators_])
    tree_std = float(np.std(tree_preds))
    rel_spread = tree_std / max(raw_normal_price, 1.0)

    # Jika ada kerusakan struktural atau foto kurang jelas, rentang ketidakpastian melebar sedikit
    photo_ok = bool(cleaned_input["kualitas_foto"].get("cukup", True))
    extra_spread = 0.018 if not photo_ok else 0.0
    if damage_calc["has_structural_damage"]:
        extra_spread += 0.025

    margin_pct = max(0.04, min(0.095, rel_spread * 1.15 + extra_spread))
    harga_min = int(round((harga_estimasi * (1.0 - margin_pct)) / rounding_unit) * rounding_unit)
    harga_max = int(round((harga_estimasi * (1.0 + margin_pct)) / rounding_unit) * rounding_unit)

    # Tingkat keyakinan keseluruhan (turun bila foto kurang bagus atau keyakinan deteksi AI rendah)
    age = max(1, CURRENT_YEAR - cleaned_input["tahun"])
    expected_km = age * catalog_item["avg_km_per_year"]
    km_deviation = abs(cleaned_input["kilometer"] - expected_km) / max(expected_km, 10000)
    base_conf = 95.0 - (rel_spread * 40.0) - (km_deviation * 3.0)
    if not photo_ok:
        base_conf -= 7.0
    if damage_calc["itemized_repairs"]:
        avg_ai_conf = float(np.mean([d["keyakinan"] for d in damage_calc["itemized_repairs"]]))
        if avg_ai_conf < 0.78:
            base_conf -= (0.80 - avg_ai_conf) * 25.0
    if damage_calc["has_structural_damage"]:
        base_conf -= 4.0
    confidence = int(max(68, min(97, round(base_conf))))

    # Susun data Grafik Waterfall
    waterfall_steps = [
        {
            "label": "Harga Dasar Normal",
            "amount": harga_dasar_normal,
            "type": "base",
        }
    ]
    for rep in damage_calc["itemized_repairs"]:
        waterfall_steps.append(
            {
                "label": f"- {rep['bagian_label']} ({rep['jenis_label']})",
                "amount": -rep["estimasi_biaya"],
                "type": "deduction",
            }
        )
    if damage_calc["diskon_pasar_rp"] > 0:
        waterfall_steps.append(
            {
                "label": f"- Diskon Pasar ({damage_calc['diskon_pasar_pct']}%)",
                "amount": -damage_calc["diskon_pasar_rp"],
                "type": "discount",
            }
        )
    waterfall_steps.append(
        {
            "label": "Harga Akhir Estimasi",
            "amount": harga_estimasi,
            "type": "final",
        }
    )

    # Susun penjelasan faktor penentu harga
    factors: List[Dict[str, Any]] = []
    age_drop_pct = round(((1.0 - catalog_item["annual_depr"]) ** age - 1.0) * 100, 1)
    factors.append(
        {
            "factor": "Usia & Depresiasi Normal",
            "label": f"Usia {age} tahun (keluaran {cleaned_input['tahun']})",
            "impact_pct": age_drop_pct,
            "direction": "down",
            "explanation": f"Harga dasar kondisi normal adalah Rp {harga_dasar_normal:,.0f} (menyusut dari OTR baru Rp {base_otr:,.0f}).".replace(",", "."),
        }
    )

    if damage_calc["total_biaya_perbaikan"] > 0:
        rep_pct = round((-damage_calc["total_biaya_perbaikan"] / max(harga_dasar_normal, 1)) * 100, 1)
        factors.append(
            {
                "factor": "Estimasi Biaya Perbaikan Bengkel",
                "label": f"{len(damage_calc['itemized_repairs'])} titik temuan kerusakan",
                "impact_pct": rep_pct,
                "direction": "down",
                "explanation": f"Total biaya perbaikan bodi/komponen mengurangi harga sebesar Rp {damage_calc['total_biaya_perbaikan']:,.0f} ({abs(rep_pct):.1f}%).".replace(",", "."),
            }
        )

    if damage_calc["diskon_pasar_rp"] > 0:
        factors.append(
            {
                "factor": "Diskon Pasar Akibat Kerusakan",
                "label": f"Penalti likuiditas -{damage_calc['diskon_pasar_pct']}%",
                "impact_pct": -damage_calc["diskon_pasar_pct"],
                "direction": "down",
                "explanation": (
                    f"Pembeli memperhitungkan diskon risiko sebesar Rp {damage_calc['diskon_pasar_rp']:,.0f} "
                    f"{'(termasuk penalti indikasi struktural)' if damage_calc['has_structural_damage'] else 'karena riwayat perbaikan panel'}."
                ).replace(",", "."),
            }
        )

    surat_impact_pct = round((surat_factor - 1.0) * 100, 1)
    factors.append(
        {
            "factor": "Kelengkapan Surat & Catatan Unit",
            "label": cleaned_input["surat"],
            "impact_pct": surat_impact_pct,
            "direction": "neutral" if surat_impact_pct == 0 else "down",
            "explanation": (
                f"Status dokumen: {cleaned_input['surat']}."
                + (f" Detail tambahan: {cleaned_input['kondisi_detail']}." if cleaned_input.get("kondisi_detail") else "")
            ),
        }
    )

    annual_depr = catalog_item["annual_depr"]
    depreciation_curve = []
    for offset in range(0, 5):
        proj_year = CURRENT_YEAR + offset
        proj_price = int(round((harga_estimasi * ((1.0 - annual_depr) ** offset)) / rounding_unit) * rounding_unit)
        depreciation_curve.append({"year": proj_year, "price": proj_price})

    return {
        "input": cleaned_input,
        "body_type": catalog_item["body_type"],
        "base_otr_price": base_otr,
        "annual_depreciation_pct": round(annual_depr * 100, 1),
        "specs": catalog_item.get("specs", {}),
        "harga_dasar_normal": harga_dasar_normal,
        "estimasi_biaya_perbaikan": damage_calc["total_biaya_perbaikan"],
        "diskon_pasar_pct": damage_calc["diskon_pasar_pct"],
        "diskon_pasar_rp": damage_calc["diskon_pasar_rp"],
        "has_structural_damage": damage_calc["has_structural_damage"],
        "itemized_repairs": damage_calc["itemized_repairs"],
        "perbandingan_keputusan": damage_calc["perbandingan_keputusan"],
        "waterfall_steps": waterfall_steps,
        "harga_estimasi": harga_estimasi,
        "harga_min": harga_min,
        "harga_max": harga_max,
        "confidence": confidence,
        "factors": factors,
        "depreciation_curve": depreciation_curve,
    }
