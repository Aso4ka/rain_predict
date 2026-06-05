import os

MAX_STORAGE_SIZE = 500 * 1024 * 1024

DATASET_PATH = "storage/datasets"
FORECAST_PATH = "storage/forecasts"
EXPORT_PATH = "storage/exports"


def get_folder_size(folder):

    total = 0

    for path, dirs, files in os.walk(folder):

        for f in files:

            fp = os.path.join(path, f)

            if os.path.exists(fp):
                total += os.path.getsize(fp)

    return total


def check_storage_limit():

    total = (
        get_folder_size(DATASET_PATH)
        + get_folder_size(FORECAST_PATH)
        + get_folder_size(EXPORT_PATH)
    )

    return total < MAX_STORAGE_SIZE