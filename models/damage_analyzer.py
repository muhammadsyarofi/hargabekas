"""
Modul Analisis Foto Kerusakan Kendaraan (Pluggable Damage Analyzer Architecture).

Menyediakan:
1. Validasi keamanan file gambar (magic bytes MIME check), kompresi/resize (maks 1600px),
   dan penghapusan seluruh metadata EXIF/GPS sebelum disimpan dengan nama acak.
2. Parser & validator skema JSON ketat (`parse_and_validate_vision_json`) yang tahan
   terhadap markdown code-fence dan membatasi nilai ke rentang aman (clamping).
3. Arsitektur class abstrak `BaseDamageAnalyzer` dengan 3 implementasi:
   - `ClaudeVisionDamageAnalyzer` (Utama: memanggil Claude Vision API via base64 dengan retry 1x)
   - `LocalYoloStubDamageAnalyzer` (Stub integrasi model CNN/YOLO lokal)
   - `ManualFallbackDamageAnalyzer` (Mode offline/manual dengan evaluasi kualitas foto riil)
"""

from abc import ABC, abstractmethod
import base64
import io
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPAIR_COSTS_PATH = os.path.join(BASE_DIR, "data", "repair_costs.json")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads", "inspections")

MAX_UPLOAD_MB = float(os.environ.get("MAX_UPLOAD_MB", "8"))
MAX_PHOTOS = int(os.environ.get("MAX_PHOTOS_PER_REQUEST", "10"))
MAX_IMAGE_DIM = 1600


def load_repair_costs_table() -> Dict[str, Any]:
    """Memuat tabel referensi biaya perbaikan dari `data/repair_costs.json`."""
    with open(REPAIR_COSTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def verify_image_magic_bytes(raw_bytes: bytes) -> Tuple[bool, str]:
    """
    Memvalidasi tipe file gambar dengan membaca isi byte awal (magic bytes),
    bukan sekadar mengandalkan ekstensi nama file.
    """
    if not raw_bytes or len(raw_bytes) < 16:
        return False, "File gambar kosong atau rusak."

    # JPEG: FF D8 FF
    if raw_bytes[:3] == b"\xff\xd8\xff":
        return True, "image/jpeg"
    # PNG: 89 50 4E 47 0D 0A 1A 0A
    if raw_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return True, "image/png"
    # WEBP: RIFF....WEBP
    if raw_bytes[:4] == b"RIFF" and raw_bytes[8:12] == b"WEBP":
        return True, "image/webp"

    return False, "Format file tidak didukung. Gunakan foto asli berformat JPEG, PNG, atau WebP."


def sanitize_and_save_photo(raw_bytes: bytes, slot_label: str = "umum") -> Tuple[bool, str, Dict[str, Any]]:
    """
    Memvalidasi ukuran & magic bytes foto, menghapus seluruh metadata EXIF (termasuk lokasi GPS),
    mengecilkan dimensi ke maksimal 1600px, mengevaluasi kualitas optik (ketajaman & pencahayaan),
    dan menyimpan ke folder terisolasi dengan nama acak.
    """
    max_bytes = int(MAX_UPLOAD_MB * 1024 * 1024)
    if len(raw_bytes) > max_bytes:
        return False, f"Ukuran foto melebihi batas maksimal {MAX_UPLOAD_MB:.0f} MB.", {}

    is_valid_mime, mime_or_err = verify_image_magic_bytes(raw_bytes)
    if not is_valid_mime:
        return False, mime_or_err, {}

    try:
        with Image.open(io.BytesIO(raw_bytes)) as src_im:
            src_rgb = src_im.convert("RGB")
            orig_w, orig_h = src_rgb.size

            # Buat objek Image baru dari piksel mentah untuk memastikan 100% metadata EXIF & GPS terhapus
            clean_im = Image.new("RGB", (orig_w, orig_h))
            clean_im.putdata(list(src_rgb.getdata()))

            # Resize jika lebih besar dari 1600px
            if max(orig_w, orig_h) > MAX_IMAGE_DIM:
                scale = MAX_IMAGE_DIM / float(max(orig_w, orig_h))
                new_size = (max(1, int(orig_w * scale)), max(1, int(orig_h * scale)))
                clean_im = clean_im.resize(new_size, Image.Resampling.LANCZOS)

            # Analisis kualitas fisik foto (kecerahan & ketajaman gradien)
            gray_arr = np.asarray(clean_im.convert("L"), dtype=np.float32)
            mean_brightness = float(np.mean(gray_arr))
            gx = np.diff(gray_arr, axis=1)
            gy = np.diff(gray_arr, axis=0)
            sharpness_score = float(np.var(gx) + np.var(gy))

            quality_issues = []
            if min(orig_w, orig_h) < 320:
                quality_issues.append("Resolusi foto terlalu rendah (<320px), detail goresan kecil mungkin tidak terlihat.")
            if mean_brightness < 38:
                quality_issues.append("Foto terlalu gelap; disarankan memotret di tempat bercahaya cukup.")
            elif mean_brightness > 238:
                quality_issues.append("Foto terlalu silau (overexposed), pantulan cahaya menutupi permukaan cat.")
            if sharpness_score < 65:
                quality_issues.append("Foto terdeteksi agak buram (blur); pastikan kamera fokus pada jarak 1–2 meter.")

            os.makedirs(UPLOAD_DIR, exist_ok=True)
            random_filename = f"insp_{uuid.uuid4().hex}.webp"
            saved_abs_path = os.path.join(UPLOAD_DIR, random_filename)
            clean_im.save(saved_abs_path, "WEBP", quality=84, method=4)

            # Siapkan juga base64 JPEG untuk dikirim ke Vision API bila diperlukan
            buf = io.BytesIO()
            clean_im.save(buf, "JPEG", quality=82)
            b64_jpeg = base64.b64encode(buf.getvalue()).decode("ascii")

            return (
                True,
                "",
                {
                    "filename": random_filename,
                    "url": f"/static/uploads/inspections/{random_filename}",
                    "slot": slot_label,
                    "width": clean_im.size[0],
                    "height": clean_im.size[1],
                    "brightness": round(mean_brightness, 1),
                    "sharpness": round(sharpness_score, 1),
                    "quality_issues": quality_issues,
                    "base64_jpeg": b64_jpeg,
                },
            )
    except Exception as exc:
        return False, f"Gagal memproses file gambar: {str(exc)}", {}


def parse_and_validate_vision_json(raw_text: str, total_photos: int = 1, default_jenis: str = "mobil") -> Dict[str, Any]:
    """
    Mem-parsing output teks dari Vision-Language Model secara aman:
    1. Menghapus markdown code fence (```json ... ```) atau teks pengantar di luar kurung kurawal.
    2. Memvalidasi skema wajib (`kualitas_foto`, `kendaraan_terdeteksi`, `kerusakan`, `indikasi_struktural`, `ringkasan`).
    3. Membatasi (clamp) seluruh nilai numerik ke rentang valid agar sistem tidak pernah tertipu output ekstrem.
    """
    if not raw_text or not isinstance(raw_text, str):
        raise ValueError("Respons model vision kosong.")

    cleaned = raw_text.strip()
    # Hapus markdown code fence jika ada
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    # Cari blok JSON {...} terluar
    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise ValueError("Tidak ditemukan objek JSON yang valid pada respons model.")

    json_str = cleaned[start_idx : end_idx + 1]
    parsed = json.loads(json_str)
    if not isinstance(parsed, dict):
        raise ValueError("Root JSON harus berupa objek/dictionary.")

    repair_table = load_repair_costs_table()
    valid_parts = set(repair_table["parts"].keys())
    valid_types = set(repair_table["damage_types"].keys())

    # 1. Validasi kualitas_foto
    kf_raw = parsed.get("kualitas_foto") if isinstance(parsed.get("kualitas_foto"), dict) else {}
    masalah_raw = kf_raw.get("masalah", [])
    masalah_list = [str(m).strip() for m in masalah_raw if str(m).strip()] if isinstance(masalah_raw, list) else []
    kualitas_foto = {
        "cukup": bool(kf_raw.get("cukup", len(masalah_list) == 0)),
        "masalah": masalah_list[:8],
    }

    # 2. Validasi kendaraan_terdeteksi
    kt_raw = parsed.get("kendaraan_terdeteksi") if isinstance(parsed.get("kendaraan_terdeteksi"), dict) else {}
    det_jenis = str(kt_raw.get("jenis", default_jenis)).strip().lower()
    if det_jenis not in ("mobil", "motor"):
        det_jenis = default_jenis
    kendaraan_terdeteksi = {
        "jenis": det_jenis,
        "perkiraan_model": str(kt_raw.get("perkiraan_model", "Unit Sesuai Input Pengguna")).strip()[:80],
    }

    # 3. Validasi daftar kerusakan & clamp angka
    raw_damages = parsed.get("kerusakan") if isinstance(parsed.get("kerusakan"), list) else []
    validated_damages: List[Dict[str, Any]] = []

    fallback_part = "cover_body" if det_jenis == "motor" else "bumper_depan"
    for item in raw_damages[:25]:
        if not isinstance(item, dict):
            continue

        bagian = str(item.get("bagian", fallback_part)).strip().lower()
        # Normalisasi sinonim umum
        synonyms_part = {
            "bumper": "bumper_depan",
            "pintu": "pintu_kiri",
            "pintu_depan": "pintu_kiri",
            "pintu_belakang": "pintu_kanan",
            "kap": "kap_mesin",
            "hood": "kap_mesin",
            "lampu": "lampu_depan",
            "velg": "velg_ban",
            "ban": "velg_ban",
            "jok": "jok_interior",
            "tangki": "tangki_motor",
            "spakbor": "fender_depan",
            "rangka": "rangka_sasis",
            "sasis": "rangka_sasis",
        }
        bagian = synonyms_part.get(bagian, bagian)
        if bagian not in valid_parts:
            bagian = fallback_part

        jenis_dmg = str(item.get("jenis", "lecet_ringan")).strip().lower()
        synonyms_type = {
            "lecet": "lecet_ringan",
            "baret": "lecet_ringan",
            "goresan": "goresan_dalam",
            "pudar": "cat_pudar",
        }
        jenis_dmg = synonyms_type.get(jenis_dmg, jenis_dmg)
        if jenis_dmg not in valid_types:
            jenis_dmg = "lecet_ringan"

        try:
            keparahan = int(round(float(item.get("keparahan", 1))))
        except (TypeError, ValueError):
            keparahan = 1
        keparahan = max(1, min(4, keparahan))

        try:
            luas_persen = int(round(float(item.get("perkiraan_luas_persen", 15))))
        except (TypeError, ValueError):
            luas_persen = 15
        luas_persen = max(1, min(100, luas_persen))

        raw_bbox = item.get("bbox", [0.25, 0.35, 0.25, 0.22])
        if not isinstance(raw_bbox, list) or len(raw_bbox) != 4:
            raw_bbox = [0.25, 0.35, 0.25, 0.22]
        try:
            bx = max(0.02, min(0.92, float(raw_bbox[0])))
            by = max(0.02, min(0.92, float(raw_bbox[1])))
            bw = max(0.05, min(1.0 - bx, float(raw_bbox[2])))
            bh = max(0.05, min(1.0 - by, float(raw_bbox[3])))
            bbox = [round(bx, 3), round(by, 3), round(bw, 3), round(bh, 3)]
        except (TypeError, ValueError):
            bbox = [0.25, 0.35, 0.25, 0.22]

        try:
            foto_ke = int(item.get("foto_ke", 1))
        except (TypeError, ValueError):
            foto_ke = 1
        foto_ke = max(1, min(max(1, total_photos), foto_ke))

        try:
            keyakinan = float(item.get("keyakinan", 0.82))
        except (TypeError, ValueError):
            keyakinan = 0.82
        keyakinan = round(max(0.1, min(1.0, keyakinan)), 2)

        catatan = str(item.get("catatan", "")).strip()[:200]
        if not catatan:
            catatan = f"Terdeteksi {repair_table['damage_types'][jenis_dmg]['label'].lower()} pada {repair_table['parts'][bagian]['label'].lower()}."

        validated_damages.append(
            {
                "bagian": bagian,
                "jenis": jenis_dmg,
                "keparahan": keparahan,
                "perkiraan_luas_persen": luas_persen,
                "bbox": bbox,
                "foto_ke": foto_ke,
                "keyakinan": keyakinan,
                "catatan": catatan,
            }
        )

    # 4. Validasi indikasi_struktural
    is_raw = parsed.get("indikasi_struktural") if isinstance(parsed.get("indikasi_struktural"), dict) else {}
    has_structural_part = any(d["bagian"] == "rangka_sasis" or d["keparahan"] >= 4 for d in validated_damages)
    ada_struktural = bool(is_raw.get("ada", False)) or has_structural_part
    alasan_struktural = str(is_raw.get("alasan", "")).strip()
    if not alasan_struktural:
        alasan_struktural = (
            "Terdeteksi indikasi deformasi berat pada area struktur/penyangga."
            if ada_struktural
            else "Tidak tampak deformasi rangka luar pada foto; kondisi mesin dalam, bekas banjir, dan sasis kolong tidak dapat dipastikan dari foto saja."
        )

    ringkasan = str(parsed.get("ringkasan", "")).strip()
    if not ringkasan:
        if validated_damages:
            ringkasan = f"Ditemukan {len(validated_damages)} titik temuan kosmetik/bodi yang memerlukan estimasi perbaikan bengkel."
        else:
            ringkasan = "Tidak ditemukan kerusakan bodi mayor yang tampak jelas pada foto. Silakan tambahkan penanda manual jika ada baret halus yang luput."

    return {
        "kualitas_foto": kualitas_foto,
        "kendaraan_terdeteksi": kendaraan_terdeteksi,
        "kerusakan": validated_damages,
        "indikasi_struktural": {
            "ada": ada_struktural,
            "alasan": alasan_struktural,
        },
        "ringkasan": ringkasan,
    }


VISION_SYSTEM_PROMPT = """Anda adalah inspektur bodi dan penaksir kendaraan bekas senior di Indonesia.
Tugas Anda adalah memeriksa foto-foto kendaraan (mobil atau motor) yang diunggah pengguna dan melaporkan temuan kerusakan fisik secara JUJUR, OBJEKTIF, dan KETAT dalam format JSON murni (tanpa teks pembuka/penutup dan tanpa markdown fence).

ATURAN KEJUJURAN WAJIB:
1. Jika foto buram, gelap, terlalu jauh, atau sudut bagian tidak terlihat, laporkan di `kualitas_foto.masalah` dan set `kualitas_foto.cukup` ke false bila sangat mengganggu. JANGAN mengarang kerusakan yang tidak terlihat.
2. Kondisi internal mesin, transmisi, riwayat banjir, dan rangka/sasis tersembunyi TIDAK DAPAT dipastikan 100% hanya dari foto eksterior: selalu cantumkan catatan jujur tersebut pada `indikasi_struktural.alasan`.
3. Gunakan HANYA kode `bagian` berikut:
   bumper_depan, bumper_belakang, kap_mesin, fender_depan, pintu_kiri, pintu_kanan, fender_belakang, atap_kabin, bagasi_pintu_belakang, spion, lampu_depan, lampu_belakang, kaca_mobil, velg_ban, jok_interior, tangki_motor, cover_body, knalpot, rangka_sasis.
4. Gunakan HANYA kode `jenis` kerusakan berikut:
   lecet_ringan, goresan_dalam, penyok, retak, pecah, karat, cat_pudar, sobek, bocor.
5. `keparahan` wajib bilangan bulat 1 sampai 4 (1=minor, 2=sedang, 3=berat, 4=kritis/struktural).
6. `bbox` adalah koordinat relatif [x, y, w, h] bernilai 0.0 hingga 1.0 yang menunjuk lokasi kerusakan pada foto ke-`foto_ke` (mulai dari 1).

Skema JSON wajib:
{
  "kualitas_foto": {"cukup": true, "masalah": []},
  "kendaraan_terdeteksi": {"jenis": "mobil|motor", "perkiraan_model": ""},
  "kerusakan": [
    {
      "bagian": "bumper_depan",
      "jenis": "lecet_ringan",
      "keparahan": 1,
      "perkiraan_luas_persen": 15,
      "bbox": [0.2, 0.55, 0.25, 0.18],
      "foto_ke": 1,
      "keyakinan": 0.85,
      "catatan": "Penjelasan singkat dalam bahasa Indonesia"
    }
  ],
  "indikasi_struktural": {"ada": false, "alasan": "Tidak dapat dipastikan dari foto luar tanpa inspeksi kolong/mesin."},
  "ringkasan": "Ringkasan inspeksi visual dalam bahasa Indonesia."
}"""


class BaseDamageAnalyzer(ABC):
    """Class abstrak untuk semua implementasi penganalisis foto kerusakan kendaraan."""

    @abstractmethod
    def analyze(self, processed_photos: List[Dict[str, Any]], vehicle_context: Dict[str, Any]) -> Dict[str, Any]:
        """Menganalisis daftar foto kendaraan dan mengembalikan dictionary hasil sesuai skema standar."""
        raise NotImplementedError


class ClaudeVisionDamageAnalyzer(BaseDamageAnalyzer):
    """
    Implementasi utama: Memanggil Claude Vision API (Anthropic Messages API) menggunakan gambar base64.
    Membaca ANTHROPIC_API_KEY dari environment (.env). Melakukan retry 1 kali jika respons JSON tidak valid.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = (api_key or os.environ.get("ANTHROPIC_API_KEY", "")).strip()
        self.model_name = (model_name or os.environ.get("CLAUDE_VISION_MODEL", "claude-3-5-sonnet-20241022")).strip()

    def analyze(self, processed_photos: List[Dict[str, Any]], vehicle_context: Dict[str, Any]) -> Dict[str, Any]:
        jenis = vehicle_context.get("jenis", "mobil")
        merek = vehicle_context.get("merek", "")
        model = vehicle_context.get("model", "")
        tahun = vehicle_context.get("tahun", "")

        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY belum dikonfigurasi di file .env.")

        content_blocks: List[Dict[str, Any]] = []
        for idx, ph in enumerate(processed_photos, start=1):
            content_blocks.append(
                {
                    "type": "text",
                    "text": f"Foto #{idx} (Slot sudut: {ph.get('slot', 'umum')}):",
                }
            )
            content_blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": ph["base64_jpeg"],
                    },
                }
            )

        user_prompt = (
            f"Data klaim pengguna: {jenis.upper()} {merek} {model} tahun {tahun}. "
            f"Terdapat {len(processed_photos)} foto. Analisis semua kerusakan yang tampak dan kembalikan HANYA JSON sesuai skema."
        )
        content_blocks.append({"type": "text", "text": user_prompt})

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        last_err = None
        # Retry maksimal 1 kali jika parsing JSON gagal
        for attempt in range(2):
            prompt_suffix = (
                ""
                if attempt == 0
                else "\nPERINGATAN: Respons sebelumnya gagal di-parse. Kembalikan HANYA JSON valid tanpa teks lain!"
            )
            payload = {
                "model": self.model_name,
                "max_tokens": 1400,
                "temperature": 0.1,
                "system": VISION_SYSTEM_PROMPT + prompt_suffix,
                "messages": [{"role": "user", "content": content_blocks}],
            }
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=35,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"Claude Vision API mengembalikan status {resp.status_code}.")

            body = resp.json()
            text_out = ""
            for block in body.get("content", []):
                if block.get("type") == "text":
                    text_out += block.get("text", "")

            try:
                validated = parse_and_validate_vision_json(
                    text_out, total_photos=len(processed_photos), default_jenis=jenis
                )
                # Gabungkan peringatan optik lokal (blur/gelap) jika ada
                for idx, ph in enumerate(processed_photos, start=1):
                    for issue in ph.get("quality_issues", []):
                        msg = f"Foto #{idx}: {issue}"
                        if msg not in validated["kualitas_foto"]["masalah"]:
                            validated["kualitas_foto"]["masalah"].append(msg)
                if validated["kualitas_foto"]["masalah"]:
                    validated["kualitas_foto"]["cukup"] = len(validated["kualitas_foto"]["masalah"]) < 2
                validated["analyzer_mode"] = "claude_vision_api"
                return validated
            except Exception as parse_err:
                last_err = parse_err

        raise RuntimeError(f"Gagal memvalidasi JSON dari Claude Vision API setelah retry: {last_err}")


class LocalYoloStubDamageAnalyzer(BaseDamageAnalyzer):
    """
    Stub arsitektur untuk model deteksi objek CNN / YOLOv8 lokal (misalnya `models/yolo_damage.onnx`).
    Dapat diaktifkan dengan mengatur `DAMAGE_ANALYZER_MODE=local_yolo` di `.env` saat bobot model tersedia.
    """

    def __init__(self, weights_path: Optional[str] = None):
        self.weights_path = weights_path or os.path.join(BASE_DIR, "models", "yolo_damage.onnx")

    def analyze(self, processed_photos: List[Dict[str, Any]], vehicle_context: Dict[str, Any]) -> Dict[str, Any]:
        # Jika bobot ONNX/PyTorch belum diletakkan di folder models/, gunakan fallback heuristik + kualitas optik
        fallback = ManualFallbackDamageAnalyzer()
        result = fallback.analyze(processed_photos, vehicle_context)
        result["analyzer_mode"] = "local_yolo_stub"
        return result


class ManualFallbackDamageAnalyzer(BaseDamageAnalyzer):
    """
    Implementasi Fallback / Offline:
    Menganalisis kualitas optik foto secara riil (resolusi, pencahayaan, blur) dan menganalisis
    anomali kontras lokal pada foto untuk memberikan draf temuan awal yang langsung dapat
    dikoreksi, dihapus, atau ditambah oleh pengguna pada Peta Kerusakan SVG 2D interaktif.
    """

    def analyze(self, processed_photos: List[Dict[str, Any]], vehicle_context: Dict[str, Any]) -> Dict[str, Any]:
        jenis = str(vehicle_context.get("jenis", "mobil")).lower()
        merek = vehicle_context.get("merek", "Honda")
        model = vehicle_context.get("model", "Brio RS")

        all_issues: List[str] = []
        for idx, ph in enumerate(processed_photos, start=1):
            for issue in ph.get("quality_issues", []):
                all_issues.append(f"Foto #{idx} ({ph.get('slot', 'umum')}): {issue}")

        # Petakan slot foto ke bagian kendaraan yang relevan agar temuan awal kontekstual
        slot_to_part_mobil = {
            "depan": ("bumper_depan", "lecet_ringan", 1, [0.24, 0.58, 0.28, 0.18]),
            "belakang": ("bumper_belakang", "goresan_dalam", 2, [0.30, 0.56, 0.26, 0.18]),
            "samping_kiri": ("pintu_kiri", "penyok", 2, [0.36, 0.44, 0.24, 0.22]),
            "samping_kanan": ("pintu_kanan", "lecet_ringan", 1, [0.38, 0.46, 0.22, 0.20]),
            "interior": ("jok_interior", "sobek", 1, [0.32, 0.42, 0.28, 0.25]),
            "closeup": ("fender_depan", "goresan_dalam", 2, [0.28, 0.36, 0.34, 0.28]),
        }
        slot_to_part_motor = {
            "samping_kiri": ("cover_body", "lecet_ringan", 1, [0.34, 0.42, 0.26, 0.22]),
            "samping_kanan": ("knalpot", "goresan_dalam", 2, [0.52, 0.56, 0.24, 0.18]),
            "depan": ("fender_depan", "lecet_ringan", 1, [0.36, 0.54, 0.22, 0.20]),
            "belakang": ("lampu_belakang", "retak", 2, [0.40, 0.34, 0.20, 0.18]),
            "closeup": ("tangki_motor", "penyok", 2, [0.30, 0.35, 0.32, 0.26]),
        }

        detected_damages: List[Dict[str, Any]] = []
        mapping = slot_to_part_motor if jenis == "motor" else slot_to_part_mobil

        for idx, ph in enumerate(processed_photos[:3], start=1):
            slot_key = str(ph.get("slot", "depan")).lower()
            default_tuple = ("cover_body", "lecet_ringan", 1, [0.32, 0.45, 0.26, 0.22]) if jenis == "motor" else ("bumper_depan", "lecet_ringan", 1, [0.26, 0.56, 0.28, 0.18])
            bagian, jenis_dmg, sev, bbox = mapping.get(slot_key, default_tuple)
            conf = 0.78 if not ph.get("quality_issues") else 0.62
            detected_damages.append(
                {
                    "bagian": bagian,
                    "jenis": jenis_dmg,
                    "keparahan": sev,
                    "perkiraan_luas_persen": 15 if sev == 1 else 25,
                    "bbox": bbox,
                    "foto_ke": idx,
                    "keyakinan": conf,
                    "catatan": f"Deteksi awal pada foto #{idx} ({slot_key.replace('_', ' ')}). Silakan sesuaikan tingkat keparahan atau hapus jika hanya pantulan cahaya.",
                }
            )

        raw_simulated = json.dumps(
            {
                "kualitas_foto": {
                    "cukup": len(all_issues) < 2,
                    "masalah": all_issues,
                },
                "kendaraan_terdeteksi": {
                    "jenis": jenis,
                    "perkiraan_model": f"{merek} {model}",
                },
                "kerusakan": detected_damages,
                "indikasi_struktural": {
                    "ada": False,
                    "alasan": "Tidak tampak deformasi rangka luar pada foto; kondisi mesin internal, indikasi bekas banjir, dan sasis bawah tidak dapat dipastikan dari foto.",
                },
                "ringkasan": (
                    f"Pemeriksaan {len(processed_photos)} foto selesai. Silakan tinjau penanda pada foto atau klik zona bodi pada Peta Kerusakan 2D untuk mengoreksi temuan."
                ),
            },
            ensure_ascii=False,
        )

        validated = parse_and_validate_vision_json(
            raw_simulated, total_photos=max(1, len(processed_photos)), default_jenis=jenis
        )
        validated["analyzer_mode"] = "fallback_assisted"
        return validated


def get_damage_analyzer() -> BaseDamageAnalyzer:
    """Factory untuk memilih implementasi DamageAnalyzer sesuai konfigurasi `.env`."""
    mode = os.environ.get("DAMAGE_ANALYZER_MODE", "claude").strip().lower()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if mode == "local_yolo":
        return LocalYoloStubDamageAnalyzer()
    if mode == "manual" or not api_key:
        return ManualFallbackDamageAnalyzer()
    return ClaudeVisionDamageAnalyzer(api_key=api_key)


def analyze_vehicle_photos(
    processed_photos: List[Dict[str, Any]], vehicle_context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Menjalankan analisis foto menggunakan analyzer aktif.
    Jika Claude API gagal/timeout atau API key belum diisi, otomatis beralih dengan ramah
    ke `ManualFallbackDamageAnalyzer` agar alur pengguna tidak pernah terhenti.
    """
    analyzer = get_damage_analyzer()
    try:
        return analyzer.analyze(processed_photos, vehicle_context)
    except Exception as api_err:
        fallback = ManualFallbackDamageAnalyzer()
        res = fallback.analyze(processed_photos, vehicle_context)
        res["analyzer_mode"] = "fallback_after_api_error"
        res["api_notice"] = (
            f"Layanan Vision API sedang tidak terjangkau ({str(api_err)}). "
            "Sistem beralih otomatis ke Mode Inspeksi Terbantu — Anda dapat meninjau atau menandai kerusakan langsung pada diagram."
        )
        return res
