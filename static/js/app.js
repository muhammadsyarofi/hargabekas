/**
 * HargaBekas — Controller Frontend Murni (Vanilla JS + Chart.js)
 * Mengelola:
 * 1. Stepper 5 Langkah: Data Unit -> Unggah & Kompresi Foto -> Analisis AI -> Tinjau & Koreksi Temuan -> Hasil Waterfall
 * 2. Sinkronisasi Dua Arah: Penanda BBox di Foto <-> Baris Tabel Inspeksi <-> Peta Kerusakan SVG 2D
 * 3. Kalkulasi Real-Time saat pengguna mengubah tingkat keparahan (1-4), menghapus, atau menambah kerusakan
 * 4. Grafik Waterfall Pembentukan Harga & Perbandingan "Jual Apa Adanya" vs "Perbaiki Dulu"
 * 5. Pembanding 2-3 Unit + Biaya Perbaikan & Simulasi Kredit dengan Peringatan Leasing
 */

(function () {
  "use strict";

  const STORAGE_LAST_PRED = "hb_last_prediction_v2";
  const STORAGE_THEME = "hb_theme_v1";

  function formatRupiah(val) {
    const num = Math.round(Number(val) || 0);
    const sign = num < 0 ? "- " : "";
    return sign + "Rp " + Math.abs(num).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function formatRibuan(val) {
    const num = Math.round(Number(val) || 0);
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function showToast(message) {
    let toast = document.getElementById("hb-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "hb-toast";
      toast.className = "toast-notification";
      toast.setAttribute("role", "status");
      toast.setAttribute("aria-live", "polite");
      document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.classList.add("show");
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => {
      toast.classList.remove("show");
    }, 3400);
  }

  function animateCountUp(el, targetValue, duration = 750) {
    if (!el) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const target = Math.round(Number(targetValue) || 0);
    if (reducedMotion) {
      el.textContent = formatRupiah(target);
      return;
    }
    const startTime = performance.now();
    function step(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = Math.round(target * eased);
      el.textContent = formatRupiah(current);
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.textContent = formatRupiah(target);
      }
    }
    requestAnimationFrame(step);
  }

  // ==================== 1. TEMA TERANG / GELAP ====================
  function initTheme() {
    const saved = localStorage.getItem(STORAGE_THEME);
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const initialTheme = saved || (prefersDark ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", initialTheme);
    updateThemeButtonLabel(initialTheme);

    const toggleBtn = document.getElementById("theme-toggle");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
        const next = current === "dark" ? "light" : "dark";
        document.documentElement.setAttribute("data-theme", next);
        localStorage.setItem(STORAGE_THEME, next);
        updateThemeButtonLabel(next);
      });
    }
  }

  function updateThemeButtonLabel(theme) {
    const labelEl = document.getElementById("theme-toggle-label");
    if (labelEl) {
      labelEl.textContent = theme === "dark" ? "Mode Terang" : "Mode Gelap";
    }
  }

  // ==================== 2. KOMPRESI GAMBAR DI SISI KLIEN (MAKS 1600PX) ====================
  function compressImageClientSide(file, maxDim = 1600, quality = 0.82) {
    return new Promise((resolve, reject) => {
      if (!file.type.match(/^image\/(jpeg|png|webp)$/)) {
        reject(new Error(`Format file '${file.name}' tidak didukung. Gunakan JPEG, PNG, atau WebP.`));
        return;
      }
      if (file.size > 15 * 1024 * 1024) {
        reject(new Error(`Ukuran file '${file.name}' terlalu besar (>15 MB).`));
        return;
      }

      const reader = new FileReader();
      reader.onerror = () => reject(new Error("Gagal membaca file gambar."));
      reader.onload = (ev) => {
        const img = new Image();
        img.onerror = () => reject(new Error("File bukan gambar yang valid."));
        img.onload = () => {
          let w = img.width;
          let h = img.height;
          if (Math.max(w, h) > maxDim) {
            const scale = maxDim / Math.max(w, h);
            w = Math.round(w * scale);
            h = Math.round(h * scale);
          }
          const canvas = document.createElement("canvas");
          canvas.width = w;
          canvas.height = h;
          const ctx = canvas.getContext("2d");
          ctx.drawImage(img, 0, 0, w, h);
          const dataUrl = canvas.toDataURL("image/jpeg", quality);
          resolve({ dataUrl, width: w, height: h, origName: file.name });
        };
        img.src = ev.target.result;
      };
      reader.readAsDataURL(file);
    });
  }

  // ==================== 3. HALAMAN PREDIKSI 5 LANGKAH (INSPEKSI FOTO & VALUASI) ====================
  function initPrediksiPage() {
    const stepperForm = document.getElementById("stepper-predict-form");
    if (!stepperForm) return;

    const catalog = window.HB_CATALOG || [];
    const repairTable = window.HB_REPAIR_TABLE || { parts: {}, damage_types: {}, severity_multipliers: {} };

    let currentStep = 1;
    let selectedColor = "#D9381E";
    let currentAngle = "samping";

    // State Foto & Temuan Kerusakan
    let stagedPhotos = []; // [{ slot, data_url, server_url, width, height }]
    let currentDamages = []; // [{ bagian, jenis, keparahan, perkiraan_luas_persen, bbox, foto_ke, keyakinan, catatan }]
    let kualitasFotoState = { cukup: true, masalah: [] };
    let indikasiStrukturalState = { ada: false, alasan: "" };
    let activeBboxPhotoIndex = 1;
    let lastPredictionResult = null;
    let waterfallChartInstance = null;

    const SLOTS_MOBIL = [
      { key: "depan", label: "1. Tampak Depan" },
      { key: "belakang", label: "2. Tampak Belakang" },
      { key: "samping_kiri", label: "3. Samping Kiri" },
      { key: "samping_kanan", label: "4. Samping Kanan" },
      { key: "interior", label: "5. Kabin Interior" },
      { key: "dashboard", label: "6. Odometer / Dashboard" },
      { key: "closeup", label: "7. Close-up Kerusakan" }
    ];

    const SLOTS_MOTOR = [
      { key: "samping_kiri", label: "1. Samping Kiri" },
      { key: "samping_kanan", label: "2. Samping Kanan" },
      { key: "depan", label: "3. Tampak Depan" },
      { key: "belakang", label: "4. Tampak Belakang" },
      { key: "speedometer", label: "5. Panel Speedometer" },
      { key: "closeup", label: "6. Close-up Kerusakan" }
    ];

    // Elemen DOM
    const errBanner = document.getElementById("pred-error-banner");
    const stageEl = document.getElementById("pred-vehicle-stage");
    const stageTitleEl = document.getElementById("pred-stage-title");
    const stageSubEl = document.getElementById("pred-stage-subtitle");
    const mapHolderEl = document.getElementById("interactive-damage-map-holder");

    const merekSelect = document.getElementById("pred-merek");
    const modelSelect = document.getElementById("pred-model");
    const transmisiSelect = document.getElementById("pred-transmisi");
    const bbmSelect = document.getElementById("pred-bbm");
    const tahunSlider = document.getElementById("pred-tahun");
    const tahunValEl = document.getElementById("pred-tahun-val");
    const kmNumber = document.getElementById("pred-kilometer-num");
    const suratSelect = document.getElementById("pred-surat");
    const kotaSelect = document.getElementById("pred-kota");
    const structuralCheckbox = document.getElementById("structural-flag-checkbox");

    function showError(msg) {
      if (!errBanner) return;
      if (!msg) {
        errBanner.classList.remove("visible");
        errBanner.textContent = "";
      } else {
        errBanner.textContent = msg;
        errBanner.classList.add("visible");
      }
    }

    function getSelectedJenis() {
      const checked = document.querySelector('input[name="jenis"]:checked');
      return checked ? checked.value : "mobil";
    }

    function getCurrentCatalogItem() {
      const jenis = getSelectedJenis();
      const merek = merekSelect.value;
      const model = modelSelect.value;
      return (
        catalog.find((c) => c.jenis === jenis && c.merek === merek && c.model === model) ||
        catalog.find((c) => c.jenis === jenis) ||
        catalog[0]
      );
    }

    function populateDamageDropdowns() {
      const jenis = getSelectedJenis();
      const partSelect = document.getElementById("add-dmg-part");
      const typeSelect = document.getElementById("add-dmg-type");
      if (partSelect && repairTable.parts) {
        partSelect.innerHTML = "";
        Object.entries(repairTable.parts).forEach(([key, info]) => {
          if (!info.applicable_to || info.applicable_to.includes(jenis)) {
            const opt = document.createElement("option");
            opt.value = key;
            opt.textContent = info.label;
            partSelect.appendChild(opt);
          }
        });
      }
      if (typeSelect && repairTable.damage_types) {
        typeSelect.innerHTML = "";
        Object.entries(repairTable.damage_types).forEach(([key, info]) => {
          const opt = document.createElement("option");
          opt.value = key;
          opt.textContent = info.label;
          typeSelect.appendChild(opt);
        });
      }
    }

    function renderSlotGuides() {
      const jenis = getSelectedJenis();
      const slots = jenis === "motor" ? SLOTS_MOTOR : SLOTS_MOBIL;
      const guideEl = document.getElementById("photo-slot-guides");
      const activeSlotSelect = document.getElementById("active-photo-slot");

      const filledSlots = new Set(stagedPhotos.map((p) => p.slot));

      if (guideEl) {
        guideEl.innerHTML = slots
          .map((s) => {
            const isFilled = filledSlots.has(s.key);
            return `
              <div class="slot-guide-item ${isFilled ? "filled" : ""}">
                <span>${s.label}</span>
                <span class="mono-label">${isFilled ? "✓ Ada" : "Kosong"}</span>
              </div>
            `;
          })
          .join("");
      }

      if (activeSlotSelect) {
        const prevVal = activeSlotSelect.value;
        activeSlotSelect.innerHTML = slots
          .map((s) => `<option value="${s.key}">${s.label}</option>`)
          .join("");
        if (prevVal && slots.some((s) => s.key === prevVal)) {
          activeSlotSelect.value = prevVal;
        }
      }
    }

    function updateBrandsForJenis() {
      const jenis = getSelectedJenis();
      const brands = [...new Set(catalog.filter((c) => c.jenis === jenis).map((c) => c.merek))];
      merekSelect.innerHTML = "";
      brands.forEach((b) => {
        const opt = document.createElement("option");
        opt.value = b;
        opt.textContent = b;
        merekSelect.appendChild(opt);
      });
      populateDamageDropdowns();
      renderSlotGuides();
      updateModelsForBrand();
    }

    function updateModelsForBrand() {
      const jenis = getSelectedJenis();
      const merek = merekSelect.value;
      const models = catalog.filter((c) => c.jenis === jenis && c.merek === merek);
      modelSelect.innerHTML = "";
      models.forEach((m) => {
        const opt = document.createElement("option");
        opt.value = m.model;
        opt.textContent = m.model;
        modelSelect.appendChild(opt);
      });
      updateSpecsForModel();
    }

    function updateSpecsForModel() {
      const item = getCurrentCatalogItem();
      if (!item) return;

      transmisiSelect.innerHTML = "";
      item.transmisi_opts.forEach((t) => {
        const opt = document.createElement("option");
        opt.value = t;
        opt.textContent = t;
        transmisiSelect.appendChild(opt);
      });

      bbmSelect.innerHTML = "";
      item.bbm_opts.forEach((b) => {
        const opt = document.createElement("option");
        opt.value = b;
        opt.textContent = b;
        bbmSelect.appendChild(opt);
      });

      refreshStudioAndMap();
    }

    function refreshStudioAndMap() {
      const item = getCurrentCatalogItem();
      if (!item) return;
      stageTitleEl.textContent = `${item.merek} ${item.model}`;
      stageSubEl.textContent = `${item.body_type.toUpperCase()} • Tahun ${tahunSlider.value} • ${formatRibuan(kmNumber.value)} km`;

      window.HargaBekasVehicles.mountVehicleVisual(stageEl, {
        merek: item.merek,
        model: item.model,
        bodyType: item.body_type,
        color: selectedColor,
        angle: currentAngle
      });

      window.HargaBekasVehicles.renderInteractiveDamageMap(
        mapHolderEl,
        item.jenis,
        currentDamages,
        (clickedPartKey, clickedPartLabel) => {
          // Siklus klik zona bodi: Hijau (Normal) -> Lv.1 -> Lv.2 -> Lv.3 -> Lv.4 -> kembali ke Hijau (Baik-baik saja)
          const existingIdx = currentDamages.findIndex((d) => d.bagian === clickedPartKey);
          if (existingIdx !== -1) {
            const currentSev = parseInt(currentDamages[existingIdx].keparahan, 10) || 1;
            if (currentSev >= 4) {
              // Mentok level 4 -> kembalikan ke hijau / kondisi baik (hapus semua temuan pada bagian ini)
              currentDamages = currentDamages.filter((d) => d.bagian !== clickedPartKey);
              showToast(`${clickedPartLabel} dikembalikan ke kondisi baik (Hijau).`);
            } else {
              currentDamages[existingIdx].keparahan = currentSev + 1;
              showToast(`Keparahan ${clickedPartLabel} dinaikkan ke Lv.${currentDamages[existingIdx].keparahan}.`);
            }
          } else {
            currentDamages.push({
              bagian: clickedPartKey,
              jenis: "lecet_ringan",
              keparahan: 1,
              perkiraan_luas_persen: 20,
              bbox: [0.3, 0.42, 0.26, 0.2],
              foto_ke: activeBboxPhotoIndex || 1,
              keyakinan: 1.0,
              catatan: `Ditambahkan manual lewat klik peta 2D (${clickedPartLabel}).`
            });
            showToast(`Titik kerusakan ${clickedPartLabel} ditambahkan (Lv.1 Minor).`);
          }
          renderReviewStepUI();
          recalculateValuationRealTime();
        }
      );
    }

    // Kontrol Perbesar / Zoom Peta Zona Bodi 2D agar sesuai dengan ukuran kerusakan pada foto
    const mapPanelEl = document.getElementById("damage-map-panel");
    const btnToggleMapExpand = document.getElementById("btn-toggle-map-expand");
    const mapZoomRange = document.getElementById("damage-map-zoom-range");
    const mapZoomValEl = document.getElementById("damage-map-zoom-val");
    if (mapZoomRange && mapHolderEl) {
      mapZoomRange.addEventListener("input", () => {
        const scale = (parseInt(mapZoomRange.value, 10) || 100) / 100;
        mapHolderEl.style.setProperty("--damage-map-scale", String(scale));
        if (mapZoomValEl) mapZoomValEl.textContent = `${mapZoomRange.value}%`;
      });
    }
    if (btnToggleMapExpand && mapPanelEl) {
      btnToggleMapExpand.addEventListener("click", () => {
        const expanded = mapPanelEl.classList.toggle("damage-map-expanded");
        btnToggleMapExpand.textContent = expanded ? "Kecilkan Peta" : "Perbesar Peta";
        if (expanded && mapZoomRange && parseInt(mapZoomRange.value, 10) < 125) {
          mapZoomRange.value = "135";
          mapZoomRange.dispatchEvent(new Event("input"));
        } else if (!expanded && mapZoomRange) {
          mapZoomRange.value = "100";
          mapZoomRange.dispatchEvent(new Event("input"));
        }
      });
    }

    // Navigasi Stepper 1..5
    function goToStep(stepNumber) {
      showError("");
      currentStep = Math.max(1, Math.min(5, stepNumber));
      document.querySelectorAll(".step-pane").forEach((pane) => {
        pane.classList.toggle("active", parseInt(pane.dataset.step, 10) === currentStep);
      });
      document.querySelectorAll(".step-indicator").forEach((ind) => {
        const s = parseInt(ind.dataset.stepTarget, 10);
        ind.classList.toggle("active", s === currentStep);
        ind.classList.toggle("completed", s < currentStep);
      });
    }

    document.querySelectorAll("[data-next-step]").forEach((btn) => {
      btn.addEventListener("click", () => goToStep(parseInt(btn.dataset.nextStep, 10)));
    });
    document.querySelectorAll("[data-prev-step]").forEach((btn) => {
      btn.addEventListener("click", () => goToStep(parseInt(btn.dataset.prevStep, 10)));
    });
    document.querySelectorAll(".step-indicator").forEach((ind) => {
      ind.addEventListener("click", () => {
        const target = parseInt(ind.dataset.stepTarget, 10);
        if (target === 4) {
          renderReviewStepUI();
          recalculateValuationRealTime();
        } else if (target === 5) {
          recalculateValuationRealTime(true);
        }
        goToStep(target);
      });
    });

    // Event Listener Spesifikasi Dasar
    document.querySelectorAll(".js-jenis-tile").forEach((tile) => {
      tile.addEventListener("click", () => {
        document.querySelectorAll(".js-jenis-tile").forEach((t) => t.classList.remove("selected"));
        tile.classList.add("selected");
        const radio = tile.querySelector('input[type="radio"]');
        if (radio) {
          radio.checked = true;
          currentDamages = [];
          updateBrandsForJenis();
        }
      });
    });

    merekSelect.addEventListener("change", updateModelsForBrand);
    modelSelect.addEventListener("change", updateSpecsForModel);
    tahunSlider.addEventListener("input", () => {
      tahunValEl.textContent = tahunSlider.value;
      refreshStudioAndMap();
    });
    kmNumber.addEventListener("input", refreshStudioAndMap);

    // Swatch Warna & Tab Sudut Pandang
    const swatchContainer = document.getElementById("pred-color-swatches");
    if (swatchContainer && window.HargaBekasVehicles) {
      window.HargaBekasVehicles.COLOR_SWATCHES.forEach((sw, idx) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "color-swatch" + (idx === 0 ? " active" : "");
        btn.style.backgroundColor = sw.hex;
        btn.title = sw.name;
        btn.addEventListener("click", () => {
          swatchContainer.querySelectorAll(".color-swatch").forEach((b) => b.classList.remove("active"));
          btn.classList.add("active");
          selectedColor = sw.hex;
          document.getElementById("pred-color-name").textContent = sw.name;
          window.HargaBekasVehicles.updateVehicleColor(stageEl, selectedColor);
        });
        swatchContainer.appendChild(btn);
      });
    }

    document.querySelectorAll(".angle-tab-btn").forEach((tab) => {
      tab.addEventListener("click", () => {
        document.querySelectorAll(".angle-tab-btn").forEach((t) => t.classList.remove("active"));
        tab.classList.add("active");
        currentAngle = tab.dataset.angle || "samping";
        refreshStudioAndMap();
      });
    });

    // ==================== LANGKAH 2: UNGGAH & KOMPRESI FOTO ====================
    const dropzone = document.getElementById("photo-dropzone");
    const fileInput = document.getElementById("photo-file-input");
    const cameraInput = document.getElementById("photo-camera-input");
    const thumbsGrid = document.getElementById("uploaded-thumbs-grid");
    const progWrap = document.getElementById("upload-progress-bar-wrap");
    const progFill = document.getElementById("upload-progress-fill");
    const progPct = document.getElementById("upload-progress-pct");

    function renderStagedThumbnails() {
      if (!thumbsGrid) return;
      thumbsGrid.innerHTML = stagedPhotos
        .map(
          (p, i) => `
          <div style="border: 1px solid var(--border-subtle); border-radius: 4px; overflow: hidden; background: var(--bg-page); position: relative;">
            <img src="${p.server_url || p.data_url}" alt="Foto ${i + 1}" style="width: 100%; height: 82px; object-fit: cover;" />
            <div style="padding: 0.3rem 0.45rem; font-size: 0.72rem; display: flex; justify-content: space-between; align-items: center;">
              <span class="mono-label">${p.slot.replace("_", " ")}</span>
              <button type="button" class="js-remove-staged-photo" data-idx="${i}" style="border:none;background:none;color:var(--accent);cursor:pointer;font-weight:700;">✕</button>
            </div>
          </div>
        `
        )
        .join("");

      thumbsGrid.querySelectorAll(".js-remove-staged-photo").forEach((btn) => {
        btn.addEventListener("click", () => {
          stagedPhotos.splice(parseInt(btn.dataset.idx, 10), 1);
          renderStagedThumbnails();
          renderSlotGuides();
        });
      });
      renderSlotGuides();
    }

    async function handleFilesSelected(fileList) {
      showError("");
      const files = Array.from(fileList || []);
      if (!files.length) return;
      if (stagedPhotos.length + files.length > 10) {
        showError("Maksimal 10 foto yang dapat diunggah dalam satu sesi inspeksi.");
        return;
      }

      progWrap.style.display = "block";
      const slotSelect = document.getElementById("active-photo-slot");
      const jenis = getSelectedJenis();
      const slotList = jenis === "motor" ? SLOTS_MOTOR : SLOTS_MOBIL;

      for (let i = 0; i < files.length; i++) {
        const pct = Math.round(((i + 0.5) / files.length) * 100);
        progFill.style.width = `${pct}%`;
        progPct.textContent = `${pct}%`;
        try {
          const compressed = await compressImageClientSide(files[i]);
          const chosenSlot =
            i === 0 && slotSelect
              ? slotSelect.value
              : slotList[(stagedPhotos.length) % slotList.length].key;

          stagedPhotos.push({
            slot: chosenSlot,
            data_url: compressed.dataUrl,
            width: compressed.width,
            height: compressed.height
          });
        } catch (err) {
          showError(err.message);
        }
      }
      progFill.style.width = "100%";
      progPct.textContent = "100%";
      setTimeout(() => {
        progWrap.style.display = "none";
      }, 500);
      renderStagedThumbnails();
    }

    if (dropzone && fileInput) {
      dropzone.addEventListener("click", () => fileInput.click());
      dropzone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropzone.classList.add("dragover");
      });
      dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
      dropzone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropzone.classList.remove("dragover");
        handleFilesSelected(e.dataTransfer.files);
      });
      fileInput.addEventListener("change", () => handleFilesSelected(fileInput.files));
    }
    if (cameraInput) {
      cameraInput.addEventListener("change", () => handleFilesSelected(cameraInput.files));
    }

    // Tombol Muat Contoh Foto Inspeksi (Mengambil foto studio kendaraan yang dipilih ke canvas)
    const demoPhotoBtn = document.getElementById("btn-load-demo-photo");
    if (demoPhotoBtn) {
      demoPhotoBtn.addEventListener("click", async () => {
        const item = getCurrentCatalogItem();
        const slug = window.HargaBekasVehicles.slugifyVehicle(item.merek, item.model);
        const angles = [
          { url: `/static/img/vehicles/${slug}.webp`, slot: "samping_kiri" },
          { url: `/static/img/vehicles/${slug}-depan.webp`, slot: "depan" }
        ];
        stagedPhotos = [];
        for (const a of angles) {
          try {
            const resp = await fetch(a.url);
            const blob = await resp.blob();
            const file = new File([blob], `${slug}-${a.slot}.webp`, { type: "image/webp" });
            const comp = await compressImageClientSide(file);
            stagedPhotos.push({
              slot: a.slot,
              data_url: comp.dataUrl,
              server_url: a.url,
              width: comp.width,
              height: comp.height
            });
          } catch (e) {
            // ignore
          }
        }
        renderStagedThumbnails();
        showToast(`2 foto contoh ${item.merek} ${item.model} siap dianalisis.`);
      });
    }

    // Tombol Lewati ke Mode Manual
    const skipManualBtn = document.getElementById("btn-skip-to-manual");
    if (skipManualBtn) {
      skipManualBtn.addEventListener("click", () => {
        const jenis = getSelectedJenis();
        currentDamages =
          jenis === "motor"
            ? [
                {
                  bagian: "cover_body",
                  jenis: "lecet_ringan",
                  keparahan: 1,
                  perkiraan_luas_persen: 15,
                  bbox: [0.34, 0.42, 0.26, 0.22],
                  foto_ke: 1,
                  keyakinan: 1.0,
                  catatan: "Contoh temuan awal — silakan koreksi atau klik Peta 2D di sebelah kanan."
                }
              ]
            : [
                {
                  bagian: "bumper_depan",
                  jenis: "goresan_dalam",
                  keparahan: 2,
                  perkiraan_luas_persen: 20,
                  bbox: [0.22, 0.54, 0.26, 0.18],
                  foto_ke: 1,
                  keyakinan: 1.0,
                  catatan: "Contoh temuan awal — silakan koreksi atau klik Peta 2D di sebelah kanan."
                }
              ];
        document.getElementById("analyzer-mode-badge").textContent = "Mode Manual Interaktif";
        renderReviewStepUI();
        recalculateValuationRealTime();
        goToStep(4);
      });
    }

    // ==================== LANGKAH 3: JALANKAN ANALISIS FOTO KE BACKEND ====================
    const runAnalysisBtn = document.getElementById("btn-run-photo-analysis");
    if (runAnalysisBtn) {
      runAnalysisBtn.addEventListener("click", async () => {
        if (stagedPhotos.length === 0) {
          showError("Silakan unggah minimal 1 foto kendaraan, klik 'Gunakan Contoh Foto Inspeksi', atau pilih 'Mode Manual'.");
          return;
        }
        goToStep(3);
        const stageEls = document.querySelectorAll("#analysis-stages-list .analysis-stage-item");
        stageEls.forEach((el) => el.classList.remove("running", "done"));

        function setStageState(stageNum) {
          stageEls.forEach((el) => {
            const s = parseInt(el.dataset.stage, 10);
            el.classList.toggle("done", s < stageNum);
            el.classList.toggle("running", s === stageNum);
          });
        }

        setStageState(1);
        setTimeout(() => setStageState(2), 420);

        try {
          const res = await fetch("/api/analyze-photos", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              jenis: getSelectedJenis(),
              merek: merekSelect.value,
              model: modelSelect.value,
              tahun: parseInt(tahunSlider.value, 10),
              photos: stagedPhotos.map((p) => ({ slot: p.slot, data_url: p.data_url }))
            })
          });
          setStageState(3);
          const json = await res.json();
          if (json.status !== "ok") {
            goToStep(2);
            showError(json.message || "Gagal menganalisis foto.");
            return;
          }

          // Simpan URL server untuk setiap foto yang sudah di-strip EXIF-nya
          if (json.photos && json.photos.length) {
            json.photos.forEach((srvPhoto, idx) => {
              if (stagedPhotos[idx]) {
                stagedPhotos[idx].server_url = srvPhoto.url;
              }
            });
          }

          const analysis = json.analysis;
          currentDamages = analysis.kerusakan || [];
          kualitasFotoState = analysis.kualitas_foto || { cukup: true, masalah: [] };
          indikasiStrukturalState = analysis.indikasi_struktural || { ada: false, alasan: "" };

          const modeBadge = document.getElementById("analyzer-mode-badge");
          if (modeBadge) {
            modeBadge.textContent =
              analysis.analyzer_mode === "claude_vision_api"
                ? "Claude Vision AI"
                : "Inspeksi Terbantu + Peta 2D";
          }

          const summaryEl = document.getElementById("inspection-summary-text");
          if (summaryEl) {
            summaryEl.textContent = analysis.api_notice
              ? `${analysis.api_notice} ${analysis.ringkasan}`
              : analysis.ringkasan;
          }

          setTimeout(() => {
            renderReviewStepUI();
            recalculateValuationRealTime();
            goToStep(4);
          }, 450);
        } catch (err) {
          goToStep(2);
          showError("Gagal menghubungi server analisis foto. Silakan gunakan Mode Manual.");
        }
      });
    }

    // ==================== LANGKAH 4: TINJAU & KOREKSI TEMUAN ====================
    function renderReviewStepUI() {
      // Peringatan kualitas foto jika ada
      const qWarn = document.getElementById("photo-quality-warning");
      if (qWarn) {
        if (kualitasFotoState.masalah && kualitasFotoState.masalah.length > 0) {
          qWarn.textContent = "Catatan Kualitas Foto: " + kualitasFotoState.masalah.join(" • ");
          qWarn.classList.add("visible");
        } else {
          qWarn.classList.remove("visible");
        }
      }

      if (structuralCheckbox) {
        structuralCheckbox.checked = Boolean(indikasiStrukturalState.ada);
      }
      const structReasonEl = document.getElementById("structural-reason-note");
      if (structReasonEl && indikasiStrukturalState.alasan) {
        structReasonEl.textContent = indikasiStrukturalState.alasan;
      }

      // Render Foto dengan Overlay BBox
      const bboxSection = document.getElementById("bbox-viewer-section");
      const bboxStage = document.getElementById("bbox-photo-stage");
      const bboxSwitcher = document.getElementById("bbox-photo-switcher");

      if (stagedPhotos.length > 0 && bboxSection && bboxStage) {
        bboxSection.style.display = "block";
        if (activeBboxPhotoIndex > stagedPhotos.length) activeBboxPhotoIndex = 1;

        bboxSwitcher.innerHTML = stagedPhotos
          .map(
            (p, idx) => `
            <button type="button" class="angle-tab-btn ${idx + 1 === activeBboxPhotoIndex ? "active" : ""}" data-photo-idx="${idx + 1}">
              Foto #${idx + 1} (${p.slot.replace("_", " ")})
            </button>
          `
          )
          .join("");

        bboxSwitcher.querySelectorAll("[data-photo-idx]").forEach((btn) => {
          btn.addEventListener("click", () => {
            activeBboxPhotoIndex = parseInt(btn.dataset.photoIdx, 10);
            renderReviewStepUI();
          });
        });

        const currentPhoto = stagedPhotos[activeBboxPhotoIndex - 1];
        const imgSrc = currentPhoto.server_url || currentPhoto.data_url;
        let markersHtml = "";

        currentDamages.forEach((d, idx) => {
          const fotoKe = parseInt(d.foto_ke, 10) || 1;
          if (fotoKe === activeBboxPhotoIndex) {
            const [bx, by, bw, bh] = d.bbox || [0.25, 0.4, 0.25, 0.2];
            const partLabel = repairTable.parts[d.bagian] ? repairTable.parts[d.bagian].label : d.bagian;
            const luasPct = d.perkiraan_luas_persen || Math.min(100, Math.max(5, Math.round(bw * bh * 260)));
            markersHtml += `
              <div class="damage-bbox-marker"
                   data-dmg-idx="${idx}"
                   style="left:${bx * 100}%; top:${by * 100}%; width:${bw * 100}%; height:${bh * 100}%;"
                   title="#${idx + 1} ${partLabel} — Geser atau tarik sudut untuk ubah ukuran">
                <span class="damage-bbox-badge">${idx + 1}</span>
                <span class="bbox-size-pill">Luas ~${luasPct}%</span>
                <span class="bbox-resize-handle handle-ne" data-dir="ne" title="Perbesar/perkecil sudut kanan atas"></span>
                <span class="bbox-resize-handle handle-sw" data-dir="sw" title="Perbesar/perkecil sudut kiri bawah"></span>
                <span class="bbox-resize-handle handle-se" data-dir="se" title="Perbesar/perkecil sudut kanan bawah"></span>
              </div>
            `;
          }
        });

        bboxStage.innerHTML = `<div class="bbox-img-wrap"><img src="${imgSrc}" alt="Foto Inspeksi #${activeBboxPhotoIndex}" />${markersHtml}</div>`;

        // Interaksi Drag (pindah) & Resize (perbesar/perkecil) kotak BBox langsung di atas foto
        const imgWrap = bboxStage.querySelector(".bbox-img-wrap");
        if (imgWrap) {
          imgWrap.querySelectorAll(".damage-bbox-marker").forEach((marker) => {
            marker.addEventListener("pointerdown", (e) => {
              const handleEl = e.target.closest(".bbox-resize-handle");
              const mode = handleEl ? handleEl.dataset.dir : "move";
              const dmgIdx = parseInt(marker.dataset.dmgIdx, 10);
              const dmg = currentDamages[dmgIdx];
              if (!dmg) return;

              e.preventDefault();
              e.stopPropagation();
              marker.classList.add("is-manipulating");

              const wrapRect = imgWrap.getBoundingClientRect();
              const startX = e.clientX;
              const startY = e.clientY;
              const orig = [...(dmg.bbox || [0.25, 0.4, 0.25, 0.2])];
              const minSize = 0.06;

              function onPointerMove(ev) {
                if (!wrapRect.width || !wrapRect.height) return;
                const dx = (ev.clientX - startX) / wrapRect.width;
                const dy = (ev.clientY - startY) / wrapRect.height;

                let [nx, ny, nw, nh] = orig;
                if (mode === "move") {
                  nx = Math.max(0, Math.min(1 - nw, orig[0] + dx));
                  ny = Math.max(0, Math.min(1 - nh, orig[1] + dy));
                } else if (mode === "se") {
                  nw = Math.max(minSize, Math.min(1 - nx, orig[2] + dx));
                  nh = Math.max(minSize, Math.min(1 - ny, orig[3] + dy));
                } else if (mode === "ne") {
                  nw = Math.max(minSize, Math.min(1 - nx, orig[2] + dx));
                  const maxTop = orig[1] + orig[3] - minSize;
                  ny = Math.max(0, Math.min(maxTop, orig[1] + dy));
                  nh = orig[1] + orig[3] - ny;
                } else if (mode === "sw") {
                  const maxLeft = orig[0] + orig[2] - minSize;
                  nx = Math.max(0, Math.min(maxLeft, orig[0] + dx));
                  nw = orig[0] + orig[2] - nx;
                  nh = Math.max(minSize, Math.min(1 - ny, orig[3] + dy));
                }

                dmg.bbox = [
                  Number(nx.toFixed(3)),
                  Number(ny.toFixed(3)),
                  Number(nw.toFixed(3)),
                  Number(nh.toFixed(3))
                ];
                const estLuas = Math.min(100, Math.max(5, Math.round(nw * nh * 260)));
                dmg.perkiraan_luas_persen = estLuas;

                marker.style.left = `${nx * 100}%`;
                marker.style.top = `${ny * 100}%`;
                marker.style.width = `${nw * 100}%`;
                marker.style.height = `${nh * 100}%`;
                const pill = marker.querySelector(".bbox-size-pill");
                if (pill) pill.textContent = `Luas ~${estLuas}%`;
              }

              function onPointerUp() {
                marker.classList.remove("is-manipulating");
                window.removeEventListener("pointermove", onPointerMove);
                window.removeEventListener("pointerup", onPointerUp);
                recalculateValuationRealTime();
              }

              window.addEventListener("pointermove", onPointerMove);
              window.addEventListener("pointerup", onPointerUp);
            });
          });
        }
      } else if (bboxSection) {
        bboxSection.style.display = "none";
      }

      // Render Tabel Temuan Kerusakan
      const tbody = document.getElementById("findings-table-body");
      if (tbody) {
        if (currentDamages.length === 0) {
          tbody.innerHTML = `
            <tr>
              <td colspan="6" style="text-align:center; padding: 1.25rem; color: var(--positive); font-weight: 600;">
                ✓ Tidak ada titik kerusakan bodi yang dicatat (Unit dinilai dalam Kondisi Standar Normal).
              </td>
            </tr>
          `;
        } else {
          tbody.innerHTML = currentDamages
            .map((d, idx) => {
              const partLabel = repairTable.parts[d.bagian] ? repairTable.parts[d.bagian].label : d.bagian;
              const typeLabel = repairTable.damage_types[d.jenis] ? repairTable.damage_types[d.jenis].label : d.jenis;
              const confPct = Math.round((d.keyakinan || 0.85) * 100);
              const costEst = d._calculated_cost || 0;
              return `
                <tr class="inspection-row" data-row-idx="${idx}" data-part="${d.bagian}">
                  <td>
                    <span class="severity-badge sev-${d.keparahan}" style="margin-right:0.35rem;">#${idx + 1}</span>
                    <strong>${partLabel}</strong>
                  </td>
                  <td>${typeLabel}</td>
                  <td>
                    <input type="range" class="range-slider js-row-sev-slider" data-idx="${idx}" min="1" max="4" step="1" value="${d.keparahan}" style="width:75px;vertical-align:middle;" aria-label="Ubah Keparahan ${partLabel}" />
                    <span class="severity-badge sev-${d.keparahan}">Lv.${d.keparahan}</span>
                  </td>
                  <td><span class="mono-label">${confPct}%</span></td>
                  <td style="color: var(--accent); font-weight: 700;">- ${formatRupiah(costEst)}</td>
                  <td>
                    <button type="button" class="btn btn-outline js-delete-dmg-row" data-idx="${idx}" style="min-height:30px;padding:0.2rem 0.55rem;font-size:0.75rem;">
                      Hapus
                    </button>
                  </td>
                </tr>
              `;
            })
            .join("");
        }

        // Event listener geser slider keparahan & hapus baris
        tbody.querySelectorAll(".js-row-sev-slider").forEach((slider) => {
          slider.addEventListener("input", () => {
            const idx = parseInt(slider.dataset.idx, 10);
            currentDamages[idx].keparahan = parseInt(slider.value, 10);
            recalculateValuationRealTime();
          });
        });

        tbody.querySelectorAll(".js-delete-dmg-row").forEach((btn) => {
          btn.addEventListener("click", () => {
            const idx = parseInt(btn.dataset.idx, 10);
            currentDamages.splice(idx, 1);
            renderReviewStepUI();
            recalculateValuationRealTime();
          });
        });

        // Mikro-interaksi: Hover baris tabel menyorot BBox di foto & zona di Peta SVG 2D
        tbody.querySelectorAll(".inspection-row").forEach((row) => {
          row.addEventListener("mouseenter", () => {
            const idx = row.dataset.rowIdx;
            const part = row.dataset.part;
            document.querySelectorAll(`.damage-bbox-marker[data-dmg-idx="${idx}"]`).forEach((m) => m.classList.add("active"));
            document.querySelectorAll(`.damage-map-zone[data-part="${part}"]`).forEach((z) => z.classList.add("active-zone"));
          });
          row.addEventListener("mouseleave", () => {
            document.querySelectorAll(".damage-bbox-marker.active").forEach((m) => m.classList.remove("active"));
            document.querySelectorAll(".damage-map-zone.active-zone").forEach((z) => z.classList.remove("active-zone"));
          });
        });
      }

      // Hover penanda BBox di foto menyorot baris daftar
      document.querySelectorAll(".damage-bbox-marker").forEach((marker) => {
        marker.addEventListener("mouseenter", () => {
          const idx = marker.dataset.dmgIdx;
          const row = document.querySelector(`.inspection-row[data-row-idx="${idx}"]`);
          if (row) row.classList.add("highlighted");
        });
        marker.addEventListener("mouseleave", () => {
          document.querySelectorAll(".inspection-row.highlighted").forEach((r) => r.classList.remove("highlighted"));
        });
      });

      refreshStudioAndMap();
    }

    // Tombol Tambah Kerusakan Manual dari Form Kecil
    const addDmgBtn = document.getElementById("btn-add-damage-row");
    if (addDmgBtn) {
      addDmgBtn.addEventListener("click", () => {
        const part = document.getElementById("add-dmg-part").value;
        const type = document.getElementById("add-dmg-type").value;
        const sev = parseInt(document.getElementById("add-dmg-sev").value, 10) || 2;
        currentDamages.push({
          bagian: part,
          jenis: type,
          keparahan: sev,
          perkiraan_luas_persen: 20,
          bbox: [0.28 + (currentDamages.length % 4) * 0.1, 0.4, 0.24, 0.2],
          foto_ke: activeBboxPhotoIndex || 1,
          keyakinan: 1.0,
          catatan: "Ditambahkan manual oleh pengguna."
        });
        renderReviewStepUI();
        recalculateValuationRealTime();
      });
    }

    if (structuralCheckbox) {
      structuralCheckbox.addEventListener("change", () => {
        indikasiStrukturalState.ada = structuralCheckbox.checked;
        recalculateValuationRealTime();
      });
    }

    document.querySelectorAll(".js-kondisi-detail").forEach((cb) => {
      cb.addEventListener("change", () => recalculateValuationRealTime());
    });

    // Fungsi Kalkulasi Harga Real-Time ke `/api/predict`
    async function recalculateValuationRealTime(renderFinalCharts = false) {
      const checkedDetails = Array.from(document.querySelectorAll(".js-kondisi-detail:checked")).map(
        (cb) => cb.value
      );
      const photoUrls = stagedPhotos.map((p) => p.server_url).filter(Boolean);

      const payload = {
        jenis: getSelectedJenis(),
        merek: merekSelect.value,
        model: modelSelect.value,
        tahun: parseInt(tahunSlider.value, 10),
        kilometer: parseInt(kmNumber.value, 10),
        transmisi: transmisiSelect.value,
        bahan_bakar: bbmSelect.value,
        kondisi: 4,
        kondisi_detail: checkedDetails,
        surat: suratSelect ? suratSelect.value : "Lengkap (STNK + BPKB + Faktur)",
        kota: kotaSelect.value,
        warna: selectedColor,
        kerusakan: currentDamages,
        indikasi_struktural: indikasiStrukturalState,
        kualitas_foto: kualitasFotoState,
        photos: photoUrls
      };

      try {
        const res = await fetch("/api/predict", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status !== "ok") return;

        lastPredictionResult = json.data;
        localStorage.setItem(STORAGE_LAST_PRED, JSON.stringify(lastPredictionResult));

        // Sinkronkan estimasi biaya per item kembali ke tabel review
        if (lastPredictionResult.itemized_repairs) {
          lastPredictionResult.itemized_repairs.forEach((rep, i) => {
            if (currentDamages[i]) {
              currentDamages[i]._calculated_cost = rep.estimasi_biaya;
            }
          });
        }

        // Update banner ringkas di Langkah 4
        const livePriceEl = document.getElementById("live-review-price");
        const liveBaseEl = document.getElementById("live-review-base");
        const liveDeductEl = document.getElementById("live-review-deduct");
        if (livePriceEl) livePriceEl.textContent = formatRupiah(lastPredictionResult.harga_estimasi);
        if (liveBaseEl) liveBaseEl.textContent = formatRupiah(lastPredictionResult.harga_dasar_normal);
        if (liveDeductEl) {
          const totCut = lastPredictionResult.estimasi_biaya_perbaikan + lastPredictionResult.diskon_pasar_rp;
          liveDeductEl.textContent = "- " + formatRupiah(totCut);
        }

        renderReviewStepUI();
        if (renderFinalCharts || currentStep === 5) {
          renderStep5WaterfallAndResults(lastPredictionResult);
        }
      } catch (e) {
        // ignore transient network errors
      }
    }

    const finalizeBtn = document.getElementById("btn-finalize-valuation");
    if (finalizeBtn) {
      finalizeBtn.addEventListener("click", async () => {
        await recalculateValuationRealTime(true);
        goToStep(5);
      });
    }

    function renderStep5WaterfallAndResults(data) {
      animateCountUp(document.getElementById("res-main-price"), data.harga_estimasi, 850);
      document.getElementById("res-min-price").textContent = formatRupiah(data.harga_min);
      document.getElementById("res-normal-price").textContent = formatRupiah(data.harga_dasar_normal);
      document.getElementById("res-max-price").textContent = formatRupiah(data.harga_max);
      document.getElementById("res-confidence").textContent = `${data.confidence}% Keyakinan Keseluruhan`;

      // Perbandingan Keputusan: Jual Apa Adanya vs Perbaiki Dulu
      const dec = data.perbandingan_keputusan;
      if (dec) {
        document.getElementById("dec-asis-price").textContent = formatRupiah(dec.harga_jual_apa_adanya);
        document.getElementById("dec-repaired-price").textContent = formatRupiah(dec.harga_jika_diperbaiki);
        document.getElementById("dec-repaired-net").textContent =
          `Setelah dikurangi modal bengkel ${formatRupiah(dec.estimasi_biaya_perbaikan)}, nilai bersih yang diterima adalah ${formatRupiah(dec.nilai_bersih_jika_diperbaiki)}.`;
        document.getElementById("dec-recommendation-box").textContent = dec.rekomendasi;
      }

      // Render Daftar Faktor
      const factorsContainer = document.getElementById("res-factors-list");
      if (factorsContainer) {
        factorsContainer.innerHTML = data.factors
          .map((f) => {
            const sign = f.impact_pct > 0 ? "+" : "";
            return `
              <div class="factor-item">
                <div class="factor-header">
                  <strong>${f.factor} — <span style="font-weight:500;color:var(--text-secondary)">${f.label}</span></strong>
                  <span class="badge-impact ${f.direction}">${sign}${f.impact_pct}%</span>
                </div>
                <p style="font-size:0.84rem;color:var(--text-secondary)">${f.explanation}</p>
              </div>
            `;
          })
          .join("");
      }

      // Render Grafik Waterfall dengan Chart.js (Floating Bars)
      const ctx = document.getElementById("waterfall-chart");
      if (ctx && window.Chart) {
        if (waterfallChartInstance) waterfallChartInstance.destroy();

        const steps = data.waterfall_steps || [];
        const labels = [];
        const floatingData = [];
        const bgColors = [];

        let runningTotal = 0;
        steps.forEach((st) => {
          labels.push(st.label);
          if (st.type === "base") {
            floatingData.push([0, st.amount]);
            runningTotal = st.amount;
            bgColors.push("#1D3B72");
          } else if (st.type === "final") {
            floatingData.push([0, st.amount]);
            bgColors.push("#156C43");
          } else {
            const nextTotal = runningTotal + st.amount;
            floatingData.push([nextTotal, runningTotal]);
            runningTotal = nextTotal;
            bgColors.push("#D9381E");
          }
        });

        waterfallChartInstance = new Chart(ctx, {
          type: "bar",
          data: {
            labels,
            datasets: [
              {
                label: "Rincian Pembentukan Harga (Rp)",
                data: floatingData,
                backgroundColor: bgColors,
                borderRadius: 4
              }
            ]
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  label: (context) => {
                    const raw = context.raw;
                    if (Array.isArray(raw)) {
                      const diff = raw[1] - raw[0];
                      return formatRupiah(diff);
                    }
                    return formatRupiah(context.parsed.y);
                  }
                }
              }
            },
            scales: {
              y: {
                ticks: {
                  callback: (val) => "Rp " + Math.round(val / 1000000) + " Jt"
                }
              }
            }
          }
        });
      }
    }

    // Simpan ke Riwayat & Bagikan
    const saveHistoryBtn = document.getElementById("btn-save-history");
    if (saveHistoryBtn) {
      saveHistoryBtn.addEventListener("click", async () => {
        if (!lastPredictionResult) return;
        const payload = { ...lastPredictionResult.input, save_to_history: true };
        const res = await fetch("/api/predict", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === "ok") {
          showToast("Laporan inspeksi & valuasi disimpan ke Riwayat!");
        }
      });
    }

    const shareBtn = document.getElementById("btn-share-result");
    if (shareBtn) {
      shareBtn.addEventListener("click", async () => {
        if (!lastPredictionResult) return;
        const inp = lastPredictionResult.input;
        const text = `Laporan Inspeksi HargaBekas: ${inp.merek} ${inp.model} (${inp.tahun}, ${formatRibuan(inp.kilometer)} km, ${inp.kota}) -> Harga Normal: ${formatRupiah(lastPredictionResult.harga_dasar_normal)} | Potongan Perbaikan (${lastPredictionResult.itemized_repairs.length} titik): -${formatRupiah(lastPredictionResult.estimasi_biaya_perbaikan)} | Diskon Pasar: -${formatRupiah(lastPredictionResult.diskon_pasar_rp)} | Estimasi Harga Akhir: ${formatRupiah(lastPredictionResult.harga_estimasi)}.`;
        if (navigator.clipboard) {
          await navigator.clipboard.writeText(text);
          showToast("Ringkasan laporan inspeksi disalin ke clipboard!");
        } else {
          showToast(text);
        }
      });
    }

    updateBrandsForJenis();
  }

  // ==================== 4. HALAMAN PEMBANDING (DENGAN TEMUAN KERUSAKAN) ====================
  function initComparePage() {
    const compareForm = document.getElementById("compare-form");
    if (!compareForm) return;

    const catalog = window.HB_CATALOG || [];
    let thirdSlotActive = false;
    let compareChartInstance = null;
    let currentChartType = "radar";
    let lastCompareData = null;

    const toggleSlot3Btn = document.getElementById("btn-toggle-slot3");
    const slot3Card = document.getElementById("compare-slot-3");

    function getDamagesFromPreset(preset, jenis) {
      const isMoto = jenis === "motor";
      if (preset === "none") return { damages: [], structural: false };
      if (preset === "minor") {
        return {
          damages: isMoto
            ? [{ bagian: "cover_body", jenis: "lecet_ringan", keparahan: 1, perkiraan_luas_persen: 15 }]
            : [
                { bagian: "bumper_depan", jenis: "lecet_ringan", keparahan: 1, perkiraan_luas_persen: 15 },
                { bagian: "pintu_kiri", jenis: "lecet_ringan", keparahan: 1, perkiraan_luas_persen: 10 }
              ],
          structural: false
        };
      }
      if (preset === "moderate") {
        return {
          damages: isMoto
            ? [
                { bagian: "cover_body", jenis: "goresan_dalam", keparahan: 2, perkiraan_luas_persen: 25 },
                { bagian: "knalpot", jenis: "penyok", keparahan: 2, perkiraan_luas_persen: 20 }
              ]
            : [
                { bagian: "pintu_kiri", jenis: "penyok", keparahan: 2, perkiraan_luas_persen: 25 },
                { bagian: "fender_depan", jenis: "goresan_dalam", keparahan: 2, perkiraan_luas_persen: 20 },
                { bagian: "spion", jenis: "retak", keparahan: 2, perkiraan_luas_persen: 30 }
              ],
          structural: false
        };
      }
      // heavy
      return {
        damages: isMoto
          ? [
              { bagian: "fender_depan", jenis: "pecah", keparahan: 3, perkiraan_luas_persen: 50 },
              { bagian: "rangka_sasis", jenis: "penyok", keparahan: 4, perkiraan_luas_persen: 30 }
            ]
          : [
              { bagian: "bumper_depan", jenis: "pecah", keparahan: 3, perkiraan_luas_persen: 60 },
              { bagian: "kap_mesin", jenis: "penyok", keparahan: 3, perkiraan_luas_persen: 40 },
              { bagian: "rangka_sasis", jenis: "penyok", keparahan: 4, perkiraan_luas_persen: 25 }
            ],
        structural: true
      };
    }

    function initSlotSelectors(slotIndex) {
      const modelSel = document.getElementById(`cmp-model-${slotIndex}`);
      const stageEl = document.getElementById(`cmp-stage-${slotIndex}`);
      if (!modelSel) return;

      modelSel.innerHTML = "";
      catalog.forEach((item, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        opt.textContent = `${item.jenis.toUpperCase()} — ${item.merek} ${item.model}`;
        modelSel.appendChild(opt);
      });

      const defaultIdx = slotIndex === 1 ? 6 : slotIndex === 2 ? 0 : 15;
      modelSel.value = Math.min(defaultIdx, catalog.length - 1);

      function updateSlotVisual() {
        const item = catalog[parseInt(modelSel.value, 10)] || catalog[0];
        window.HargaBekasVehicles.mountVehicleVisual(stageEl, {
          merek: item.merek,
          model: item.model,
          bodyType: item.body_type,
          color: "#D9381E",
          angle: "samping"
        });
      }

      modelSel.addEventListener("change", updateSlotVisual);
      updateSlotVisual();
    }

    [1, 2, 3].forEach(initSlotSelectors);

    if (toggleSlot3Btn && slot3Card) {
      toggleSlot3Btn.addEventListener("click", () => {
        thirdSlotActive = !thirdSlotActive;
        slot3Card.style.display = thirdSlotActive ? "block" : "none";
        toggleSlot3Btn.textContent = thirdSlotActive ? "− Hapus Kandidat ke-3" : "+ Tambah Kandidat ke-3";
        runComparison();
      });
    }

    async function runComparison() {
      const activeSlots = thirdSlotActive ? [1, 2, 3] : [1, 2];
      const vehicles = activeSlots.map((s) => {
        const item = catalog[parseInt(document.getElementById(`cmp-model-${s}`).value, 10)] || catalog[0];
        const preset = document.getElementById(`cmp-damage-preset-${s}`).value;
        const dmgConfig = getDamagesFromPreset(preset, item.jenis);

        return {
          jenis: item.jenis,
          merek: item.merek,
          model: item.model,
          tahun: parseInt(document.getElementById(`cmp-tahun-${s}`).value, 10) || 2022,
          kilometer: parseInt(document.getElementById(`cmp-km-${s}`).value, 10) || 30000,
          transmisi: item.transmisi_opts[0],
          bahan_bakar: item.bbm_opts[0],
          kondisi: 4,
          surat: document.getElementById(`cmp-surat-${s}`).value,
          kota: document.getElementById(`cmp-kota-${s}`).value || "Jakarta",
          kerusakan: dmgConfig.damages,
          indikasi_struktural: { ada: dmgConfig.structural, alasan: "" }
        };
      });

      try {
        const res = await fetch("/api/compare", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ vehicles })
        });
        const json = await res.json();
        if (json.status === "ok") {
          lastCompareData = json;
          renderComparisonTableAndVerdict(json);
          renderComparisonChart(json, currentChartType);
        }
      } catch (e) {
        showToast("Gagal memuat data perbandingan.");
      }
    }

    function renderComparisonTableAndVerdict(data) {
      document.getElementById("cmp-verdict-title").textContent =
        `Paling Worth It Setelah Perbaikan: ${data.verdict.winner_title} (Skor ${data.verdict.winner_score}/100)`;
      document.getElementById("cmp-verdict-summary").textContent = data.verdict.summary;

      const tbody = document.getElementById("cmp-table-body");
      const theadRow = document.getElementById("cmp-table-head-row");
      theadRow.innerHTML =
        `<th>Parameter Komparasi</th>` + data.items.map((it) => `<th>${it.title}</th>`).join("");

      const h = data.highlights;
      const rows = [
        {
          label: "Harga Dasar Kondisi Normal",
          render: (it) => formatRupiah(it.harga_dasar_normal),
          bestSlot: null
        },
        {
          label: "Temuan Kerusakan & Biaya Bengkel",
          render: (it) =>
            it.itemized_repairs.length
              ? `${it.itemized_repairs.length} titik (- ${formatRupiah(it.estimasi_biaya_perbaikan)})`
              : "0 titik (Rp 0)",
          bestSlot: h.lowest_repair_slot,
          bestLabel: "Perbaikan Termurah"
        },
        {
          label: "Harga Beli Apa Adanya (As-Is)",
          render: (it) => formatRupiah(it.harga_estimasi),
          bestSlot: h.lowest_price_slot,
          bestLabel: "Harga Beli Terendah"
        },
        {
          label: "Total Modal Siap Pakai (Beli + Perbaikan)",
          render: (it) => formatRupiah(it.total_siap_pakai),
          bestSlot: h.lowest_ready_slot,
          bestLabel: "Total Termurah"
        },
        {
          label: "Jarak Tempuh & Rata-rata/Thn",
          render: (it) => `${formatRibuan(it.input.kilometer)} km (${formatRibuan(it.km_per_year)} km/thn)`,
          bestSlot: h.lowest_km_slot,
          bestLabel: "KM Terendah"
        },
        {
          label: "Kelengkapan Surat-Surat",
          render: (it) => it.input.surat,
          bestSlot: null
        },
        {
          label: "Depresiasi per Tahun",
          render: (it) => `${it.annual_depreciation_pct}% (~${formatRupiah(it.annual_depreciation_rp)}/thn)`,
          bestSlot: h.lowest_depr_slot,
          bestLabel: "Paling Tahan"
        },
        {
          label: "Indeks Worth-It Setelah Perbaikan",
          render: (it) => `${it.value_score} / 100`,
          bestSlot: h.best_value_slot,
          bestLabel: "Paling Worth It"
        }
      ];

      tbody.innerHTML = rows
        .map((r) => {
          const cells = data.items
            .map((it) => {
              const isBest = r.bestSlot === it.slot;
              return `<td class="${isBest ? "cell-best" : ""}">${r.render(it)}${
                isBest ? `<span class="best-tag">${r.bestLabel}</span>` : ""
              }</td>`;
            })
            .join("");
          return `<tr><th>${r.label}</th>${cells}</tr>`;
        })
        .join("");
    }

    function renderComparisonChart(data, chartType) {
      const ctx = document.getElementById("compare-chart");
      if (!ctx || !window.Chart) return;
      if (compareChartInstance) compareChartInstance.destroy();

      const labels = Object.keys(data.items[0].scores);
      const palette = [
        { border: "#D9381E", bg: "rgba(217, 56, 30, 0.22)" },
        { border: "#1D3B72", bg: "rgba(29, 59, 114, 0.22)" },
        { border: "#156C43", bg: "rgba(21, 108, 67, 0.22)" }
      ];

      const datasets = data.items.map((item, idx) => ({
        label: item.title,
        data: labels.map((k) => item.scores[k]),
        borderColor: palette[idx].border,
        backgroundColor: palette[idx].bg,
        borderWidth: 2
      }));

      compareChartInstance = new Chart(ctx, {
        type: chartType,
        data: { labels, datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales:
            chartType === "radar"
              ? { r: { suggestedMin: 25, suggestedMax: 100 } }
              : { y: { beginAtZero: true, max: 100 } }
        }
      });
    }

    document.querySelectorAll("[data-chart-type]").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("[data-chart-type]").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentChartType = btn.dataset.chartType;
        if (lastCompareData) renderComparisonChart(lastCompareData, currentChartType);
      });
    });

    compareForm.addEventListener("submit", (e) => {
      e.preventDefault();
      runComparison();
    });

    runComparison();
  }

  // ==================== 5. HALAMAN SIMULASI KREDIT ====================
  function initCreditPage() {
    const creditForm = document.getElementById("credit-sim-form");
    if (!creditForm) return;

    const hargaInput = document.getElementById("cr-harga");
    const dpSlider = document.getElementById("cr-dp-persen");
    const dpRupiahInput = document.getElementById("cr-dp-rupiah");
    const dpPersenBadge = document.getElementById("cr-dp-persen-badge");
    const tenorSelect = document.getElementById("cr-tenor");
    const bungaSlider = document.getElementById("cr-bunga");
    const bungaBadge = document.getElementById("cr-bunga-badge");
    const usePredictedBtn = document.getElementById("btn-use-predicted-price");
    const toggleAmortBtn = document.getElementById("btn-toggle-amortization");
    const amortWrap = document.getElementById("cr-amortization-container");
    const warnBox = document.getElementById("credit-structural-warning");
    const warnText = document.getElementById("credit-structural-warning-text");

    let activeMethod = "anuitas";
    let lastSimData = null;
    let creditChartInstance = null;

    function syncDpFromSlider() {
      const harga = Math.max(5000000, parseInt(hargaInput.value, 10) || 180000000);
      const pct = parseFloat(dpSlider.value) || 25;
      const dpRp = Math.round((harga * pct) / 100);
      dpRupiahInput.value = dpRp;
      dpPersenBadge.textContent = `${pct}% (${formatRupiah(dpRp)})`;
      requestCreditCalculation();
    }

    function syncDpFromRupiah() {
      const harga = Math.max(5000000, parseInt(hargaInput.value, 10) || 180000000);
      const dpRp = Math.max(0, Math.min(harga * 0.9, parseInt(dpRupiahInput.value, 10) || 0));
      const pct = Math.round((dpRp / harga) * 100);
      dpSlider.value = Math.min(70, Math.max(10, pct));
      dpPersenBadge.textContent = `${pct}% (${formatRupiah(dpRp)})`;
      requestCreditCalculation();
    }

    async function requestCreditCalculation() {
      const payload = {
        harga: parseInt(hargaInput.value, 10) || 204850000,
        dp_rupiah: parseInt(dpRupiahInput.value, 10) || 51212500,
        tenor: parseInt(tenorSelect.value, 10) || 36,
        bunga_tahunan: parseFloat(bungaSlider.value) || 8.5
      };
      bungaBadge.textContent = `${payload.bunga_tahunan}% / thn`;

      try {
        const res = await fetch("/api/credit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (json.status === "ok") {
          lastSimData = json.data;
          renderCreditOutput();
        }
      } catch (e) {
        // ignore
      }
    }

    function renderCreditOutput() {
      if (!lastSimData) return;
      const current = lastSimData[activeMethod];
      const other = lastSimData[activeMethod === "anuitas" ? "flat" : "anuitas"];

      document.getElementById("cr-out-cicilan").textContent = formatRupiah(current.cicilan_per_bulan);
      document.getElementById("cr-out-pokok").textContent = formatRupiah(lastSimData.pokok_pinjaman);
      document.getElementById("cr-out-bunga").textContent = formatRupiah(current.total_bunga);
      document.getElementById("cr-out-total").textContent = formatRupiah(current.total_pembayaran);

      const diffNote = document.getElementById("cr-method-comparison-note");
      if (diffNote) {
        diffNote.textContent =
          activeMethod === "anuitas"
            ? `Pada metode Anuitas, total bunga (${formatRupiah(current.total_bunga)}) lebih hemat ${formatRupiah(lastSimData.selisih_total_bunga)} dibandingkan Bunga Flat (${formatRupiah(other.total_bunga)}).`
            : `Pada metode Bunga Flat, porsi pokok & bunga tetap setiap bulan dengan total bunga ${formatRupiah(current.total_bunga)} (cicilan Anuitas: ${formatRupiah(other.cicilan_per_bulan)}/bln).`;
      }

      const tbody = document.getElementById("cr-amort-tbody");
      if (tbody) {
        tbody.innerHTML = current.jadwal
          .map(
            (row) => `
            <tr>
              <td>Bulan ke-${row.bulan}</td>
              <td>${formatRupiah(row.cicilan)}</td>
              <td>${formatRupiah(row.pokok)}</td>
              <td>${formatRupiah(row.bunga)}</td>
              <td>${formatRupiah(row.sisa_pinjaman)}</td>
            </tr>
          `
          )
          .join("");
      }

      const ctx = document.getElementById("credit-composition-chart");
      if (ctx && window.Chart) {
        const dpVal = lastSimData.input.dp_rupiah;
        const pokokVal = lastSimData.pokok_pinjaman;
        const bungaVal = current.total_bunga;

        if (!creditChartInstance) {
          creditChartInstance = new Chart(ctx, {
            type: "doughnut",
            data: {
              labels: ["Uang Muka (DP)", "Pokok Pinjaman", "Total Bunga"],
              datasets: [
                {
                  data: [dpVal, pokokVal, bungaVal],
                  backgroundColor: ["#156C43", "#1D3B72", "#D9381E"],
                  borderWidth: 2
                }
              ]
            },
            options: {
              responsive: true,
              maintainAspectRatio: false,
              plugins: {
                tooltip: {
                  callbacks: {
                    label: (context) => `${context.label}: ${formatRupiah(context.parsed)}`
                  }
                }
              }
            }
          });
        } else {
          creditChartInstance.data.datasets[0].data = [dpVal, pokokVal, bungaVal];
          creditChartInstance.update();
        }
      }
    }

    hargaInput.addEventListener("input", syncDpFromSlider);
    dpSlider.addEventListener("input", syncDpFromSlider);
    dpRupiahInput.addEventListener("input", syncDpFromRupiah);
    tenorSelect.addEventListener("change", requestCreditCalculation);
    bungaSlider.addEventListener("input", requestCreditCalculation);

    document.querySelectorAll("[data-credit-method]").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("[data-credit-method]").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        activeMethod = btn.dataset.creditMethod;
        renderCreditOutput();
      });
    });

    if (usePredictedBtn) {
      usePredictedBtn.addEventListener("click", () => {
        const raw = localStorage.getItem(STORAGE_LAST_PRED);
        if (!raw) {
          showToast("Belum ada hasil inspeksi terakhir. Menggunakan contoh Rp 204.850.000.");
          hargaInput.value = 204850000;
          syncDpFromSlider();
          return;
        }
        try {
          const pred = JSON.parse(raw);
          hargaInput.value = pred.harga_estimasi;
          syncDpFromSlider();
          if (pred.has_structural_damage && warnBox && warnText) {
            warnBox.style.borderLeftColor = "var(--accent)";
            warnBox.style.backgroundColor = "var(--accent-soft)";
            warnText.innerHTML = `<strong>PERINGATAN KERUSAKAN BERAT/STRUKTURAL:</strong> Unit ${pred.input.merek} ${pred.input.model} yang baru Anda inspeksi memiliki indikasi kerusakan struktural/berat. Pengajuan kredit ke perusahaan leasing berisiko tinggi ditolak saat survei fisik.`;
          }
          showToast(`Harga diisi dari hasil inspeksi ${pred.input.merek} ${pred.input.model}: ${formatRupiah(pred.harga_estimasi)}`);
        } catch (e) {
          showToast("Gagal membaca data prediksi terakhir.");
        }
      });
    }

    if (toggleAmortBtn && amortWrap) {
      toggleAmortBtn.addEventListener("click", () => {
        const isHidden = amortWrap.style.display === "none";
        amortWrap.style.display = isHidden ? "block" : "none";
        toggleAmortBtn.textContent = isHidden ? "Sembunyikan Tabel Amortisasi" : "Buka Tabel Amortisasi Lengkap";
      });
    }

    syncDpFromSlider();
  }

  // ==================== 6. HALAMAN RIWAYAT ====================
  function initHistoryPage() {
    document.querySelectorAll(".js-delete-history").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.dataset.id;
        const res = await fetch(`/api/history?id=${id}`, { method: "DELETE" });
        const json = await res.json();
        if (json.status === "ok") {
          const card = document.getElementById(`history-card-${id}`);
          if (card) card.remove();
          showToast("Riwayat & file foto terkait berhasil dihapus.");
        }
      });
    });

    document.querySelectorAll(".js-use-in-credit").forEach((btn) => {
      btn.addEventListener("click", () => {
        const price = parseInt(btn.dataset.price, 10);
        const structural = parseInt(btn.dataset.structural, 10) === 1;
        const merek = btn.dataset.merek;
        const model = btn.dataset.model;
        localStorage.setItem(
          STORAGE_LAST_PRED,
          JSON.stringify({
            harga_estimasi: price,
            has_structural_damage: structural,
            input: { merek, model }
          })
        );
        window.location.href = "/kredit";
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    if (window.HargaBekasVehicles) {
      window.HargaBekasVehicles.initAllVisuals();
    }
    initPrediksiPage();
    initComparePage();
    initCreditPage();
    initHistoryPage();
  });
})();
