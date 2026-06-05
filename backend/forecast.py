import subprocess

def run_model(input_csv, output_csv):

    subprocess.run([
        "python",
        "model_service/predict.py",
        input_csv,
        output_csv
    ])

    return output_csv 