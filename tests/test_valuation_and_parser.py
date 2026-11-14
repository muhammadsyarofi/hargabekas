"""
Unit Test untuk Sistem HargaBekas:
1. Pengujian parser & validator skema JSON hasil analisis foto (`parse_and_validate_vision_json`).
2. Pengujian validasi magic bytes gambar & penghapusan EXIF (`verify_image_magic_bytes`, `sanitize_and_save_photo`).
3. Pengujian rumus kalkulasi harga dengan kerusakan (`calculate_damage_deductions`, `predict_vehicle_price`).

Jalankan dengan:
    python -m unittest tests/test_valuation_and_parser.py
"""

import io
import os
import sys
import unittest
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from models.damage_analyzer import (
    parse_and_validate_vision_json,
    sanitize_and_save_photo,
    verify_image_magic_bytes,
)
from models.predictor import calculate_damage_deductions, predict_vehicle_price


class TestVisionJsonParserAndValuation(unittest.TestCase):
    def test_parse_vision_json_strips_code_fence_and_clamps_values(self):
        """Parser harus menghapus markdown ```json dan membatasi nilai ekstrem ke rentang valid."""
        raw_llm_output = """Berikut hasil analisis foto:
```json
{
  "kualitas_foto": {"cukup": true, "masalah": []},
  "kendaraan_terdeteksi": {"jenis": "mobil", "perkiraan_model": "Honda Brio RS"},
  "kerusakan": [
    {
      "bagian": "bumper_depan",
      "jenis": "penyok",
      "keparahan": 99,
      "perkiraan_luas_persen": 250,
      "bbox": [-0.5, 0.4, 2.5, 0.3],
      "foto_ke": 5,
      "keyakinan": 1.8,
      "catatan": "Penyok cukup dalam di sudut kiri"
    }
  ],
  "indikasi_struktural": {"ada": false, "alasan": ""},
  "ringkasan": "Ada penyok pada bumper depan."
}
```
Semoga membantu!"""

        parsed = parse_and_validate_vision_json(raw_llm_output, total_photos=2, default_jenis="mobil")
        self.assertEqual(parsed["kendaraan_terdeteksi"]["jenis"], "mobil")
        self.assertEqual(len(parsed["kerusakan"]), 1)

        dmg = parsed["kerusakan"][0]
        self.assertEqual(dmg["bagian"], "bumper_depan")
        self.assertEqual(dmg["jenis"], "penyok")
        # Keparahan 99 harus di-clamp menjadi 4
        self.assertEqual(dmg["keparahan"], 4)
        # Luas 250% harus di-clamp menjadi 100
        self.assertEqual(dmg["perkiraan_luas_persen"], 100)
        # foto_ke 5 pada total_photos=2 harus di-clamp menjadi 2
        self.assertEqual(dmg["foto_ke"], 2)
        # keyakinan 1.8 harus di-clamp menjadi 1.0
        self.assertEqual(dmg["keyakinan"], 1.0)
        # Karena keparahan == 4, indikasi_struktural.ada otomatis True
        self.assertTrue(parsed["indikasi_struktural"]["ada"])

    def test_magic_bytes_validation_and_exif_strip(self):
        """Harus menolak file teks palsu berekstensi .jpg dan menerima gambar asli serta menghapus EXIF."""
        ok_fake, _ = verify_image_magic_bytes(b"ini bukan file gambar melainkan teks biasa")
        self.assertFalse(ok_fake)

        # Buat gambar JPEG valid di memori
        im = Image.new("RGB", (640, 480), color=(140, 145, 150))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        raw_jpeg = buf.getvalue()

        ok_real, mime = verify_image_magic_bytes(raw_jpeg)
        self.assertTrue(ok_real)
        self.assertEqual(mime, "image/jpeg")

        saved_ok, err_msg, meta = sanitize_and_save_photo(raw_jpeg, slot_label="depan")
        self.assertTrue(saved_ok, err_msg)
        self.assertTrue(meta["filename"].startswith("insp_"))
        self.assertEqual(meta["width"], 640)

        # Bersihkan file uji
        saved_path = os.path.join(BASE_DIR, "static", "uploads", "inspections", meta["filename"])
        if os.path.exists(saved_path):
            os.remove(saved_path)

    def test_damage_deduction_formula_and_prediction(self):
        """
        Rumus wajib:
        harga_akhir = harga_dasar_kondisi_normal - estimasi_biaya_perbaikan - diskon_pasar_akibat_kerusakan
        """
        kerusakan = [
            {
                "bagian": "bumper_depan",
                "jenis": "goresan_dalam",
                "keparahan": 2,
                "perkiraan_luas_persen": 25,
                "bbox": [0.2, 0.5, 0.3, 0.2],
                "foto_ke": 1,
                "keyakinan": 0.9,
            },
            {
                "bagian": "pintu_kiri",
                "jenis": "penyok",
                "keparahan": 2,
                "perkiraan_luas_persen": 20,
                "bbox": [0.4, 0.4, 0.2, 0.2],
                "foto_ke": 2,
                "keyakinan": 0.85,
            },
        ]

        res = predict_vehicle_price(
            {
                "jenis": "mobil",
                "merek": "Honda",
                "model": "Brio RS",
                "tahun": 2022,
                "kilometer": 25000,
                "transmisi": "Otomatis",
                "bahan_bakar": "Bensin",
                "kondisi": 4,
                "surat": "Lengkap (STNK + BPKB + Faktur)",
                "kota": "Jakarta",
                "kerusakan": kerusakan,
                "indikasi_struktural": {"ada": False, "alasan": ""},
                "kualitas_foto": {"cukup": True, "masalah": []},
            }
        )

        self.assertGreater(res["harga_dasar_normal"], 100_000_000)
        self.assertGreater(res["estimasi_biaya_perbaikan"], 0)
        self.assertGreater(res["diskon_pasar_rp"], 0)
        self.assertEqual(
            res["harga_estimasi"],
            res["harga_dasar_normal"] - res["estimasi_biaya_perbaikan"] - res["diskon_pasar_rp"],
        )
        self.assertLess(res["harga_min"], res["harga_estimasi"])
        self.assertGreater(res["harga_max"], res["harga_estimasi"])
        self.assertEqual(len(res["waterfall_steps"]), 5)  # Base + 2 repairs + discount + final


if __name__ == "__main__":
    unittest.main()
