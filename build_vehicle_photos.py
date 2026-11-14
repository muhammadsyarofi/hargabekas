"""
Script Pembuat Aset Foto Studio Kendaraan Realistis (.webp) untuk 3 Sudut Pandang:
- Tampak Samping: /static/img/vehicles/{merek}-{model}.webp
- Tampak Depan  : /static/img/vehicles/{merek}-{model}-depan.webp
- Tampak Belakang: /static/img/vehicles/{merek}-{model}-belakang.webp

Mengolah 12 foto studio fotorealistis resolusi tinggi (1024x1024) menjadi 177 file .webp
untuk seluruh 47 model mobil dan motor di katalog HargaBekas.
"""

import os
import re
from PIL import Image, ImageDraw, ImageEnhance, ImageFont
from generate_dataset import VEHICLE_CATALOG

ARTIFACT_DIR = r"C:\Users\lenovo\.gemini\antigravity\brain\a921ae6b-f194-4c6e-9509-8f24a6c9a6ba"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "static", "img", "vehicles")

SOURCE_PHOTOS = {
    "hatchback": os.path.join(ARTIFACT_DIR, "archetype_hatchback_1794671063294.jpg"),
    "sedan": os.path.join(ARTIFACT_DIR, "archetype_sedan_1794671085669.jpg"),
    "mpv": os.path.join(ARTIFACT_DIR, "archetype_mpv_1794671103208.jpg"),
    "suv": os.path.join(ARTIFACT_DIR, "archetype_suv_1794671123092.jpg"),
    "crossover": os.path.join(ARTIFACT_DIR, "crossover_suv_profile_png_1794671194280.jpg"),
    "ev": os.path.join(ARTIFACT_DIR, "electric_crossover_profile_png_1794671213505.jpg"),
    "exec_sedan": os.path.join(ARTIFACT_DIR, "executive_sedan_profile_png_1794671233200.jpg"),
    "matic": os.path.join(ARTIFACT_DIR, "archetype_matic_1794671108341.jpg"),
    "nmax": os.path.join(ARTIFACT_DIR, "yamaha_nmax_155_src_1794684878338.jpg"),
    "retro_matic": os.path.join(ARTIFACT_DIR, "retro_modern_scooter_profile_png_1794671257054.jpg"),
    "sport": os.path.join(ARTIFACT_DIR, "archetype_sport_1794671128382.jpg"),
    "bebek": os.path.join(ARTIFACT_DIR, "archetype_bebek_1794671180180.jpg"),
    "trail": os.path.join(ARTIFACT_DIR, "archetype_trail_1794671199810.jpg"),
}


def slugify(merek: str, model: str) -> str:
    raw = f"{merek}-{model}".lower()
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", raw))


def choose_archetype(item: dict) -> str:
    merek = item["merek"].lower()
    model = item["model"].lower()
    btype = item["body_type"]
    bbm = " ".join(item["bbm_opts"]).lower()

    if "nmax" in model or "aerox" in model:
        return "nmax"
    if "vespa" in merek or "pcx" in model:
        return "retro_matic"
    if btype in ("matic", "sport", "bebek", "trail"):
        return btype
    if "listrik" in bbm or "ioniq" in model or "air ev" in model or "atto" in model:
        return "ev"
    if merek in ("bmw", "mercedes-benz") or "camry" in model or "seal" in model:
        return "exec_sedan"
    if btype == "suv" and any(k in model for k in ("hr-v", "cr-v", "xforce", "creta", "almaz", "cx-5")):
        return "crossover"
    return btype


def apply_brand_livery(img: Image.Image, merek: str, model: str) -> Image.Image:
    """
    Menyesuaikan warna khas pabrikan (livery) pada piksel bodi kendaraan
    tanpa mengubah latar belakang studio netral (#F5F2EB).
    """
    import numpy as np

    m = merek.lower()
    mod = model.lower()

    # Tentukan target hue/tint berdasarkan merek pabrikan di Indonesia
    if "kawasaki" in m:
        # Kawasaki Lime Green khas Ninja / KLX
        tint_mode = "green"
    elif "yamaha" in m and ("r15" in mod or "mx king" in mod):
        # Yamaha Racing Blue
        tint_mode = "blue"
    elif "suzuki" in m and ("gsx" in mod or "satria" in mod or "baleno" in mod):
        # Suzuki Ecstar Blue
        tint_mode = "blue"
    elif "bmw" in m or "byd" in m:
        tint_mode = "cobalt"
    elif "mercedes" in m or "nissan" in m or "daihatsu" in m:
        tint_mode = "silver"
    elif "mitsubishi" in m or "toyota" in m:
        if "fortuner" in mod or "pajero" in mod or "camry" in mod:
            tint_mode = "obsidian"
        elif "avanza" in mod or "innova" in mod or "xpander" in mod:
            tint_mode = "silver"
        else:
            return img
    else:
        return img

    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

    # Deteksi piksel berwarna (bodi merah/oranye/kuning/biru) agar latar belakang abu/krem tidak ikut berubah
    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    chroma = max_c - min_c
    is_colored_body = chroma > 28.0

    if tint_mode == "green":
        nr = r * 0.38
        ng = np.clip(r * 0.92 + 30.0, 0, 255)
        nb = b * 0.35
    elif tint_mode == "blue":
        nr = r * 0.25
        ng = g * 0.72 + 25.0
        nb = np.clip(r * 0.95 + 35.0, 0, 255)
    elif tint_mode == "cobalt":
        nr = r * 0.22
        ng = g * 0.55 + 15.0
        nb = np.clip(r * 0.85 + 25.0, 0, 255)
    elif tint_mode == "silver":
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        nr = np.clip(lum * 1.06, 0, 255)
        ng = np.clip(lum * 1.06, 0, 255)
        nb = np.clip(lum * 1.08, 0, 255)
    elif tint_mode == "obsidian":
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        nr = np.clip(lum * 0.42, 0, 255)
        ng = np.clip(lum * 0.43, 0, 255)
        nb = np.clip(lum * 0.46, 0, 255)
    else:
        return img

    out = arr.copy()
    out[:, :, 0] = np.where(is_colored_body, nr, r)
    out[:, :, 1] = np.where(is_colored_body, ng, g)
    out[:, :, 2] = np.where(is_colored_body, nb, b)
    return Image.fromarray(out.astype(np.uint8), mode="RGB")


def crop_angle_view(img: Image.Image, angle: str) -> Image.Image:
    """
    Membuat framing kamera studio realistis dari foto beresolusi tinggi (1024x1024):
    - 'samping' : Full wide shot kendaraan utuh (tampak samping penuh)
    - 'depan'   : Fokus kamera showroom pada bagian fascia depan, lampu utama, kap/visor & roda depan
    - 'belakang': Fokus kamera showroom pada bagian buritan belakang, stop lamp, knalpot/diffuser & roda belakang
    """
    img = img.convert("RGB")
    w, h = img.size

    if angle == "samping":
        target_ratio = 16 / 9.2
        new_h = int(w / target_ratio)
        top = int((h - new_h) * 0.52) if new_h < h else 0
        cropped = img.crop((0, top, w, min(h, top + new_h)))
        return cropped.resize((840, 480), Image.Resampling.LANCZOS)

    if angle == "depan":
        # Kendaraan menghadap ke kiri -> bagian depan berada di sisi kiri-tengah (x: 2% s/d 64%, y: 24% s/d 84%)
        left = int(w * 0.02)
        right = int(w * 0.64)
        top = int(h * 0.25)
        bottom = int(h * 0.83)
        cropped = img.crop((left, top, right, bottom))
        return cropped.resize((840, 480), Image.Resampling.LANCZOS)

    # angle == "belakang"
    # Bagian belakang berada di sisi kanan-tengah (x: 36% s/d 98%, y: 24% s/d 84%)
    left = int(w * 0.36)
    right = int(w * 0.98)
    top = int(h * 0.24)
    bottom = int(h * 0.83)
    cropped = img.crop((left, top, right, bottom))
    return cropped.resize((840, 480), Image.Resampling.LANCZOS)


def add_showroom_badge(img: Image.Image, merek: str, model: str, angle: str) -> Image.Image:
    """Menambahkan ketajaman kontras studio dan badge sudut pandang pada foto."""
    enhancer_contrast = ImageEnhance.Contrast(img)
    img = enhancer_contrast.enhance(1.04)

    draw = ImageDraw.Draw(img, "RGBA")
    angle_tag = {
        "samping": "TAMPAK SAMPING",
        "depan": "DETAIL DEPAN",
        "belakang": "DETAIL BELAKANG",
    }.get(angle, "STUDIO")
    badge_text = f"{angle_tag}  •  {merek.upper()} {model.upper()}"

    try:
        font = ImageFont.truetype("arialbd.ttf", 14)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), badge_text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad_x, pad_y = 14, 8
    bx1 = 840 - tw - (pad_x * 2) - 18
    by1 = 480 - th - (pad_y * 2) - 16
    bx2 = 840 - 18
    by2 = 480 - 16

    draw.rounded_rectangle([bx1, by1, bx2, by2], radius=5, fill=(18, 18, 16, 210))
    draw.rectangle([bx1, by1, bx1 + 4, by2], fill=(217, 56, 30, 255))
    draw.text((bx1 + pad_x + 2, by1 + pad_y - 1), badge_text, fill=(245, 242, 235, 255), font=font)
    return img


def build_all_photos():
    os.makedirs(OUT_DIR, exist_ok=True)
    angles = ["samping", "depan", "belakang"]

    # 1. Simpan foto archetype untuk 3 sudut pandang
    for arch_name, src_path in SOURCE_PHOTOS.items():
        if not os.path.exists(src_path):
            continue
        with Image.open(src_path) as im:
            for angle in angles:
                view_im = crop_angle_view(im, angle)
                suffix = "" if angle == "samping" else f"-{angle}"
                out_arch = os.path.join(OUT_DIR, f"archetype-{arch_name}{suffix}.webp")
                view_im.save(out_arch, "WEBP", quality=84, method=4)

    # 2. Buat foto .webp 3 sudut pandang (samping, depan, belakang) untuk seluruh 47 model
    created_files = 0
    for item in VEHICLE_CATALOG:
        arch = choose_archetype(item)
        src_path = SOURCE_PHOTOS.get(arch, SOURCE_PHOTOS["hatchback"])
        if not os.path.exists(src_path):
            continue
        slug = slugify(item["merek"], item["model"])
        with Image.open(src_path) as im:
            livery_im = apply_brand_livery(im, item["merek"], item["model"])
            for angle in angles:
                view_im = crop_angle_view(livery_im, angle)
                badged_im = add_showroom_badge(view_im, item["merek"], item["model"], angle)
                suffix = "" if angle == "samping" else f"-{angle}"
                out_path = os.path.join(OUT_DIR, f"{slug}{suffix}.webp")
                badged_im.save(out_path, "WEBP", quality=82, method=4)
                created_files += 1

    print(f"[HargaBekas] Berhasil membuat {created_files} file foto studio 3-sudut (.webp) di {OUT_DIR}")


if __name__ == "__main__":
    build_all_photos()
