/**
 * HargaBekas — Studio Ilustrasi Kendaraan 2D Vektor (SVG Inline) & Slot Foto Asli (.webp)
 *
 * Fitur Utama:
 * 1. 8 siluet bodi berbeda dengan proporsi akurat (4 Motor: Matic, Sport, Bebek, Trail;
 *    4 Mobil: Hatchback, Sedan, MPV, SUV) + kustomisasi detail per model.
 * 2. Detail realistis: velg multi-spoke, cakram rem + kaliper, bayangan lantai (ground shadow),
 *    gradasi bodi metalik berbasis CSS Variable (--vehicle-color), pantulan kaca, lampu DRL/LED.
 * 3. Dukungan 3 sudut pandang (Tampak Samping, Depan, Belakang).
 * 4. Deteksi otomatis foto asli di `/static/img/vehicles/{merek}-{model}.webp` dengan lazy loading;
 *    jika tidak tersedia, otomatis merender SVG inline berkualitas tinggi.
 */

window.HargaBekasVehicles = (function () {
  // Cache status ketersediaan file .webp agar tidak melakukan request berulang
  const photoAvailabilityCache = {};

  // Palet warna otomotif realistis yang bisa dipilih pengguna (beserta filter untuk foto studio)
  const COLOR_SWATCHES = [
    { name: "Signal Vermilion", hex: "#D9381E", filter: "none" },
    { name: "Obsidian Black", hex: "#1F2328", filter: "grayscale(0.85) contrast(1.18) brightness(0.78)" },
    { name: "Pearl White", hex: "#EAE8E1", filter: "saturate(0.18) brightness(1.14) contrast(1.05)" },
    { name: "Titanium Silver", hex: "#8C929A", filter: "grayscale(0.75) brightness(1.04) contrast(1.08)" },
    { name: "Deep Cobalt", hex: "#1D3B72", filter: "hue-rotate(205deg) saturate(1.15) brightness(0.92)" },
    { name: "British Racing Green", hex: "#1E4D3B", filter: "hue-rotate(115deg) saturate(0.95) brightness(0.88)" },
    { name: "Satin Bronze", hex: "#8A5A36", filter: "hue-rotate(28deg) saturate(0.85) brightness(0.95)" }
  ];

  function slugifyVehicle(merek, model) {
    return `${merek || ""}-${model || ""}`
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
  }

  /**
   * Membuat komponen roda mobil realistis (ban, velg alloy 10-palang, cakram rem, kaliper merah)
   */
  function renderCarWheel(cx, cy, r, uid) {
    const rimR = r * 0.68;
    const discR = r * 0.48;
    const hubR = r * 0.16;
    let spokes = "";
    for (let angle = 0; angle < 360; angle += 36) {
      spokes += `<line x1="${cx}" y1="${cy}" x2="${cx + rimR * Math.cos((angle * Math.PI) / 180)}" y2="${cy + rimR * Math.sin((angle * Math.PI) / 180)}" stroke="url(#rimGrad-${uid})" stroke-width="3.2" stroke-linecap="round"/>`;
    }
    return `
      <g class="car-wheel">
        <!-- Ban Luar -->
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="#18191C" stroke="#0D0E10" stroke-width="2"/>
        <circle cx="${cx}" cy="${cy}" r="${r * 0.88}" fill="none" stroke="#2B2E33" stroke-width="1.5" stroke-dasharray="6 4"/>
        <!-- Velg Lingkar Luar -->
        <circle cx="${cx}" cy="${cy}" r="${rimR}" fill="#1F2229" stroke="#C5CBD3" stroke-width="2.5"/>
        <!-- Cakram Rem & Kaliper -->
        <circle cx="${cx}" cy="${cy}" r="${discR}" fill="#5A6068" stroke="#3E434A" stroke-width="1.5"/>
        <path d="M ${cx - discR * 0.85} ${cy - discR * 0.5} A ${discR} ${discR} 0 0 1 ${cx - discR * 0.35} ${cy - discR * 0.92} L ${cx - discR * 0.18} ${cy - discR * 0.55} Z" fill="#D9381E"/>
        <!-- Palang Velg -->
        ${spokes}
        <!-- Center Cap -->
        <circle cx="${cx}" cy="${cy}" r="${hubR}" fill="#D8DDE4" stroke="#323740" stroke-width="2"/>
        <circle cx="${cx}" cy="${cy}" r="${hubR * 0.4}" fill="#D9381E"/>
      </g>
    `;
  }

  /**
   * Membuat komponen roda motor realistis (ban profil bulat, cakram bergelombang, velg racing Y-spoke)
   */
  function renderMotoWheel(cx, cy, r, uid, isTrail = false) {
    const rimR = r * 0.70;
    const discR = r * 0.50;
    const spokeCount = isTrail ? 18 : 6;
    const step = 360 / spokeCount;
    let spokes = "";
    for (let angle = 0; angle < 360; angle += step) {
      spokes += `<line x1="${cx}" y1="${cy}" x2="${cx + rimR * Math.cos((angle * Math.PI) / 180)}" y2="${cy + rimR * Math.sin((angle * Math.PI) / 180)}" stroke="${isTrail ? '#CBD2D9' : '#2E323B'}" stroke-width="${isTrail ? '1.3' : '4.2'}" stroke-linecap="round"/>`;
    }
    return `
      <g class="moto-wheel">
        <circle cx="${cx}" cy="${cy}" r="${r}" fill="#17181B" stroke="#0E0F12" stroke-width="${isTrail ? '4' : '2'}" ${isTrail ? 'stroke-dasharray="7 3"' : ''}/>
        <circle cx="${cx}" cy="${cy}" r="${rimR}" fill="#121316" stroke="url(#rimGrad-${uid})" stroke-width="3.5"/>
        <circle cx="${cx}" cy="${cy}" r="${discR}" fill="none" stroke="#8C939E" stroke-width="4" stroke-dasharray="8 3"/>
        <circle cx="${cx - discR * 0.55}" cy="${cy - discR * 0.3}" r="5.5" fill="#D9381E"/>
        ${spokes}
        <circle cx="${cx}" cy="${cy}" r="${r * 0.16}" fill="#AEB6C2" stroke="#1E2026" stroke-width="2"/>
      </g>
    `;
  }

  /**
   * Definisi <defs> SVG untuk gradasi bodi dinamis (--vehicle-color), kaca, krom, dan bayangan lantai
   */
  function buildSvgDefs(uid) {
    return `
      <defs>
        <!-- Gradasi Bodi Utama dengan Highlight & Shade Otomotif -->
        <linearGradient id="bodyGrad-${uid}" x1="0%" y1="0%" x2="10%" y2="100%">
          <stop offset="0%" stop-color="var(--vehicle-color, #D9381E)" stop-opacity="1"/>
          <stop offset="45%" stop-color="var(--vehicle-color, #D9381E)" stop-opacity="0.94"/>
          <stop offset="100%" stop-color="#0D0E11" stop-opacity="0.55"/>
        </linearGradient>
        <!-- Pantulan Cahaya Atas Bodi -->
        <linearGradient id="bodySpec-${uid}" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.48"/>
          <stop offset="35%" stop-color="#FFFFFF" stop-opacity="0.08"/>
          <stop offset="100%" stop-color="#000000" stop-opacity="0.32"/>
        </linearGradient>
        <!-- Gradasi Kaca Kabin -->
        <linearGradient id="glassGrad-${uid}" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#1E293B"/>
          <stop offset="50%" stop-color="#0F172A"/>
          <stop offset="100%" stop-color="#334155"/>
        </linearGradient>
        <!-- Gradasi Velg & Aksesoris Krom -->
        <linearGradient id="rimGrad-${uid}" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#F1F5F9"/>
          <stop offset="50%" stop-color="#94A3B8"/>
          <stop offset="100%" stop-color="#475569"/>
        </linearGradient>
        <!-- Bayangan Lantai Kendaraan -->
        <radialGradient id="shadowGrad-${uid}" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#000000" stop-opacity="0.48"/>
          <stop offset="65%" stop-color="#000000" stop-opacity="0.22"/>
          <stop offset="100%" stop-color="#000000" stop-opacity="0"/>
        </radialGradient>
        <!-- Pendar Lampu Depan -->
        <linearGradient id="headlightGlow-${uid}" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#FFFBEB"/>
          <stop offset="50%" stop-color="#BAE6FD"/>
          <stop offset="100%" stop-color="#38BDF8" stop-opacity="0.2"/>
        </linearGradient>
      </defs>
    `;
  }

  /**
   * 8 Siluet Tampak Samping Berbeda (4 Mobil + 4 Motor) dengan Proporsi & Detail Presisi
   */
  function renderSideGeometry(bodyType, uid, modelName = "") {
    const isNmax = modelName.toLowerCase().includes("nmax");
    const isZenix = modelName.toLowerCase().includes("zenix");

    switch (bodyType) {
      // ==================== 1. MOBIL HATCHBACK (Honda Brio RS) ====================
      case "hatchback":
        return `
          <!-- Bayangan Lantai -->
          <ellipse cx="260" cy="212" rx="185" ry="13" fill="url(#shadowGrad-${uid})"/>
          <!-- Bodi Utama Hatchback Sporty -->
          <path d="M 78 175
                   L 72 152
                   Q 73 132 95 125
                   L 152 114
                   L 215 74
                   Q 232 66 265 65
                   L 378 67
                   Q 404 69 415 88
                   L 432 128
                   Q 442 142 438 174
                   L 415 182
                   L 96 182 Z"
                fill="var(--vehicle-color, #D9381E)"/>
          <path d="M 78 175 L 72 152 Q 73 132 95 125 L 152 114 L 215 74 Q 232 66 265 65 L 378 67 Q 404 69 415 88 L 432 128 Q 442 142 438 174 L 415 182 L 96 182 Z"
                fill="url(#bodySpec-${uid})"/>
          <!-- Spoiler Atap RS -->
          <path d="M 382 67 L 424 62 L 418 76 L 392 75 Z" fill="#18191C"/>
          <!-- Kaca Samping Kabin -->
          <path d="M 164 112 L 220 77 Q 234 71 262 71 L 385 73 Q 398 75 404 92 L 412 114 Z" fill="url(#glassGrad-${uid})" stroke="#1E293B" stroke-width="2"/>
          <!-- Pilar B Hitam & Refleksi Kaca -->
          <rect x="282" y="71" width="9" height="42" fill="#111317"/>
          <path d="M 195 108 L 235 76 L 252 76 L 212 108 Z" fill="#FFFFFF" fill-opacity="0.18"/>
          <path d="M 308 110 L 342 75 L 356 75 L 322 110 Z" fill="#FFFFFF" fill-opacity="0.14"/>
          <!-- Garis Karakter Samping & Side Skirt -->
          <path d="M 92 144 L 418 134" stroke="#FFFFFF" stroke-opacity="0.35" stroke-width="2" fill="none"/>
          <path d="M 155 156 L 355 150" stroke="#000000" stroke-opacity="0.28" stroke-width="1.8" fill="none"/>
          <path d="M 150 178 L 362 178 L 358 183 L 154 183 Z" fill="#181A1F"/>
          <!-- Gagang Pintu & Spion -->
          <rect x="255" y="122" width="18" height="4.5" rx="2" fill="#1F242B"/>
          <rect x="355" y="120" width="16" height="4.5" rx="2" fill="#1F242B"/>
          <path d="M 168 108 L 185 102 L 187 115 L 170 116 Z" fill="#18191C"/>
          <!-- Lampu Depan LED Proyektor & DRL -->
          <path d="M 75 135 L 116 127 L 108 145 L 74 147 Z" fill="url(#headlightGlow-${uid})" stroke="#E2E8F0" stroke-width="1.2"/>
          <path d="M 76 146 L 109 144" stroke="#38BDF8" stroke-width="2.5" stroke-linecap="round"/>
          <!-- Lampu Belakang C-Shape -->
          <path d="M 418 105 L 434 125 L 436 145 L 416 142 Z" fill="#EF4444" stroke="#7F1D1D" stroke-width="1.2"/>
          <!-- Air Dam Bumper Depan -->
          <path d="M 73 158 L 102 156 L 98 173 L 76 173 Z" fill="#141619"/>
          <!-- Roda Depan & Belakang -->
          ${renderCarWheel(135, 180, 34, uid)}
          ${renderCarWheel(382, 180, 34, uid)}
        `;

      // ==================== 2. MOBIL SEDAN (Honda Civic RS) ====================
      case "sedan":
        return `
          <ellipse cx="260" cy="212" rx="212" ry="13" fill="url(#shadowGrad-${uid})"/>
          <!-- Bodi Fastback Sedan Rendah & Lebar -->
          <path d="M 45 174
                   L 42 148
                   Q 46 130 74 123
                   L 158 112
                   L 228 73
                   Q 255 64 295 65
                   L 382 78
                   L 448 112
                   Q 468 116 472 138
                   L 468 173
                   L 442 181
                   L 72 181 Z"
                fill="var(--vehicle-color, #D9381E)"/>
          <path d="M 45 174 L 42 148 Q 46 130 74 123 L 158 112 L 228 73 Q 255 64 295 65 L 382 78 L 448 112 Q 468 116 472 138 L 468 173 L 442 181 L 72 181 Z"
                fill="url(#bodySpec-${uid})"/>
          <!-- Ducktail Spoiler RS -->
          <path d="M 446 111 L 472 103 L 470 116 Z" fill="#16181D"/>
          <!-- Kaca Kabin Sedan -->
          <path d="M 172 110 L 234 77 Q 258 70 295 71 L 375 82 L 412 109 Z" fill="url(#glassGrad-${uid})" stroke="#CBD5E1" stroke-width="1.5"/>
          <rect x="288" y="71" width="9" height="39" fill="#121318"/>
          <path d="M 205 108 L 245 76 L 262 76 L 222 108 Z" fill="#FFFFFF" fill-opacity="0.2"/>
          <!-- Garis Bahu Tegas -->
          <path d="M 65 138 L 462 126" stroke="#FFFFFF" stroke-opacity="0.38" stroke-width="2.2"/>
          <path d="M 162 178 L 368 178 L 364 182 L 166 182 Z" fill="#14161A"/>
          <!-- Lampu Depan Laser Keen Look -->
          <path d="M 44 136 L 92 130 L 84 143 L 43 145 Z" fill="url(#headlightGlow-${uid})"/>
          <path d="M 44 145 L 86 143" stroke="#38BDF8" stroke-width="2.5"/>
          <!-- Lampu Belakang LED Bar -->
          <path d="M 446 118 L 471 124 L 469 138 L 442 135 Z" fill="#EF4444"/>
          <!-- Gagang Pintu & Spion -->
          <rect x="262" y="120" width="18" height="4" rx="2" fill="#181A20"/>
          <rect x="358" y="119" width="18" height="4" rx="2" fill="#181A20"/>
          <path d="M 176 105 L 194 99 L 195 112 L 178 113 Z" fill="#181A20"/>
          ${renderCarWheel(122, 180, 35, uid)}
          ${renderCarWheel(404, 180, 35, uid)}
        `;

      // ==================== 3. MOBIL MPV (Toyota Avanza Veloz / Innova Zenix) ====================
      case "mpv":
        return `
          <ellipse cx="260" cy="213" rx="208" ry="14" fill="url(#shadowGrad-${uid})"/>
          <!-- Bodi MPV 7-Seater Proporsional -->
          <path d="M 54 176
                   L 50 140
                   Q 53 118 82 112
                   L 148 102
                   L 208 60
                   Q 225 53 255 53
                   L 418 55
                   Q 442 57 450 78
                   L 462 128
                   Q 468 152 462 176
                   L 432 182
                   L 82 182 Z"
                fill="var(--vehicle-color, #D9381E)"/>
          <path d="M 54 176 L 50 140 Q 53 118 82 112 L 148 102 L 208 60 Q 225 53 255 53 L 418 55 Q 442 57 450 78 L 462 128 Q 468 152 462 176 L 432 182 L 82 182 Z"
                fill="url(#bodySpec-${uid})"/>
          <!-- Roof Rail & Garnish Krom Atas Kaca -->
          <path d="M 218 52 L 408 53" stroke="#CBD5E1" stroke-width="3" stroke-linecap="round"/>
          <!-- Kaca 3-Baris MPV -->
          <path d="M 162 100 L 214 63 Q 228 59 252 59 L 424 61 Q 436 63 442 82 L 448 104 Z" fill="url(#glassGrad-${uid})" stroke="#E2E8F0" stroke-width="1.5"/>
          <rect x="266" y="59" width="9" height="44" fill="#13161C"/>
          <rect x="364" y="60" width="9" height="44" fill="#13161C"/>
          <path d="M 192 98 L 228 63 L 245 63 L 208 98 Z" fill="#FFFFFF" fill-opacity="0.18"/>
          <path d="M 290 98 L 325 63 L 340 63 L 306 98 Z" fill="#FFFFFF" fill-opacity="0.14"/>
          <!-- Overfender & Cladding Samping Crossover MPV -->
          <path d="M 156 174 L 368 174 L 364 182 L 160 182 Z" fill="#191B20"/>
          <path d="M 68 128 L 448 120" stroke="#FFFFFF" stroke-opacity="0.35" stroke-width="2"/>
          ${isZenix ? '<rect x="235" y="162" width="52" height="7" rx="3" fill="#0284C7"/>' : ''}
          <!-- Lampu Depan & Belakang -->
          <path d="M 52 122 L 98 116 L 92 131 L 51 133 Z" fill="url(#headlightGlow-${uid})"/>
          <path d="M 442 104 L 461 112 L 462 128 L 440 124 Z" fill="#EF4444"/>
          <!-- Gagang Pintu -->
          <rect x="242" y="112" width="18" height="4.5" rx="2" fill="#E2E8F0"/>
          <rect x="338" y="111" width="18" height="4.5" rx="2" fill="#E2E8F0"/>
          ${renderCarWheel(124, 181, 36, uid)}
          ${renderCarWheel(400, 181, 36, uid)}
        `;

      // ==================== 4. MOBIL SUV (Toyota Fortuner VRZ) ====================
      case "suv":
        return `
          <ellipse cx="260" cy="215" rx="212" ry="15" fill="url(#shadowGrad-${uid})"/>
          <!-- Bodi SUV Gagah Ground Clearance Tinggi -->
          <path d="M 48 166
                   L 44 122
                   Q 48 102 78 96
                   L 156 88
                   L 212 46
                   Q 228 39 258 39
                   L 422 42
                   Q 445 44 454 66
                   L 466 116
                   Q 472 142 464 166
                   L 432 170
                   L 365 168
                   L 158 168
                   L 82 170 Z"
                fill="var(--vehicle-color, #D9381E)"/>
          <path d="M 48 166 L 44 122 Q 48 102 78 96 L 156 88 L 212 46 Q 228 39 258 39 L 422 42 Q 445 44 454 66 L 466 116 Q 472 142 464 166 L 432 170 L 365 168 L 158 168 L 82 170 Z"
                fill="url(#bodySpec-${uid})"/>
          <!-- Roof Rail SUV & Footstep Samping -->
          <path d="M 222 37 L 412 39" stroke="#94A3B8" stroke-width="4" stroke-linecap="round"/>
          <rect x="166" y="168" width="190" height="7" rx="3" fill="#1E2026" stroke="#64748B" stroke-width="1"/>
          <!-- Kaca Samping SUV dengan Kick-up Pillar C -->
          <path d="M 168 86 L 218 49 Q 232 45 256 45 L 428 48 Q 440 50 446 70 L 452 90 L 365 92 L 352 86 Z" fill="url(#glassGrad-${uid})" stroke="#CBD5E1" stroke-width="1.8"/>
          <rect x="272" y="45" width="10" height="42" fill="#111318"/>
          <rect x="364" y="46" width="12" height="44" fill="#111318"/>
          <!-- Overfender Hitam Maskulin -->
          <path d="M 80 170 A 48 48 0 0 1 172 170" fill="none" stroke="#181A20" stroke-width="8"/>
          <path d="M 356 170 A 48 48 0 0 1 448 170" fill="none" stroke="#181A20" stroke-width="8"/>
          <!-- Lampu Bi-Beam LED & Stop Lamp -->
          <path d="M 46 104 L 96 99 L 88 115 L 45 116 Z" fill="url(#headlightGlow-${uid})"/>
          <path d="M 446 94 L 465 100 L 466 114 L 444 111 Z" fill="#EF4444"/>
          <!-- Skid Plate Perak Depan -->
          <path d="M 46 154 L 78 152 L 72 167 L 48 167 Z" fill="#94A3B8"/>
          ${renderCarWheel(126, 176, 40, uid)}
          ${renderCarWheel(402, 176, 40, uid)}
        `;

      // ==================== 5. MOTOR MATIC (Honda Vario 160 / Yamaha NMAX 155) ====================
      case "matic":
        return `
          <ellipse cx="260" cy="212" rx="150" ry="12" fill="url(#shadowGrad-${uid})"/>
          <!-- Knalpot & CVT Box -->
          <rect x="255" y="162" width="76" height="20" rx="9" fill="#272A30" stroke="#15171A" stroke-width="2"/>
          <path d="M 315 168 L 395 146 L 402 158 L 320 176 Z" fill="#1E2026" stroke="#94A3B8" stroke-width="1.5"/>
          <!-- Roda Depan & Belakang Skutik -->
          ${renderMotoWheel(148, 174, 34, uid, false)}
          ${renderMotoWheel(362, 174, 34, uid, false)}
          <!-- Suspensi Depan Teleskopik & Shock Belakang -->
          <line x1="176" y1="112" x2="148" y2="174" stroke="#64748B" stroke-width="7" stroke-linecap="round"/>
          <line x1="342" y1="126" x2="358" y2="168" stroke="#D9381E" stroke-width="5" stroke-dasharray="4 2"/>
          <!-- Bodi Utama Skutik (Maxi NMAX vs Sporty Dek Rata Vario) -->
          <path d="${
            isNmax
              ? 'M 142 132 Q 152 88 188 74 L 212 118 L 252 132 L 285 104 L 385 96 Q 402 98 392 118 L 335 148 L 245 162 L 168 158 Z'
              : 'M 145 130 Q 158 86 190 76 L 204 128 L 248 148 L 275 102 L 386 92 Q 400 95 388 116 L 330 144 L 242 162 L 172 155 Z'
          }" fill="var(--vehicle-color, #D9381E)" stroke="#141619" stroke-width="1.5"/>
          <path d="${
            isNmax
              ? 'M 142 132 Q 152 88 188 74 L 212 118 L 252 132 L 285 104 L 385 96 Q 402 98 392 118 L 335 148 L 245 162 L 168 158 Z'
              : 'M 145 130 Q 158 86 190 76 L 204 128 L 248 148 L 275 102 L 386 92 Q 400 95 388 116 L 330 144 L 242 162 L 172 155 Z'
          }" fill="url(#bodySpec-${uid})"/>
          <!-- Windshield & Setang -->
          <path d="M 168 88 L 196 46 Q 204 42 208 54 L 190 86 Z" fill="url(#glassGrad-${uid})" stroke="#475569" stroke-width="1.5"/>
          <path d="M 192 65 L 222 60" stroke="#1E2026" stroke-width="5" stroke-linecap="round"/>
          <!-- Jok Bertingkat Ergonomis -->
          <path d="M 248 104 Q 285 104 312 92 L 378 88 Q 388 90 382 100 L 265 116 Z" fill="#181A20"/>
          <!-- Lampu Depan LED Agresif & Spakbor Depan -->
          <path d="M 146 114 L 174 106 L 168 122 L 144 124 Z" fill="url(#headlightGlow-${uid})"/>
          <path d="M 118 142 Q 146 132 168 146 L 156 154 Q 138 146 122 150 Z" fill="var(--vehicle-color, #D9381E)"/>
        `;

      // ==================== 6. MOTOR SPORT FAIRING (Honda CBR150R) ====================
      case "sport":
        return `
          <ellipse cx="260" cy="212" rx="158" ry="12" fill="url(#shadowGrad-${uid})"/>
          <!-- Swingarm & Knalpot Sport Underbelly/Upswept -->
          <path d="M 255 162 L 368 174" stroke="#334155" stroke-width="8" stroke-linecap="round"/>
          <path d="M 278 168 L 392 134 L 402 146 L 285 176 Z" fill="#1E293B" stroke="#CBD5E1" stroke-width="1.5"/>
          <!-- Roda Sport Tapak Lebar -->
          ${renderMotoWheel(144, 172, 37, uid, false)}
          ${renderMotoWheel(368, 172, 37, uid, false)}
          <!-- Upside-Down Fork Emas -->
          <line x1="182" y1="88" x2="144" y2="172" stroke="#D97706" stroke-width="7.5" stroke-linecap="round"/>
          <!-- Full Fairing Aerodinamis & Tangki Kekar -->
          <path d="M 124 122
                   L 158 76
                   L 195 72
                   L 218 88
                   Q 238 68 272 72
                   L 285 98
                   L 345 86
                   L 402 68
                   L 408 78
                   L 348 112
                   L 272 135
                   L 232 164
                   L 168 160
                   L 152 128 Z"
                fill="var(--vehicle-color, #D9381E)"/>
          <path d="M 124 122 L 158 76 L 195 72 L 218 88 Q 238 68 272 72 L 285 98 L 345 86 L 402 68 L 408 78 L 348 112 L 272 135 L 232 164 L 168 160 L 152 128 Z"
                fill="url(#bodySpec-${uid})"/>
          <!-- Visor Bubble Racing -->
          <path d="M 152 78 Q 172 52 198 56 L 192 74 Z" fill="url(#glassGrad-${uid})"/>
          <!-- Jok Split Seat Sport -->
          <path d="M 274 96 L 325 94 L 328 104 L 272 106 Z" fill="#14161B"/>
          <path d="M 342 84 L 388 72 L 390 80 L 345 92 Z" fill="#14161B"/>
          <!-- Blok Mesin DOHC Terekspos -->
          <circle cx="248" cy="146" r="18" fill="#334155" stroke="#94A3B8" stroke-width="2"/>
          <!-- Lampu Depan Dual Keen Eyes -->
          <path d="M 125 116 L 152 108 L 148 122 Z" fill="url(#headlightGlow-${uid})"/>
        `;

      // ==================== 7. MOTOR BEBEK / UNDERBONE SPORT (Yamaha MX King 150) ====================
      case "bebek":
        return `
          <ellipse cx="260" cy="212" rx="152" ry="12" fill="url(#shadowGrad-${uid})"/>
          <path d="M 255 164 L 365 172" stroke="#334155" stroke-width="7" stroke-linecap="round"/>
          <path d="M 272 168 L 396 142 L 402 154 L 278 176 Z" fill="#1F242D" stroke="#CBD5E1" stroke-width="1.5"/>
          ${renderMotoWheel(146, 172, 36, uid, false)}
          ${renderMotoWheel(366, 172, 36, uid, false)}
          <line x1="184" y1="84" x2="146" y2="172" stroke="#475569" stroke-width="6.5" stroke-linecap="round"/>
          <!-- Bodi Underbone Tajam dengan Sayap Depan -->
          <path d="M 152 94
                   L 186 58
                   L 206 62
                   L 198 92
                   L 234 122
                   L 276 96
                   L 392 78
                   L 398 90
                   L 328 122
                   L 246 154
                   L 184 148
                   L 168 112 Z"
                fill="var(--vehicle-color, #D9381E)"/>
          <path d="M 152 94 L 186 58 L 206 62 L 198 92 L 234 122 L 276 96 L 392 78 L 398 90 L 328 122 L 246 154 L 184 148 L 168 112 Z"
                fill="url(#bodySpec-${uid})"/>
          <!-- Jok Mengalir Khas Bebek Super -->
          <path d="M 262 98 L 378 80 L 382 90 L 268 110 Z" fill="#16181E"/>
          <!-- Mesin SOHC & Pelindung Bawah -->
          <circle cx="244" cy="148" r="15" fill="#475569" stroke="#1E293B" stroke-width="2"/>
          <path d="M 154 90 L 178 82 L 174 96 Z" fill="url(#headlightGlow-${uid})"/>
        `;

      // ==================== 8. MOTOR TRAIL / DUAL PURPOSE (Kawasaki KLX 150) ====================
      case "trail":
      default:
        return `
          <ellipse cx="260" cy="214" rx="152" ry="12" fill="url(#shadowGrad-${uid})"/>
          <!-- Swingarm Panjang & Roda Jari-Jari Offroad -->
          <path d="M 252 148 L 372 170" stroke="#94A3B8" stroke-width="6.5" stroke-linecap="round"/>
          ${renderMotoWheel(140, 170, 39, uid, true)}
          ${renderMotoWheel(372, 170, 37, uid, true)}
          <!-- Long-Travel Inverted Fork -->
          <line x1="188" y1="68" x2="140" y2="170" stroke="#EAB308" stroke-width="6.5" stroke-linecap="round"/>
          <!-- Spakbor Tinggi Khas Motor Trail -->
          <path d="M 112 108 Q 148 94 176 106 L 172 114 Q 144 106 116 116 Z" fill="var(--vehicle-color, #D9381E)"/>
          <!-- Shroud Tangki Tajam & Tail Tinggi -->
          <path d="M 168 88
                   L 192 64
                   L 232 82
                   L 272 86
                   L 398 68
                   L 406 78
                   L 335 106
                   L 252 118
                   L 212 134
                   L 184 108 Z"
                fill="var(--vehicle-color, #D9381E)"/>
          <path d="M 168 88 L 192 64 L 232 82 L 272 86 L 398 68 L 406 78 L 335 106 L 252 118 L 212 134 L 184 108 Z"
                fill="url(#bodySpec-${uid})"/>
          <!-- Jok Rata Panjang Motocross -->
          <path d="M 232 82 L 368 72 L 370 82 L 236 94 Z" fill="#181A20"/>
          <!-- Mesin Tinggi Ground Clearance Ekstra & Knalpot Tinggi -->
          <rect x="226" y="118" width="36" height="30" rx="5" fill="#475569" stroke="#1E293B" stroke-width="2"/>
          <path d="M 262 118 L 372 86 L 378 95 L 266 125 Z" fill="#334155"/>
        `;
    }
  }

  /**
   * Tampak Depan & Belakang Simetris Presisi (untuk Tab Sudut Pandang di Halaman Prediksi)
   */
  function renderFrontOrRearGeometry(bodyType, viewAngle, uid) {
    const isMoto = ["matic", "sport", "bebek", "trail"].includes(bodyType);
    const isRear = viewAngle === "belakang";

    if (isMoto) {
      return `
        <ellipse cx="260" cy="212" rx="68" ry="11" fill="url(#shadowGrad-${uid})"/>
        <!-- Ban Depan/Belakang Vertikal -->
        <rect x="242" y="128" width="36" height="82" rx="16" fill="#16181C" stroke="#0D0E11" stroke-width="2"/>
        <!-- Shockbreaker Kiri-Kanan -->
        <line x1="234" y1="82" x2="238" y2="168" stroke="#94A3B8" stroke-width="6" stroke-linecap="round"/>
        <line x1="286" y1="82" x2="282" y2="168" stroke="#94A3B8" stroke-width="6" stroke-linecap="round"/>
        <!-- Fairing / Tameng Depan atau Bodi Belakang -->
        <path d="M 212 72 Q 260 54 308 72 L 296 132 Q 260 144 224 132 Z" fill="var(--vehicle-color, #D9381E)"/>
        <path d="M 212 72 Q 260 54 308 72 L 296 132 Q 260 144 224 132 Z" fill="url(#bodySpec-${uid})"/>
        <!-- Windshield / Tail -->
        <path d="M 232 72 Q 260 36 288 72 Z" fill="url(#glassGrad-${uid})"/>
        <!-- Setang & Spion -->
        <line x1="186" y1="66" x2="334" y2="66" stroke="#1E2026" stroke-width="5" stroke-linecap="round"/>
        <ellipse cx="182" cy="54" rx="14" ry="8" fill="#18191C"/>
        <ellipse cx="338" cy="54" rx="14" ry="8" fill="#18191C"/>
        <!-- Lampu Utama (Putih di Depan, Merah di Belakang) -->
        <path d="M 226 96 L 254 104 L 252 116 L 222 108 Z" fill="${isRear ? '#EF4444' : 'url(#headlightGlow-' + uid + ')'}"/>
        <path d="M 294 96 L 266 104 L 268 116 L 298 108 Z" fill="${isRear ? '#EF4444' : 'url(#headlightGlow-' + uid + ')'}"/>
      `;
    }

    // Mobil Tampak Depan / Belakang
    const heightTop = bodyType === "suv" ? 48 : bodyType === "mpv" ? 56 : 68;
    return `
      <ellipse cx="260" cy="212" rx="168" ry="13" fill="url(#shadowGrad-${uid})"/>
      <!-- Ban Kiri & Kanan -->
      <rect x="108" y="148" width="38" height="62" rx="8" fill="#16181C"/>
      <rect x="374" y="148" width="38" height="62" rx="8" fill="#16181C"/>
      <!-- Bodi Utama Simetris -->
      <path d="M 102 174
               L 98 124
               Q 100 104 124 98
               L 158 ${heightTop}
               Q 260 ${heightTop - 8} 362 ${heightTop}
               L 396 98
               Q 420 104 422 124
               L 418 174 Z"
            fill="var(--vehicle-color, #D9381E)"/>
      <path d="M 102 174 L 98 124 Q 100 104 124 98 L 158 ${heightTop} Q 260 ${heightTop - 8} 362 ${heightTop} L 396 98 Q 420 104 422 124 L 418 174 Z"
            fill="url(#bodySpec-${uid})"/>
      <!-- Kaca Depan / Belakang -->
      <path d="M 142 98 L 168 ${heightTop + 8} Q 260 ${heightTop + 3} 352 ${heightTop + 8} L 378 98 Z" fill="url(#glassGrad-${uid})" stroke="#CBD5E1" stroke-width="1.5"/>
      <!-- Grille / Garnish Tengah -->
      <rect x="174" y="124" width="172" height="${isRear ? '18' : '32'}" rx="6" fill="#14161B" stroke="#64748B" stroke-width="1.5"/>
      <!-- Lampu Kiri & Kanan -->
      <path d="M 106 116 L 168 122 L 164 136 L 104 132 Z" fill="${isRear ? '#EF4444' : 'url(#headlightGlow-' + uid + ')'}"/>
      <path d="M 414 116 L 352 122 L 356 136 L 416 132 Z" fill="${isRear ? '#EF4444' : 'url(#headlightGlow-' + uid + ')'}"/>
      <!-- Plat Nomor -->
      <rect x="222" y="152" width="76" height="18" rx="3" fill="#F8FAFC" stroke="#334155" stroke-width="1.5"/>
      <text x="260" y="164" text-anchor="middle" fill="#0F172A" font-family="monospace" font-size="10" font-weight="700">B 2025 HB</text>
    `;
  }

  /**
   * Menghasilkan markup SVG inline lengkap dengan atribut aksesibilitas (role="img", aria-label)
   */
  function getVehicleSVG(options = {}) {
    const merek = options.merek || "Honda";
    const model = options.model || "Brio RS";
    const bodyType = options.bodyType || "hatchback";
    const color = options.color || "#D9381E";
    const angle = options.angle || "samping";
    const uid = Math.random().toString(36).substring(2, 9);
    const label = `Ilustrasi 2D tampak ${angle} ${merek} ${model}`;

    const geometry =
      angle === "samping"
        ? renderSideGeometry(bodyType, uid, model)
        : renderFrontOrRearGeometry(bodyType, angle, uid);

    return `
      <svg class="vehicle-svg-render"
           style="--vehicle-color: ${color};"
           viewBox="0 0 520 230"
           role="img"
           aria-label="${label}"
           xmlns="http://www.w3.org/2000/svg">
        <title>${label}</title>
        ${buildSvgDefs(uid)}
        ${geometry}
      </svg>
    `;
  }

  /**
   * Merender kendaraan ke dalam elemen DOM container:
   * Seluruh sudut pandang ("samping", "depan", "belakang") menggunakan FOTO STUDIO REAL (.webp)
   * lengkap dengan animasi transisi kamera showroom saat berganti sudut pandang.
   */
  function mountVehicleVisual(container, options = {}) {
    if (!container) return;
    const merek = options.merek || container.dataset.merek || "Honda";
    const model = options.model || container.dataset.model || "Brio RS";
    const bodyType = options.bodyType || container.dataset.bodyType || "hatchback";
    const color = options.color || container.dataset.color || "#D9381E";
    const angle = options.angle || container.dataset.angle || "samping";

    container.dataset.merek = merek;
    container.dataset.model = model;
    container.dataset.bodyType = bodyType;
    container.dataset.color = color;
    container.dataset.angle = angle;

    const slug = slugifyVehicle(merek, model);
    const suffix = angle === "samping" ? "" : `-${angle}`;
    const webpUrl = `/static/img/vehicles/${slug}${suffix}.webp`;
    const fallbackArchUrl = `/static/img/vehicles/archetype-${bodyType}${suffix}.webp`;

    const swatch = COLOR_SWATCHES.find((s) => s.hex.toLowerCase() === color.toLowerCase());
    const filterStyle = swatch && swatch.filter !== "none" ? `filter: ${swatch.filter};` : "";
    const angleLabel = angle === "depan" ? "Tampak Depan" : angle === "belakang" ? "Tampak Belakang" : "Tampak Samping";

    container.classList.add("vehicle-stage-transition");
    container.innerHTML = `
      <img src="${webpUrl}"
           alt="Foto Studio ${angleLabel} ${merek} ${model}"
           loading="lazy"
           style="${filterStyle}"
           class="vehicle-real-photo angle-anim-${angle}" />
    `;

    const imgEl = container.querySelector("img");
    if (imgEl) {
      imgEl.onerror = function () {
        if (imgEl.src.indexOf("archetype-") === -1) {
          imgEl.src = fallbackArchUrl;
        } else {
          container.innerHTML = getVehicleSVG({ merek, model, bodyType, color, angle });
        }
      };
    }
  }

  /**
   * Mengubah warna bodi secara langsung baik pada Foto Studio Real maupun SVG 2D
   */
  function updateVehicleColor(container, hexColor) {
    if (!container) return;
    container.dataset.color = hexColor;
    const svgEl = container.querySelector(".vehicle-svg-render");
    if (svgEl) {
      svgEl.style.setProperty("--vehicle-color", hexColor);
    }
    const photoEl = container.querySelector(".vehicle-real-photo");
    if (photoEl) {
      const swatch = COLOR_SWATCHES.find((s) => s.hex.toLowerCase() === hexColor.toLowerCase());
      photoEl.style.filter = swatch ? swatch.filter : "none";
    }
  }

  /**
   * Menginisialisasi seluruh elemen `.js-vehicle-visual` yang ada di halaman
   */
  function initAllVisuals(root = document) {
    const stages = root.querySelectorAll(".js-vehicle-visual");
    stages.forEach((stage) => {
      mountVehicleVisual(stage);
    });
  }

  /**
   * Merender Peta Kerusakan Interaktif (2D SVG Blueprint) untuk Mobil atau Motor.
   * Setiap zona bodi berubah warna menurut tingkat keparahan (0=Hijau, 1=Kuning, 2=Oranye, 3-4=Merah),
   * dapat di-hover untuk menyorot baris tabel, dan diklik untuk menambah/mengedit kerusakan pada bagian tersebut.
   */
  function renderInteractiveDamageMap(container, jenis = "mobil", damages = [], onPartClick = null) {
    if (!container) return;

    // Hitung keparahan tertinggi per bagian
    const partSeverity = {};
    (damages || []).forEach((d) => {
      const p = d.bagian;
      const s = parseInt(d.keparahan, 10) || 1;
      if (!partSeverity[p] || s > partSeverity[p]) {
        partSeverity[p] = s;
      }
    });

    function zoneAttrs(partKey, label) {
      const sev = partSeverity[partKey] || 0;
      return `class="damage-map-zone sev-${sev}" data-part="${partKey}" data-label="${label}" tabindex="0" role="button" aria-label="Zona ${label} (Keparahan ${sev})"`;
    }

    if (jenis === "motor") {
      container.innerHTML = `
        <svg viewBox="0 0 540 240" class="damage-map-svg" xmlns="http://www.w3.org/2000/svg">
          <title>Peta Zona Kerusakan Sepeda Motor</title>
          <!-- Garis Grid Teknis -->
          <line x1="20" y1="205" x2="520" y2="205" stroke="var(--border-subtle)" stroke-dasharray="4 4"/>
          <!-- Velg & Ban Depan/Belakang -->
          <g ${zoneAttrs("velg_ban", "Velg & Kaki-kaki")}>
            <circle cx="128" cy="166" r="38"/>
            <circle cx="402" cy="166" r="38"/>
          </g>
          <!-- Spakbor Depan -->
          <path ${zoneAttrs("fender_depan", "Spakbor Depan")} d="M 88 128 Q 126 112 162 132 L 152 144 Q 124 130 94 140 Z"/>
          <!-- Lampu Depan & Visor -->
          <path ${zoneAttrs("lampu_depan", "Lampu Depan")} d="M 134 86 L 176 68 L 184 96 L 140 108 Z"/>
          <!-- Spion -->
          <path ${zoneAttrs("spion", "Spion Motor")} d="M 182 42 L 204 34 L 208 50 L 186 56 Z"/>
          <!-- Tangki / Dek Tengah -->
          <path ${zoneAttrs("tangki_motor", "Tangki / Dek Tengah")} d="M 188 86 L 265 76 L 272 126 L 196 134 Z"/>
          <!-- Cover Body / Fairing Samping -->
          <path ${zoneAttrs("cover_body", "Cover Body / Fairing")} d="M 152 106 L 202 98 L 258 126 L 372 98 L 386 122 L 265 156 L 168 148 Z"/>
          <!-- Jok Motor -->
          <path ${zoneAttrs("jok_interior", "Jok Motor")} d="M 264 78 L 378 68 L 384 88 L 268 102 Z"/>
          <!-- Knalpot -->
          <path ${zoneAttrs("knalpot", "Knalpot")} d="M 296 156 L 434 132 L 442 148 L 302 170 Z"/>
          <!-- Lampu Belakang & Tail -->
          <path ${zoneAttrs("lampu_belakang", "Lampu Belakang")} d="M 382 72 L 424 76 L 418 96 L 380 94 Z"/>
          <!-- Rangka / Sasis Bawah -->
          <rect ${zoneAttrs("rangka_sasis", "Struktur Rangka / Sasis")} x="208" y="158" width="90" height="16" rx="4"/>
        </svg>
      `;
    } else {
      container.innerHTML = `
        <svg viewBox="0 0 560 250" class="damage-map-svg" xmlns="http://www.w3.org/2000/svg">
          <title>Peta Zona Kerusakan Mobil (Tampak Samping & Atas)</title>
          <line x1="20" y1="212" x2="540" y2="212" stroke="var(--border-subtle)" stroke-dasharray="4 4"/>
          <!-- Velg & Ban -->
          <g ${zoneAttrs("velg_ban", "Velg & Ban")}>
            <circle cx="136" cy="176" r="36"/>
            <circle cx="422" cy="176" r="36"/>
          </g>
          <!-- Bumper Depan -->
          <path ${zoneAttrs("bumper_depan", "Bumper Depan")} d="M 42 136 L 86 132 L 88 178 L 44 176 Z"/>
          <!-- Lampu Depan -->
          <path ${zoneAttrs("lampu_depan", "Lampu Depan")} d="M 48 112 L 96 106 L 92 128 L 46 130 Z"/>
          <!-- Kap Mesin -->
          <path ${zoneAttrs("kap_mesin", "Kap Mesin")} d="M 64 104 L 166 90 L 172 114 L 88 126 Z"/>
          <!-- Fender Depan -->
          <path ${zoneAttrs("fender_depan", "Fender Depan")} d="M 88 118 L 182 112 L 182 172 L 88 172 Z"/>
          <!-- Kaca Depan & Samping -->
          <path ${zoneAttrs("kaca_mobil", "Kaca Kabin")} d="M 168 88 L 228 50 L 386 52 L 426 88 Z"/>
          <!-- Atap Kabin -->
          <path ${zoneAttrs("atap_kabin", "Atap Kabin")} d="M 222 36 L 392 38 L 388 50 L 226 48 Z"/>
          <!-- Spion -->
          <rect ${zoneAttrs("spion", "Spion Samping")} x="176" y="88" width="24" height="16" rx="4"/>
          <!-- Pintu Samping Kiri / Depan -->
          <rect ${zoneAttrs("pintu_kiri", "Pintu Samping Kiri")} x="186" y="92" width="102" height="78" rx="3"/>
          <!-- Pintu Samping Kanan / Belakang -->
          <rect ${zoneAttrs("pintu_kanan", "Pintu Samping Kanan")} x="292" y="92" width="98" height="78" rx="3"/>
          <!-- Fender Belakang -->
          <path ${zoneAttrs("fender_belakang", "Fender Belakang")} d="M 394 92 L 466 96 L 466 172 L 394 172 Z"/>
          <!-- Pintu Bagasi / Tailgate -->
          <path ${zoneAttrs("bagasi_pintu_belakang", "Pintu Bagasi")} d="M 430 62 L 478 96 L 478 134 L 456 134 Z"/>
          <!-- Lampu Belakang -->
          <rect ${zoneAttrs("lampu_belakang", "Lampu Belakang")} x="466" y="102" width="28" height="26" rx="3"/>
          <!-- Bumper Belakang -->
          <path ${zoneAttrs("bumper_belakang", "Bumper Belakang")} d="M 468 134 L 508 136 L 504 178 L 466 176 Z"/>
          <!-- Struktur Rangka / Sasis Bawah -->
          <rect ${zoneAttrs("rangka_sasis", "Struktur Rangka / Sasis")} x="184" y="175" width="204" height="14" rx="3"/>
        </svg>
      `;
    }

    container.querySelectorAll(".damage-map-zone").forEach((zone) => {
      zone.addEventListener("click", () => {
        const partKey = zone.dataset.part;
        if (typeof onPartClick === "function") {
          onPartClick(partKey, zone.dataset.label);
        }
      });
    });
  }

  return {
    COLOR_SWATCHES,
    getVehicleSVG,
    mountVehicleVisual,
    updateVehicleColor,
    initAllVisuals,
    renderInteractiveDamageMap,
    slugifyVehicle
  };
})();
