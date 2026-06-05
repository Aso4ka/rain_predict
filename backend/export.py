import pandas as pd
import matplotlib.pyplot as plt

from reportlab.pdfgen import canvas


def export_xls(csv_file, output_file):

    df = pd.read_csv(csv_file)

    df.to_excel(output_file, index=False)


def export_png(csv_file, output_file):

    df = pd.read_csv(csv_file)

    plt.figure(figsize=(10, 5))

    plt.plot(df["date"], df["rain"])

    plt.xticks(rotation=45)

    plt.tight_layout()

    plt.savefig(output_file)


def export_pdf(output_file):

    c = canvas.Canvas(output_file)

    c.drawString(100, 750, "RainPredict Forecast Report")

    c.save()