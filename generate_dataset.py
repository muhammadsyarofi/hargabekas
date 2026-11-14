"""
Generator Dataset Dummy Realistis untuk Sistem Prediksi HargaBekas.
Mencakup 15 Merek Pabrikan (12 Merek Mobil & 5 Merek Motor) dan 44 Model Kendaraan Populer di Indonesia.
CATATAN PENTING:
Dataset ini adalah data sintetis terkalibrasi berdasarkan harga pasar kendaraan bekas
di Indonesia (2015-2025). Anda dapat mengganti file `data/vehicles_dataset.csv`
dengan data scraping/observasi asli dari dealer atau marketplace otomotif selama
mempertahankan struktur kolom yang sama, lalu jalankan ulang `python train_model.py`.
"""

import os
import random
import numpy as np
import pandas as pd

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# Katalog Lengkap Kendaraan Pasar Indonesia (Mobil & Motor)
VEHICLE_CATALOG = [
    # ==================== MOBIL: TOYOTA ====================
    {
        "jenis": "mobil",
        "merek": "Toyota",
        "model": "Avanza Veloz",
        "body_type": "mpv",
        "base_price": 312_000_000,
        "annual_depr": 0.072,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 14500,
        "specs": {"Mesin": "1.5L Dual VVT-i", "Tenaga": "105 HP", "Konsumsi BBM": "15.8 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Toyota",
        "model": "Innova Zenix",
        "body_type": "mpv",
        "base_price": 478_000_000,
        "annual_depr": 0.066,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Hybrid", "Bensin"],
        "avg_km_per_year": 14000,
        "specs": {"Mesin": "2.0L Dynamic Force / Hybrid", "Tenaga": "183 HP", "Konsumsi BBM": "21.0 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Toyota",
        "model": "Fortuner VRZ",
        "body_type": "suv",
        "base_price": 635_000_000,
        "annual_depr": 0.075,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Diesel", "Bensin"],
        "avg_km_per_year": 15500,
        "specs": {"Mesin": "2.8L VNT Intercooler", "Tenaga": "201 HP", "Konsumsi BBM": "12.8 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Toyota",
        "model": "Rush GR Sport",
        "body_type": "suv",
        "base_price": 308_000_000,
        "annual_depr": 0.076,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 14000,
        "specs": {"Mesin": "1.5L 2NR-VE", "Tenaga": "103 HP", "Konsumsi BBM": "14.8 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Toyota",
        "model": "Agya GR Sport",
        "body_type": "hatchback",
        "base_price": 242_000_000,
        "annual_depr": 0.078,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 12000,
        "specs": {"Mesin": "1.2L Dual VVT-i", "Tenaga": "87 HP", "Konsumsi BBM": "19.2 km/L", "Kapasitas": "5 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Toyota",
        "model": "Camry Hybrid",
        "body_type": "sedan",
        "base_price": 935_000_000,
        "annual_depr": 0.095,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Hybrid", "Bensin"],
        "avg_km_per_year": 11000,
        "specs": {"Mesin": "2.5L A25A-FXS Hybrid", "Tenaga": "204 HP", "Konsumsi BBM": "22.5 km/L", "Kapasitas": "5 Kursi"},
    },

    # ==================== MOBIL: HONDA ====================
    {
        "jenis": "mobil",
        "merek": "Honda",
        "model": "Brio RS",
        "body_type": "hatchback",
        "base_price": 244_000_000,
        "annual_depr": 0.068,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 12500,
        "specs": {"Mesin": "1.2L i-VTEC", "Tenaga": "89 HP", "Konsumsi BBM": "18.5 km/L", "Kapasitas": "5 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Honda",
        "model": "HR-V SE",
        "body_type": "suv",
        "base_price": 424_000_000,
        "annual_depr": 0.076,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 12500,
        "specs": {"Mesin": "1.5L DOHC i-VTEC", "Tenaga": "119 HP", "Konsumsi BBM": "15.2 km/L", "Kapasitas": "5 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Honda",
        "model": "CR-V Turbo",
        "body_type": "suv",
        "base_price": 749_000_000,
        "annual_depr": 0.082,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin", "Hybrid"],
        "avg_km_per_year": 13000,
        "specs": {"Mesin": "1.5L VTEC Turbo / 2.0L e:HEV", "Tenaga": "188 HP", "Konsumsi BBM": "16.4 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Honda",
        "model": "Civic RS",
        "body_type": "sedan",
        "base_price": 616_000_000,
        "annual_depr": 0.088,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 11500,
        "specs": {"Mesin": "1.5L VTEC Turbo", "Tenaga": "176 HP", "Konsumsi BBM": "14.5 km/L", "Kapasitas": "5 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Honda",
        "model": "BR-V Prestige",
        "body_type": "mpv",
        "base_price": 348_000_000,
        "annual_depr": 0.079,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 13500,
        "specs": {"Mesin": "1.5L DOHC i-VTEC", "Tenaga": "119 HP", "Konsumsi BBM": "15.6 km/L", "Kapasitas": "7 Kursi"},
    },

    # ==================== MOBIL: DAIHATSU ====================
    {
        "jenis": "mobil",
        "merek": "Daihatsu",
        "model": "Sigra R Deluxe",
        "body_type": "mpv",
        "base_price": 182_000_000,
        "annual_depr": 0.078,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 15000,
        "specs": {"Mesin": "1.2L 3NR-VE", "Tenaga": "87 HP", "Konsumsi BBM": "18.8 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Daihatsu",
        "model": "Xenia R ADS",
        "body_type": "mpv",
        "base_price": 268_000_000,
        "annual_depr": 0.077,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 14800,
        "specs": {"Mesin": "1.5L 2NR-VE", "Tenaga": "105 HP", "Konsumsi BBM": "16.0 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Daihatsu",
        "model": "Terios R Custom",
        "body_type": "suv",
        "base_price": 292_000_000,
        "annual_depr": 0.079,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 14200,
        "specs": {"Mesin": "1.5L Dual VVT-i", "Tenaga": "103 HP", "Konsumsi BBM": "14.5 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Daihatsu",
        "model": "Ayla R ADS",
        "body_type": "hatchback",
        "base_price": 189_000_000,
        "annual_depr": 0.080,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 12500,
        "specs": {"Mesin": "1.2L WA-VE", "Tenaga": "87 HP", "Konsumsi BBM": "19.5 km/L", "Kapasitas": "5 Kursi"},
    },

    # ==================== MOBIL: MITSUBISHI ====================
    {
        "jenis": "mobil",
        "merek": "Mitsubishi",
        "model": "Xpander Ultimate",
        "body_type": "mpv",
        "base_price": 322_000_000,
        "annual_depr": 0.072,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 14000,
        "specs": {"Mesin": "1.5L MIVEC", "Tenaga": "104 HP", "Konsumsi BBM": "15.4 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Mitsubishi",
        "model": "Pajero Sport Dakar",
        "body_type": "suv",
        "base_price": 652_000_000,
        "annual_depr": 0.076,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Diesel"],
        "avg_km_per_year": 15500,
        "specs": {"Mesin": "2.4L MIVEC Turbo Diesel", "Tenaga": "179 HP", "Konsumsi BBM": "12.5 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Mitsubishi",
        "model": "Xforce Ultimate",
        "body_type": "suv",
        "base_price": 412_000_000,
        "annual_depr": 0.079,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 12000,
        "specs": {"Mesin": "1.5L MIVEC CVT", "Tenaga": "104 HP", "Konsumsi BBM": "15.2 km/L", "Kapasitas": "5 Kursi"},
    },

    # ==================== MOBIL: SUZUKI ====================
    {
        "jenis": "mobil",
        "merek": "Suzuki",
        "model": "Ertiga Hybrid",
        "body_type": "mpv",
        "base_price": 292_000_000,
        "annual_depr": 0.078,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Hybrid", "Bensin"],
        "avg_km_per_year": 14000,
        "specs": {"Mesin": "1.5L K15B Smart Hybrid", "Tenaga": "103 HP", "Konsumsi BBM": "17.5 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Suzuki",
        "model": "XL7 Alpha",
        "body_type": "suv",
        "base_price": 309_000_000,
        "annual_depr": 0.077,
        "transmisi_opts": ["Otomatis", "Manual"],
        "bbm_opts": ["Hybrid", "Bensin"],
        "avg_km_per_year": 14000,
        "specs": {"Mesin": "1.5L K15B SHVS", "Tenaga": "103 HP", "Konsumsi BBM": "16.8 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Suzuki",
        "model": "Baleno Hatchback",
        "body_type": "hatchback",
        "base_price": 283_000_000,
        "annual_depr": 0.081,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 12000,
        "specs": {"Mesin": "1.5L K15B", "Tenaga": "103 HP", "Konsumsi BBM": "17.2 km/L", "Kapasitas": "5 Kursi"},
    },

    # ==================== MOBIL: HYUNDAI ====================
    {
        "jenis": "mobil",
        "merek": "Hyundai",
        "model": "Stargazer Prime",
        "body_type": "mpv",
        "base_price": 321_000_000,
        "annual_depr": 0.082,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 13500,
        "specs": {"Mesin": "1.5L Smartstream IVT", "Tenaga": "113 HP", "Konsumsi BBM": "15.5 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Hyundai",
        "model": "Creta Prime",
        "body_type": "suv",
        "base_price": 416_000_000,
        "annual_depr": 0.083,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 12500,
        "specs": {"Mesin": "1.5L Smartstream IVT", "Tenaga": "113 HP", "Konsumsi BBM": "15.1 km/L", "Kapasitas": "5 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Hyundai",
        "model": "Ioniq 5 Signature",
        "body_type": "suv",
        "base_price": 870_000_000,
        "annual_depr": 0.105,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Listrik (EV)"],
        "avg_km_per_year": 11000,
        "specs": {"Mesin": "Motor Listrik 72.6 kWh", "Tenaga": "214 HP", "Konsumsi BBM": "451 km/charge", "Kapasitas": "5 Kursi"},
    },

    # ==================== MOBIL: WULING ====================
    {
        "jenis": "mobil",
        "merek": "Wuling",
        "model": "Air ev Long Range",
        "body_type": "hatchback",
        "base_price": 275_000_000,
        "annual_depr": 0.112,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Listrik (EV)"],
        "avg_km_per_year": 9500,
        "specs": {"Mesin": "Motor Listrik 26.7 kWh", "Tenaga": "40 HP", "Konsumsi BBM": "300 km/charge", "Kapasitas": "4 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Wuling",
        "model": "Almaz RS Pro",
        "body_type": "suv",
        "base_price": 415_000_000,
        "annual_depr": 0.092,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin", "Hybrid"],
        "avg_km_per_year": 13000,
        "specs": {"Mesin": "1.5L Turbo / 2.0L Hybrid", "Tenaga": "140 HP", "Konsumsi BBM": "14.8 km/L", "Kapasitas": "7 Kursi"},
    },

    # ==================== MOBIL: MAZDA, NISSAN, BMW, MERCEDES-BENZ, BYD ====================
    {
        "jenis": "mobil",
        "merek": "Mazda",
        "model": "CX-5 Elite",
        "body_type": "suv",
        "base_price": 628_000_000,
        "annual_depr": 0.088,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 11500,
        "specs": {"Mesin": "2.5L Skyactiv-G", "Tenaga": "188 HP", "Konsumsi BBM": "13.5 km/L", "Kapasitas": "5 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Mazda",
        "model": "Mazda3 Hatchback",
        "body_type": "hatchback",
        "base_price": 565_000_000,
        "annual_depr": 0.089,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 10500,
        "specs": {"Mesin": "2.0L Skyactiv-G", "Tenaga": "153 HP", "Konsumsi BBM": "14.2 km/L", "Kapasitas": "5 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Nissan",
        "model": "Livina VL",
        "body_type": "mpv",
        "base_price": 310_000_000,
        "annual_depr": 0.084,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 13500,
        "specs": {"Mesin": "1.5L Twin VTC", "Tenaga": "104 HP", "Konsumsi BBM": "15.0 km/L", "Kapasitas": "7 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "BMW",
        "model": "320i M Sport",
        "body_type": "sedan",
        "base_price": 1_145_000_000,
        "annual_depr": 0.108,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 10000,
        "specs": {"Mesin": "2.0L TwinPower Turbo", "Tenaga": "184 HP", "Konsumsi BBM": "14.8 km/L", "Kapasitas": "5 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "Mercedes-Benz",
        "model": "C200 Avantgarde",
        "body_type": "sedan",
        "base_price": 1_210_000_000,
        "annual_depr": 0.110,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin", "Hybrid"],
        "avg_km_per_year": 9800,
        "specs": {"Mesin": "1.5L EQ Boost Turbo", "Tenaga": "204 HP", "Konsumsi BBM": "15.2 km/L", "Kapasitas": "5 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "BYD",
        "model": "Seal Performance",
        "body_type": "sedan",
        "base_price": 719_000_000,
        "annual_depr": 0.098,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Listrik (EV)"],
        "avg_km_per_year": 11000,
        "specs": {"Mesin": "Dual Motor Blade Battery 82.5 kWh", "Tenaga": "523 HP", "Konsumsi BBM": "580 km/charge", "Kapasitas": "5 Kursi"},
    },
    {
        "jenis": "mobil",
        "merek": "BYD",
        "model": "Atto 3 Superior",
        "body_type": "suv",
        "base_price": 515_000_000,
        "annual_depr": 0.095,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Listrik (EV)"],
        "avg_km_per_year": 11500,
        "specs": {"Mesin": "Motor Listrik 60.5 kWh", "Tenaga": "201 HP", "Konsumsi BBM": "480 km/charge", "Kapasitas": "5 Kursi"},
    },

    # ==================== MOTOR: HONDA, YAMAHA, KAWASAKI, SUZUKI, VESPA ====================
    {
        "jenis": "motor",
        "merek": "Honda",
        "model": "Vario 160",
        "body_type": "matic",
        "base_price": 27_800_000,
        "annual_depr": 0.082,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 9500,
        "specs": {"Mesin": "160cc eSP+", "Tenaga": "15.1 HP", "Konsumsi BBM": "46.9 km/L", "Tangki": "5.5 L"},
    },
    {
        "jenis": "motor",
        "merek": "Honda",
        "model": "Beat Deluxe",
        "body_type": "matic",
        "base_price": 19_800_000,
        "annual_depr": 0.078,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 10000,
        "specs": {"Mesin": "110cc eSP", "Tenaga": "8.9 HP", "Konsumsi BBM": "60.6 km/L", "Tangki": "4.2 L"},
    },
    {
        "jenis": "motor",
        "merek": "Honda",
        "model": "PCX 160",
        "body_type": "matic",
        "base_price": 33_400_000,
        "annual_depr": 0.076,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 10200,
        "specs": {"Mesin": "160cc 4-Katup eSP+", "Tenaga": "15.8 HP", "Konsumsi BBM": "45.0 km/L", "Tangki": "8.1 L"},
    },
    {
        "jenis": "motor",
        "merek": "Honda",
        "model": "CBR150R",
        "body_type": "sport",
        "base_price": 38_700_000,
        "annual_depr": 0.102,
        "transmisi_opts": ["Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 8200,
        "specs": {"Mesin": "150cc DOHC 6-Speed", "Tenaga": "16.9 HP", "Konsumsi BBM": "41.2 km/L", "Tangki": "12.0 L"},
    },
    {
        "jenis": "motor",
        "merek": "Honda",
        "model": "CRF150L",
        "body_type": "trail",
        "base_price": 37_200_000,
        "annual_depr": 0.079,
        "transmisi_opts": ["Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 7500,
        "specs": {"Mesin": "149cc SOHC PGM-FI", "Tenaga": "12.7 HP", "Konsumsi BBM": "39.3 km/L", "Tangki": "7.2 L"},
    },
    {
        "jenis": "motor",
        "merek": "Yamaha",
        "model": "NMAX 155",
        "body_type": "matic",
        "base_price": 33_200_000,
        "annual_depr": 0.075,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 10500,
        "specs": {"Mesin": "155cc Blue Core VVA", "Tenaga": "15.1 HP", "Konsumsi BBM": "43.5 km/L", "Tangki": "7.1 L"},
    },
    {
        "jenis": "motor",
        "merek": "Yamaha",
        "model": "Aerox 155",
        "body_type": "matic",
        "base_price": 31_500_000,
        "annual_depr": 0.077,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 10000,
        "specs": {"Mesin": "155cc VVA Connected", "Tenaga": "15.1 HP", "Konsumsi BBM": "42.5 km/L", "Tangki": "5.5 L"},
    },
    {
        "jenis": "motor",
        "merek": "Yamaha",
        "model": "R15 Connected",
        "body_type": "sport",
        "base_price": 40_300_000,
        "annual_depr": 0.100,
        "transmisi_opts": ["Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 8000,
        "specs": {"Mesin": "155cc VVA Assist & Slipper", "Tenaga": "19.0 HP", "Konsumsi BBM": "41.5 km/L", "Tangki": "11.0 L"},
    },
    {
        "jenis": "motor",
        "merek": "Yamaha",
        "model": "MX King 150",
        "body_type": "bebek",
        "base_price": 26_500_000,
        "annual_depr": 0.088,
        "transmisi_opts": ["Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 11500,
        "specs": {"Mesin": "150cc SOHC 5-Speed", "Tenaga": "15.1 HP", "Konsumsi BBM": "44.8 km/L", "Tangki": "4.2 L"},
    },
    {
        "jenis": "motor",
        "merek": "Kawasaki",
        "model": "KLX 150",
        "body_type": "trail",
        "base_price": 37_400_000,
        "annual_depr": 0.080,
        "transmisi_opts": ["Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 7200,
        "specs": {"Mesin": "144cc SOHC Air-Cooled", "Tenaga": "11.8 HP", "Konsumsi BBM": "38.0 km/L", "Tangki": "6.9 L"},
    },
    {
        "jenis": "motor",
        "merek": "Kawasaki",
        "model": "Ninja ZX-25R",
        "body_type": "sport",
        "base_price": 110_900_000,
        "annual_depr": 0.086,
        "transmisi_opts": ["Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 6500,
        "specs": {"Mesin": "250cc 4-Silinder Segaris DOHC", "Tenaga": "50.3 HP", "Konsumsi BBM": "24.5 km/L", "Tangki": "15.0 L"},
    },
    {
        "jenis": "motor",
        "merek": "Suzuki",
        "model": "Satria F150",
        "body_type": "bebek",
        "base_price": 28_900_000,
        "annual_depr": 0.094,
        "transmisi_opts": ["Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 10500,
        "specs": {"Mesin": "150cc DOHC 4-Valve", "Tenaga": "18.2 HP", "Konsumsi BBM": "41.0 km/L", "Tangki": "4.0 L"},
    },
    {
        "jenis": "motor",
        "merek": "Suzuki",
        "model": "GSX-R150",
        "body_type": "sport",
        "base_price": 35_300_000,
        "annual_depr": 0.104,
        "transmisi_opts": ["Manual"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 8500,
        "specs": {"Mesin": "150cc DOHC Keyless", "Tenaga": "18.9 HP", "Konsumsi BBM": "42.0 km/L", "Tangki": "11.0 L"},
    },
    {
        "jenis": "motor",
        "merek": "Vespa",
        "model": "Sprint 150 i-get",
        "body_type": "matic",
        "base_price": 57_100_000,
        "annual_depr": 0.065,
        "transmisi_opts": ["Otomatis"],
        "bbm_opts": ["Bensin"],
        "avg_km_per_year": 7000,
        "specs": {"Mesin": "154.8cc i-get ABS", "Tenaga": "11.6 HP", "Konsumsi BBM": "41.0 km/L", "Tangki": "8.0 L"},
    },
]

CITY_FACTORS = {
    "Jakarta": 1.00,
    "Surabaya": 0.98,
    "Bandung": 0.99,
    "Medan": 0.96,
    "Semarang": 0.97,
    "Yogyakarta": 0.985,
    "Makassar": 0.965,
    "Denpasar": 1.01,
}

CONDITION_FACTORS = {
    1: 0.74,  # Butuh Perbaikan Berat
    2: 0.85,  # Kurang Terawat
    3: 0.94,  # Standar Pemakaian
    4: 1.00,  # Terawat Baik
    5: 1.06,  # Istimewa / Seperti Baru
}

SURAT_FACTORS = {
    "Lengkap (STNK + BPKB + Faktur)": 1.00,
    "Hanya STNK + BPKB": 0.97,
    "Hanya STNK Saja": 0.62,
    "Hanya BPKB Saja": 0.85,
}

CURRENT_YEAR = 2025
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATASET_PATH = os.path.join(BASE_DIR, "data", "vehicles_dataset.csv")


def generate_dataset(n_samples: int = 1800, output_path: str = DEFAULT_DATASET_PATH) -> pd.DataFrame:
    """Menghasilkan dataset kendaraan bekas realistis dan menyimpannya ke CSV."""
    rows = []
    cities = list(CITY_FACTORS.keys())

    # Pastikan setiap model kendaraan muncul minimal 20 kali di dataset
    for idx in range(n_samples):
        if idx < len(VEHICLE_CATALOG) * 20:
            item = VEHICLE_CATALOG[idx % len(VEHICLE_CATALOG)]
        else:
            item = random.choice(VEHICLE_CATALOG)

        tahun = random.randint(2015, 2024)
        age = max(1, CURRENT_YEAR - tahun)

        expected_km = age * item["avg_km_per_year"]
        kilometer = int(max(1200, np.random.normal(expected_km, expected_km * 0.30)))

        transmisi = random.choice(item["transmisi_opts"])
        bahan_bakar = random.choice(item["bbm_opts"])
        kondisi = random.choices([1, 2, 3, 4, 5], weights=[5, 12, 35, 34, 14])[0]
        surat = random.choices(
            list(SURAT_FACTORS.keys()),
            weights=[58, 28, 9, 5],
        )[0]
        kota = random.choice(cities)

        age_retention = (1.0 - item["annual_depr"]) ** age
        km_ratio = (kilometer - expected_km) / max(expected_km, 10000)
        km_factor = max(0.72, min(1.08, 1.0 - (km_ratio * 0.085)))

        trans_factor = 1.03 if transmisi == "Otomatis" else 0.97
        bbm_factor = (
            1.06
            if bahan_bakar in ("Hybrid", "Listrik (EV)")
            else (1.04 if bahan_bakar == "Diesel" else 1.00)
        )

        cond_factor = CONDITION_FACTORS[kondisi]
        surat_factor = SURAT_FACTORS[surat]
        city_factor = CITY_FACTORS[kota]
        noise = np.random.normal(1.0, 0.02)

        raw_price = (
            item["base_price"]
            * age_retention
            * km_factor
            * trans_factor
            * bbm_factor
            * cond_factor
            * surat_factor
            * city_factor
            * noise
        )

        rounding_unit = 100_000 if item["jenis"] == "motor" else 500_000
        harga = int(round(raw_price / rounding_unit) * rounding_unit)

        rows.append(
            {
                "jenis": item["jenis"],
                "merek": item["merek"],
                "model": item["model"],
                "tahun": tahun,
                "kilometer": kilometer,
                "transmisi": transmisi,
                "bahan_bakar": bahan_bakar,
                "kondisi": kondisi,
                "surat": surat,
                "kota": kota,
                "harga": harga,
            }
        )

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"[HargaBekas] Dataset berhasil dibuat: {output_path} ({len(df)} baris, {len(VEHICLE_CATALOG)} model)")
    return df


if __name__ == "__main__":
    generate_dataset()
