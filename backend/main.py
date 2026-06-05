from fastapi import FastAPI
from fastapi import UploadFile
from fastapi import File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fastapi.responses import FileResponse

import shutil
import os
import pandas as pd

from storage import check_storage_limit

from forecast import run_model

from export import (
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

DATASET_PATH = "storage/datasets"
FORECAST_PATH = "storage/forecasts"
EXPORT_PATH = "storage/exports"

os.makedirs(DATASET_PATH, exist_ok=True)
os.makedirs(FORECAST_PATH, exist_ok=True)
os.makedirs(EXPORT_PATH, exist_ok=True)

class Feedback(BaseModel):
    rating: int
    text: str

# =========================
# Upload dataset
# =========================

@app.post("/upload-dataset")
async def upload_dataset(
    file: UploadFile = File(...)
):
    if not file.filename.endswith(".csv"):
        return {
            "error": "Only CSV files allowed"
    }

    if not check_storage_limit():

        return {
            "error": "Storage limit exceeded"
        }

    path = f"{DATASET_PATH}/{file.filename}"

    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {
        "message": "Dataset uploaded",
        "filename": file.filename
    }


# =========================
# Create forecast
# =========================

@app.post("/forecast")
async def create_forecast(
    file: UploadFile = File(...)
):

    input_path = f"{DATASET_PATH}/{file.filename}"

    with open(input_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    output_name = f"forecast_{file.filename}"

    output_path = (
        f"{FORECAST_PATH}/{output_name}"
    )

    run_model(input_path, output_path)

    return {
        "forecast": output_name
    }


# =========================
# Forecast JSON for frontend
# =========================

@app.get("/forecast-data/{filename}")
async def forecast_data(filename: str):

    path = f"{FORECAST_PATH}/{filename}"

    df = pd.read_csv(path)

    return df.to_dict(orient="records")


# =========================
# List datasets
# =========================

@app.get("/datasets")
async def datasets():

    return {
        "datasets": os.listdir(DATASET_PATH)
    }


# =========================
# List forecasts
# =========================

@app.get("/forecasts")
async def forecasts():

    return {
        "forecasts": os.listdir(FORECAST_PATH)
    }


# =========================
# Download XLS
# =========================

@app.get("/download/xls/{filename}")
async def download_xls(filename: str):

    csv_path = (
        f"{FORECAST_PATH}/{filename}"
    )

    xls_path = (
        f"{EXPORT_PATH}/{filename}.xlsx"
    )

    export_xls(csv_path, xls_path)

    return FileResponse(xls_path)


# =========================
# Download PNG
# =========================

@app.get("/download/png/{filename}")
async def download_png(filename: str):

    csv_path = (
        f"{FORECAST_PATH}/{filename}"
    )

    png_path = (
        f"{EXPORT_PATH}/{filename}.png"
    )

    export_png(csv_path, png_path)

    return FileResponse(png_path)


# =========================
# Download PDF
# =========================

@app.get("/download/pdf/{filename}")
async def download_pdf(filename: str):

    pdf_path = (
        f"{EXPORT_PATH}/{filename}.pdf"
    )

    export_pdf(pdf_path)

    return FileResponse(pdf_path)

@app.post("/feedback")
async def feedback(item: Feedback):

    with open(
        "storage/feedback.txt",
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            f"{item.rating}|{item.text}\n"
        )

    return {
        "message": "Feedback saved"
    }
