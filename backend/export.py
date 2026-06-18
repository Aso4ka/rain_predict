import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4


def export_xls(csv_file, output_file):

    df = pd.read_csv(csv_file)

    df.to_excel(output_file, index=False)


def export_png(csv_file, output_file):

    df = pd.read_csv(csv_file)

    plt.figure(figsize=(10, 5))

    plt.plot(df["date"], df["rain"], marker="o")

    plt.xticks(rotation=45)
    plt.title("RainPredict forecast")
    plt.xlabel("Date")
    plt.ylabel("Rain, mm")
    plt.grid(alpha=0.25)

    plt.tight_layout()

    plt.savefig(output_file)
    plt.close()


def export_pdf(csv_file, output_file):

    df = pd.read_csv(csv_file)
    c = canvas.Canvas(str(output_file), pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 60, "RainPredict Forecast Report")

    c.setFont("Helvetica", 11)
    y = height - 100
    c.drawString(50, y, "Date")
    c.drawString(180, y, "Rain, mm")
    c.drawString(280, y, "Probability, %")
    y -= 18

    for _, row in df.head(25).iterrows():
        c.drawString(50, y, str(row["date"]))
        c.drawString(180, y, str(row["rain"]))
        c.drawString(280, y, str(row["probability"]))
        y -= 18

    c.save()
