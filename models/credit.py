"""
Modul Kalkulator Simulasi Kredit Kendaraan (Metode Anuitas & Bunga Flat).
Menghasilkan rincian cicilan bulanan, total bunga, total pembayaran, dan jadwal amortisasi.
"""

from typing import Any, Dict, List, Tuple


def validate_credit_payload(payload: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """Memvalidasi input simulasi kredit kendaraan."""
    try:
        harga = float(payload.get("harga", 0))
        dp_rupiah = float(payload.get("dp_rupiah", 0))
        tenor = int(payload.get("tenor", 36))
        bunga_tahunan = float(payload.get("bunga_tahunan", 8.5))
    except (TypeError, ValueError):
        return False, "Parameter harga, DP, tenor, dan suku bunga harus berupa angka yang valid.", {}

    if harga < 5_000_000 or harga > 5_000_000_000:
        return False, "Harga kendaraan harus berada di antara Rp 5.000.000 hingga Rp 5.000.000.000.", {}

    if dp_rupiah < 0 or dp_rupiah >= harga * 0.95:
        return False, "Uang muka (DP) harus antara 0% hingga maksimal 90% dari harga kendaraan.", {}

    if tenor not in (12, 24, 36, 48, 60):
        return False, "Pilihan tenor harus 12, 24, 36, 48, atau 60 bulan.", {}

    if bunga_tahunan < 0.5 or bunga_tahunan > 35.0:
        return False, "Suku bunga tahunan harus berada di antara 0,5% hingga 35%.", {}

    return (
        True,
        "",
        {
            "harga": int(round(harga)),
            "dp_rupiah": int(round(dp_rupiah)),
            "dp_persen": round((dp_rupiah / harga) * 100, 2),
            "tenor": tenor,
            "bunga_tahunan": bunga_tahunan,
        },
    )


def calculate_credit_simulation(cleaned: Dict[str, Any]) -> Dict[str, Any]:
    """
    Menghitung simulasi kredit dengan dua metode:
    1. Metode Anuitas (cicilan tetap, porsi bunga menurun & pokok membesar tiap bulan)
    2. Metode Bunga Flat (porsi pokok & bunga tetap setiap bulan)
    """
    harga = cleaned["harga"]
    dp = cleaned["dp_rupiah"]
    pokok_pinjaman = max(0, harga - dp)
    tenor = cleaned["tenor"]
    rate_annual = cleaned["bunga_tahunan"] / 100.0
    rate_monthly = rate_annual / 12.0

    # --- 1. Perhitungan Metode Anuitas ---
    if rate_monthly > 0 and pokok_pinjaman > 0:
        faktor_anuitas = (rate_monthly * ((1 + rate_monthly) ** tenor)) / (((1 + rate_monthly) ** tenor) - 1)
        cicilan_anuitas = pokok_pinjaman * faktor_anuitas
    else:
        cicilan_anuitas = pokok_pinjaman / max(tenor, 1)

    jadwal_anuitas: List[Dict[str, Any]] = []
    sisa_pokok_anuitas = float(pokok_pinjaman)
    total_bunga_anuitas = 0.0

    for bulan in range(1, tenor + 1):
        bunga_bulan_ini = sisa_pokok_anuitas * rate_monthly
        pokok_bulan_ini = cicilan_anuitas - bunga_bulan_ini
        if bulan == tenor:
            pokok_bulan_ini = sisa_pokok_anuitas
            cicilan_aktual = pokok_bulan_ini + bunga_bulan_ini
        else:
            cicilan_aktual = cicilan_anuitas

        sisa_pokok_anuitas = max(0.0, sisa_pokok_anuitas - pokok_bulan_ini)
        total_bunga_anuitas += bunga_bulan_ini

        jadwal_anuitas.append(
            {
                "bulan": bulan,
                "cicilan": int(round(cicilan_aktual)),
                "pokok": int(round(pokok_bulan_ini)),
                "bunga": int(round(bunga_bulan_ini)),
                "sisa_pinjaman": int(round(sisa_pokok_anuitas)),
            }
        )

    total_bayar_anuitas = dp + pokok_pinjaman + int(round(total_bunga_anuitas))

    # --- 2. Perhitungan Metode Bunga Flat ---
    pokok_per_bulan_flat = pokok_pinjaman / max(tenor, 1)
    bunga_per_bulan_flat = pokok_pinjaman * rate_monthly
    cicilan_flat = pokok_per_bulan_flat + bunga_per_bulan_flat
    total_bunga_flat = bunga_per_bulan_flat * tenor

    jadwal_flat: List[Dict[str, Any]] = []
    sisa_pokok_flat = float(pokok_pinjaman)
    for bulan in range(1, tenor + 1):
        sisa_pokok_flat = max(0.0, sisa_pokok_flat - pokok_per_bulan_flat)
        jadwal_flat.append(
            {
                "bulan": bulan,
                "cicilan": int(round(cicilan_flat)),
                "pokok": int(round(pokok_per_bulan_flat)),
                "bunga": int(round(bunga_per_bulan_flat)),
                "sisa_pinjaman": int(round(sisa_pokok_flat)),
            }
        )

    total_bayar_flat = dp + pokok_pinjaman + int(round(total_bunga_flat))

    return {
        "input": cleaned,
        "pokok_pinjaman": int(round(pokok_pinjaman)),
        "anuitas": {
            " metode": "Anuitas",
            "cicilan_per_bulan": int(round(cicilan_anuitas)),
            "total_bunga": int(round(total_bunga_anuitas)),
            "total_pembayaran": int(round(total_bayar_anuitas)),
            "total_pinjaman_plus_bunga": int(round(pokok_pinjaman + total_bunga_anuitas)),
            "jadwal": jadwal_anuitas,
        },
        "flat": {
            "metode": "Flat",
            "cicilan_per_bulan": int(round(cicilan_flat)),
            "total_bunga": int(round(total_bunga_flat)),
            "total_pembayaran": int(round(total_bayar_flat)),
            "total_pinjaman_plus_bunga": int(round(pokok_pinjaman + total_bunga_flat)),
            "jadwal": jadwal_flat,
        },
        "selisih_total_bunga": int(round(total_bunga_flat - total_bunga_anuitas)),
    }
