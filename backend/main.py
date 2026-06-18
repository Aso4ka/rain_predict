from pathlib import Path

import os

BASE_DIR = Path(__file__).resolve().parent.parent
MATPLOTLIB_CONFIG_DIR = BASE_DIR / ".matplotlib"
MATPLOTLIB_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MATPLOTLIB_CONFIG_DIR))

from fastapi import FastAPI
from fastapi import UploadFile
from fastapi import File
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import shutil
import pandas as pd

from .storage import check_storage_limit

from .forecast import run_model

from .export import (
    export_xls,
    export_png,
    export_pdf
)

app = FastAPI()
print("Rain predict backend initialized")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_PATH = BASE_DIR / "frontend"
STORAGE_PATH = BASE_DIR / "storage"
DATASET_PATH = STORAGE_PATH / "datasets"
FORECAST_PATH = STORAGE_PATH / "forecasts"
EXPORT_PATH = STORAGE_PATH / "exports"

DATASET_PATH.mkdir(parents=True, exist_ok=True)
FORECAST_PATH.mkdir(parents=True, exist_ok=True)
EXPORT_PATH.mkdir(parents=True, exist_ok=True)

class Feedback(BaseModel):
    rating: int
    text: str


def safe_filename(filename: str) -> str:
    name = Path(filename).name

    if not name:
        raise HTTPException(status_code=400, detail="Empty filename")

    return name

# =========================
# Upload dataset
# =========================

@app.post("/upload-dataset")
async def upload_dataset(
    file: UploadFile = File(...)
):
    filename = safe_filename(file.filename)

    if not filename.lower().endswith(".csv"):
        return {
            "error": "Можно загружать только CSV файлы"
    }

    if not check_storage_limit():

        return {
            "error": "Превышен лимит хранилища"
        }

    path = DATASET_PATH / filename

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "Датасет загружен",
        "filename": filename
    }


# =========================
# Create forecast
# =========================

@app.post("/forecast")
async def create_forecast(
    file: UploadFile = File(...)
):
    filename = safe_filename(file.filename)

    if not filename.lower().endswith(".csv"):
        return {
            "error": "Можно загружать только CSV файлы"
        }

    input_path = DATASET_PATH / filename

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    output_name = f"forecast_{filename}"

    output_path = FORECAST_PATH / output_name

    try:
        run_model(input_path, output_path)
    except (ValueError, FileNotFoundError, ImportError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "message": "Прогноз построен",
        "forecast": output_name
    }


# =========================
# Forecast JSON for frontend
# =========================

@app.get("/forecast-data/{filename}")
async def forecast_data(filename: str):
    filename = safe_filename(filename)
    path = FORECAST_PATH / filename

    if not path.exists():
        raise HTTPException(status_code=404, detail="Forecast not found")

    df = pd.read_csv(path)

    return df.to_dict(orient="records")


# =========================
# List datasets
# =========================

@app.get("/datasets")
async def datasets():

    return {
        "datasets": sorted(os.listdir(DATASET_PATH))
    }


@app.delete("/delete-dataset/{filename}")
async def delete_dataset(filename: str):
    filename = safe_filename(filename)
    path = DATASET_PATH / filename

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Dataset not found")

    path.unlink()

    return {
        "message": "Датасет удалён",
        "filename": filename
    }


# =========================
# List forecasts
# =========================

@app.get("/forecasts")
async def forecasts():

    return {
        "forecasts": sorted(os.listdir(FORECAST_PATH))
    }


# =========================
# Download XLS
# =========================

@app.get("/download/xls/{filename}")
async def download_xls(filename: str):
    filename = safe_filename(filename)
    csv_path = FORECAST_PATH / filename
    xls_path = EXPORT_PATH / f"{filename}.xlsx"

    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Forecast not found")

    export_xls(csv_path, xls_path)

    return FileResponse(xls_path, filename=xls_path.name)


# =========================
# Download PNG
# =========================

@app.get("/download/png/{filename}")
async def download_png(filename: str):
    filename = safe_filename(filename)
    csv_path = FORECAST_PATH / filename
    png_path = EXPORT_PATH / f"{filename}.png"

    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Forecast not found")

    export_png(csv_path, png_path)

    return FileResponse(png_path, filename=png_path.name)


# =========================
# Download PDF
# =========================

@app.get("/download/pdf/{filename}")
async def download_pdf(filename: str):
    filename = safe_filename(filename)
    csv_path = FORECAST_PATH / filename
    pdf_path = EXPORT_PATH / f"{filename}.pdf"

    if not csv_path.exists():
        raise HTTPException(status_code=404, detail="Forecast not found")

    export_pdf(csv_path, pdf_path)

    return FileResponse(pdf_path, filename=pdf_path.name)

@app.post("/feedback")
async def feedback(item: Feedback):

    with open(
        STORAGE_PATH / "feedback.txt",
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            f"{item.rating}|{item.text}\n"
        )

    return {
        "message": "Отзыв сохранен"
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if FRONTEND_PATH.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_PATH, html=True), name="frontend")
