from functools import lru_cache
from pathlib import Path
import pickle
import warnings

import numpy as np
import pandas as pd


warnings.simplefilter("ignore", pd.errors.PerformanceWarning)

MODEL_PATH = Path(__file__).resolve().parent / "model_service" / "model_xgb_24h.pkl"

RAW_DEFAULTS = {
    "precip_helman_mm": 0.0,
    "wind_direction_deg": 0.0,
    "wind_speed_ms": 0.0,
    "temperature_c": 0.0,
    "humidity_percent": 70.0,
    "pressure_hpa": 1013.0,
    "precip_vaisala_mm": 0.0,
    "solar_radiation_wm2": 0.0,
}

ALIASES = {
    "date": "date",
    "datetime": "date",
    "timestamp": "date",
    "time": "date",
    "дата": "date",
    "precip": "precip_helman_mm",
    "rain": "precip_helman_mm",
    "осадки": "precip_helman_mm",
    "rain_mm": "precip_helman_mm",
    "precipitation": "precip_helman_mm",
    "temperature": "temperature_c",
    "temp": "temperature_c",
    "температура": "temperature_c",
    "humidity": "humidity_percent",
    "влажность": "humidity_percent",
    "pressure": "pressure_hpa",
    "давление": "pressure_hpa",
    "wind_speed": "wind_speed_ms",
    "скорость_ветра": "wind_speed_ms",
    "wind_direction": "wind_direction_deg",
    "направление_ветра": "wind_direction_deg",
    "solar_radiation": "solar_radiation_wm2",
}


@lru_cache(maxsize=1)
def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    with MODEL_PATH.open("rb") as file:
        return pickle.load(file)


def _read_csv(input_csv: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(input_csv, sep=None, engine="python")
    except Exception:
        return pd.read_csv(input_csv)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}

    for column in df.columns:
        normalized = str(column).strip().lower()
        renamed[column] = ALIASES.get(normalized, normalized)

    return df.rename(columns=renamed)


def _numeric(series: pd.Series) -> pd.Series:
    values = (
        series.astype(str)
        .str.strip()
        .str.replace(",", ".", regex=False)
        .str.replace(" ", "", regex=False)
    )
    return pd.to_numeric(values, errors="coerce")


def _season(month: pd.Series) -> pd.Series:
    return ((month % 12) // 3).astype(int)


def _prepare_base_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = _normalize_columns(df).copy()
    has_vaisala = "precip_vaisala_mm" in df.columns

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    else:
        end = pd.Timestamp.now().floor("h")
        df["date"] = pd.date_range(end=end, periods=len(df), freq="h")

    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    if df.empty:
        raise ValueError("CSV does not contain valid rows with dates")

    for column, default in RAW_DEFAULTS.items():
        if column in df.columns:
            df[column] = _numeric(df[column]).ffill().bfill().fillna(default)
        else:
            df[column] = default

    if not has_vaisala:
        df["precip_vaisala_mm"] = df["precip_helman_mm"]

    return df


def _add_time_features(features: pd.DataFrame) -> None:
    date = features["date"]
    features["hour"] = date.dt.hour
    features["dayofweek"] = date.dt.dayofweek
    features["month"] = date.dt.month
    features["dayofyear"] = date.dt.dayofyear

    features["hour_sin"] = np.sin(2 * np.pi * features["hour"] / 24)
    features["hour_cos"] = np.cos(2 * np.pi * features["hour"] / 24)
    features["month_sin"] = np.sin(2 * np.pi * features["month"] / 12)
    features["month_cos"] = np.cos(2 * np.pi * features["month"] / 12)
    features["dayofweek_sin"] = np.sin(2 * np.pi * features["dayofweek"] / 7)
    features["dayofweek_cos"] = np.cos(2 * np.pi * features["dayofweek"] / 7)
    features["dayofyear_sin"] = np.sin(2 * np.pi * features["dayofyear"] / 365)
    features["dayofyear_cos"] = np.cos(2 * np.pi * features["dayofyear"] / 365)

    features["season"] = _season(features["month"])
    features["season_sin"] = np.sin(2 * np.pi * features["season"] / 4)
    features["season_cos"] = np.cos(2 * np.pi * features["season"] / 4)
    features["is_winter"] = (features["season"] == 0).astype(int)
    features["is_spring"] = (features["season"] == 1).astype(int)
    features["is_summer"] = (features["season"] == 2).astype(int)
    features["is_autumn"] = (features["season"] == 3).astype(int)


def _add_weather_features(features: pd.DataFrame) -> None:
    wind_rad = np.deg2rad(features["wind_direction_deg"])
    features["wind_dir_sin"] = np.sin(wind_rad)
    features["wind_dir_cos"] = np.cos(wind_rad)
    features["low_solar_flag"] = (features["solar_radiation_wm2"] < 50).astype(int)
    features["very_low_solar_flag"] = (features["solar_radiation_wm2"] < 10).astype(int)


def _add_precip_features(features: pd.DataFrame) -> None:
    precip = features["precip_helman_mm"].clip(lower=0)

    for hours in [1, 2, 3, 6, 12, 24, 36, 48, 72, 96, 120, 168]:
        lag = precip.shift(hours)
        window = precip.rolling(hours, min_periods=1)

        features[f"precip_lag_{hours}h"] = lag
        features[f"precip_mean_{hours}h"] = window.mean()
        features[f"precip_max_{hours}h"] = window.max()
        features[f"precip_sum_{hours}h"] = window.sum()

    for hours in [6, 12, 24, 48, 72, 168]:
        rain_hours = precip.rolling(hours, min_periods=1).apply(lambda values: float((values > 0).sum()))
        features[f"rain_hours_{hours}h"] = rain_hours
        features[f"precip_intensity_{hours}h"] = features[f"precip_sum_{hours}h"] / rain_hours.replace(0, np.nan)

    for hours in [24, 72, 168]:
        features[f"precip_max_intensity_{hours}h"] = (
            precip / precip.rolling(hours, min_periods=1).apply(lambda values: max(float((values > 0).sum()), 1.0))
        )

    features["precip_sum_7d"] = precip.rolling(24 * 7, min_periods=1).sum()
    features["precip_sum_30d"] = precip.rolling(24 * 30, min_periods=1).sum()


def _add_trend_features(features: pd.DataFrame) -> None:
    sources = {
        "pressure": "pressure_hpa",
        "temp": "temperature_c",
        "humidity": "humidity_percent",
        "wind": "wind_speed_ms",
    }

    for hours in [1, 2, 3, 6, 12, 24, 48]:
        for prefix, column in sources.items():
            if prefix == "wind" and hours > 6:
                continue

            trend_name = f"{prefix}_trend_{hours}h"
            features[trend_name] = features[column] - features[column].shift(hours)

            if prefix in {"pressure", "temp"}:
                features[f"{prefix}_acceleration_{hours}h"] = features[trend_name] - features[trend_name].shift(hours)


def _build_features(df: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
    features = _prepare_base_frame(df)

    if set(feature_names).issubset(features.columns):
        return features[feature_names].apply(_numeric).fillna(0)

    _add_time_features(features)
    _add_weather_features(features)
    _add_precip_features(features)
    _add_trend_features(features)

    features = features.replace([np.inf, -np.inf], np.nan).ffill().bfill().fillna(0)

    missing = [name for name in feature_names if name not in features.columns]
    if missing:
        for name in missing:
            features[name] = 0

    return features[feature_names]


def _expected_rain_mm(source: pd.DataFrame, probability: float) -> float:
    recent = source["precip_helman_mm"].tail(min(24, len(source))).clip(lower=0)
    recent_sum = float(recent.sum())
    rainy_mean = float(recent[recent > 0].mean()) if (recent > 0).any() else 1.0
    estimate = max(recent_sum * 0.35, rainy_mean)

    return round(max(0.0, estimate * probability), 1)


def run_model(input_csv: str | Path, output_csv: str | Path) -> Path:
    input_csv = Path(input_csv)
    output_csv = Path(output_csv)
    model = load_model()
    df = _read_csv(input_csv)

    if df.empty:
        raise ValueError("CSV file is empty")

    feature_names = list(getattr(model, "feature_names_in_", []))
    if not feature_names:
        booster = model.get_booster()
        feature_names = list(booster.feature_names or [])

    if not feature_names:
        raise ValueError("The model does not contain feature names")

    source = _prepare_base_frame(df)
    features = _build_features(df, feature_names)
    latest_features = features.tail(1)

    if hasattr(model, "predict_proba"):
        probability = float(model.predict_proba(latest_features)[0][1])
    else:
        probability = float(model.predict(latest_features)[0])

    probability = min(max(probability, 0.0), 1.0)
    last_date = source["date"].max()
    forecast_date = last_date + pd.Timedelta(hours=24)
    expected_rain = _expected_rain_mm(source, probability)

    forecast_df = pd.DataFrame([{
        "date": forecast_date.isoformat(),
        "rain": expected_rain,
        "probability": round(probability * 100, 1),
    }])

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    forecast_df.to_csv(output_csv, index=False)

    return output_csv
