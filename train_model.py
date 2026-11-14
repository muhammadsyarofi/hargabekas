"""
Script Pelatihan Model Machine Learning HargaBekas.
Melatih Pipeline GradientBoostingRegressor & RandomForestRegressor menggunakan scikit-learn,
mengevaluasi metrik MAE, RMSE, MAPE, dan R², serta menyimpan model ke `models/price_model.joblib`.
"""

import json
import os
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from generate_dataset import VEHICLE_CATALOG, CITY_FACTORS, SURAT_FACTORS, generate_dataset

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "data", "vehicles_dataset.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "price_model.joblib")
METADATA_PATH = os.path.join(BASE_DIR, "models", "model_metadata.json")


def train_and_save_model():
    """Melatih model prediksi harga kendaraan bekas dan menyimpan artefak model."""
    if not os.path.exists(DATASET_PATH):
        print("[HargaBekas] Dataset belum ditemukan, men-generate dataset baru...")
        df = generate_dataset(n_samples=750, output_path=DATASET_PATH)
    else:
        df = pd.read_csv(DATASET_PATH)
        if "surat" not in df.columns:
            print("[HargaBekas] Dataset versi lama terdeteksi, memperbarui dataset dengan kolom kelengkapan surat...")
            df = generate_dataset(n_samples=750, output_path=DATASET_PATH)

    feature_cols = [
        "jenis",
        "merek",
        "model",
        "tahun",
        "kilometer",
        "transmisi",
        "bahan_bakar",
        "kondisi",
        "surat",
        "kota",
    ]
    target_col = "harga"

    X = df[feature_cols]
    y = df[target_col]

    categorical_features = ["jenis", "merek", "model", "transmisi", "bahan_bakar", "surat", "kota"]
    numeric_features = ["tahun", "kilometer", "kondisi"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features),
            ("num", StandardScaler(), numeric_features),
        ]
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=df["model"]
    )

    # 1. Latih Gradient Boosting Regressor (Model Utama)
    gbr_pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "regressor",
                GradientBoostingRegressor(
                    n_estimators=260,
                    learning_rate=0.065,
                    max_depth=5,
                    min_samples_split=4,
                    subsample=0.88,
                    random_state=42,
                ),
            ),
        ]
    )
    gbr_pipeline.fit(X_train, y_train)
    y_pred_gbr = gbr_pipeline.predict(X_test)

    # 2. Latih Random Forest Regressor (Pembanding & Estimator Interval Kepercayaan)
    rf_pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "regressor",
                RandomForestRegressor(
                    n_estimators=180,
                    max_depth=14,
                    min_samples_split=3,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    rf_pipeline.fit(X_train, y_train)
    y_pred_rf = rf_pipeline.predict(X_test)

    # Hitung metrik evaluasi
    mae_gbr = float(mean_absolute_error(y_test, y_pred_gbr))
    rmse_gbr = float(np.sqrt(mean_squared_error(y_test, y_pred_gbr)))
    r2_gbr = float(r2_score(y_test, y_pred_gbr))
    mape_gbr = float(np.mean(np.abs((y_test - y_pred_gbr) / y_test)) * 100)

    # Metrik terpisah untuk motor vs mobil agar transparan di halaman Tentang
    mask_motor = X_test["jenis"] == "motor"
    mask_mobil = X_test["jenis"] == "mobil"
    mae_motor = float(mean_absolute_error(y_test[mask_motor], y_pred_gbr[mask_motor]))
    mae_mobil = float(mean_absolute_error(y_test[mask_mobil], y_pred_gbr[mask_mobil]))

    mae_rf = float(mean_absolute_error(y_test, y_pred_rf))
    r2_rf = float(r2_score(y_test, y_pred_rf))

    # Hitung agregasi feature importance per kolom asli
    ohe_feature_names = (
        gbr_pipeline.named_steps["preprocessor"]
        .named_transformers_["cat"]
        .get_feature_names_out(categorical_features)
    )
    all_feature_names = list(ohe_feature_names) + numeric_features
    raw_importances = gbr_pipeline.named_steps["regressor"].feature_importances_

    aggregated_importance = {col: 0.0 for col in feature_cols}
    for fname, imp in zip(all_feature_names, raw_importances):
        matched = False
        for col in categorical_features:
            if fname.startswith(col + "_"):
                aggregated_importance[col] += float(imp)
                matched = True
                break
        if not matched and fname in aggregated_importance:
            aggregated_importance[fname] += float(imp)

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    # Simpan bundle kedua model (utama + ensemble interval)
    joblib.dump(
        {
            "primary_model": gbr_pipeline,
            "rf_model": rf_pipeline,
            "feature_cols": feature_cols,
        },
        MODEL_PATH,
    )

    metadata = {
        "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M WIB"),
        "algorithm": "Gradient Boosting Regressor + Random Forest Ensemble",
        "dataset_rows": int(len(df)),
        "train_rows": int(len(X_train)),
        "test_rows": int(len(X_test)),
        "metrics": {
            "mae": round(mae_gbr),
            "mae_motor": round(mae_motor),
            "mae_mobil": round(mae_mobil),
            "rmse": round(rmse_gbr),
            "r2": round(r2_gbr, 4),
            "mape_percent": round(mape_gbr, 2),
            "rf_mae": round(mae_rf),
            "rf_r2": round(r2_rf, 4),
        },
        "feature_importance": {
            k: round(v * 100, 2)
            for k, v in sorted(aggregated_importance.items(), key=lambda x: x[1], reverse=True)
        },
        "catalog": VEHICLE_CATALOG,
        "cities": list(CITY_FACTORS.keys()),
        "surat_options": list(SURAT_FACTORS.keys()),
    }

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"[HargaBekas] Model disimpan ke {MODEL_PATH}")
    print(f"[HargaBekas] Metrik GBR -> R²: {r2_gbr:.4f} | MAE Total: Rp {mae_gbr:,.0f} | MAPE: {mape_gbr:.2f}%")
    return metadata


if __name__ == "__main__":
    train_and_save_model()
