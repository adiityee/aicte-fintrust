"""Generate ten synthetic Indian-bank FDR certificates for local testing."""

from __future__ import annotations

import argparse
from pathlib import Path

import fitz
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


BANKS = (
    {"name": "State Bank of India", "branch": "Parliament Street Branch", "ifsc": "SBIN0000691"},
    {"name": "Punjab National Bank", "branch": "Sansad Marg Branch", "ifsc": "PUNB0001200"},
    {"name": "HDFC Bank", "branch": "Connaught Place Branch", "ifsc": "HDFC0000003"},
)
CREATION_DATE = "D:20261026090000+05'30'"


def _indian_amount(amount: int) -> str:
    digits = str(amount)
    if len(digits) <= 3:
        return digits
    trailing = digits[-3:]
    leading = digits[:-3]
    groups = []
    while leading:
        groups.insert(0, leading[-2:])
        leading = leading[:-2]
    return ",".join([*groups, trailing])


def _draw_certificate(output: Path, number: int, bank: dict[str, str], amount: int, submitted: int) -> None:
    page_width, page_height = A4
    pdf = canvas.Canvas(str(output), pagesize=A4)
    pdf.setTitle(f"Synthetic Fixed Deposit Receipt {number:03d}")
    pdf.setAuthor("FinTrust Synthetic Dataset")

    if bank["name"] == "State Bank of India":
        title = "STATE BANK OF INDIA | TERM DEPOSIT RECEIPT"
    elif bank["name"] == "Punjab National Bank":
        title = "PUNJAB NATIONAL BANK | FIXED DEPOSIT ADVICE"
    else:
        title = "HDFC BANK | FIXED DEPOSIT RECEIPT"

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(page_width / 2, page_height - 72, title)
    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(page_width / 2, page_height - 91, "SYNTHETIC SAMPLE - NOT A NEGOTIABLE INSTRUMENT")
    pdf.line(54, page_height - 105, page_width - 54, page_height - 105)

    rows = (
        ("Branch", bank["branch"]),
        ("FDR Number", f"FDR2026{number:05d}"),
        ("IFSC", bank["ifsc"]),
        ("Depositor", f"Example Institution {number:02d}"),
        ("Principal Amount", f"INR {_indian_amount(amount)}.00"),
        ("Form Submitted Amount", f"INR {_indian_amount(submitted)}.00"),
        ("Interest Rate", "7.10% p.a."),
        ("Issue Date", "26 October 2026"),
        ("Maturity Date", "26 October 2027"),
        ("Lien Holder", "AICTE"),
        ("Lien", "Marked in favour of AICTE"),
    )
    y = page_height - 145
    for label, value in rows:
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(72, y, f"{label}:")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(245, y, value)
        y -= 32

    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(72, 74, "All names, account details, and deposit records on this certificate are fabricated.")
    pdf.save()

    with fitz.open(output) as document:
        metadata = document.metadata
        metadata["creationDate"] = CREATION_DATE
        metadata["modDate"] = CREATION_DATE
        document.set_metadata(metadata)
        temporary = output.with_suffix(".metadata.pdf")
        document.save(temporary)
    temporary.replace(output)


def generate(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for number in range(1, 11):
        bank = BANKS[(number - 1) % len(BANKS)]
        amount = 100_000 if number in {4, 8} else 1_000_000 + number * 100_000
        submitted_amount = 1_000_000 if number in {4, 8} else amount
        output = output_dir / f"synthetic_fdr_{number:02d}.pdf"
        _draw_certificate(output, number, bank, amount, submitted_amount)
        generated.append(output)

    revised_pdf = generated[9]
    with fitz.open(revised_pdf) as document:
        metadata = document.metadata
        metadata["modDate"] = "D:20261027100000+05'30'"
        document.set_metadata(metadata)
        document.saveIncr()
    return generated


def main() -> None:
    default_dir = Path(__file__).resolve().parents[1] / "data" / "synthetic_fdrs"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=default_dir)
    args = parser.parse_args()
    for path in generate(args.output_dir):
        print(path)


if __name__ == "__main__":
    main()