"""Rebuild the public Iris talk's source table from the frozen UCI input."""

import csv
import hashlib
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "bezdekIris.data"
DIGEST = "0fed2a99db77ec533a62dc66894d3ec6df3b58b6a8f3cf4a6b47e4086b7f97dc"


def summarize(dest):
    if hashlib.sha256(INPUT.read_bytes()).hexdigest() != DIGEST:
        raise ValueError("The input differs from the cited UCI snapshot.")
    groups = {}
    with INPUT.open(encoding="ascii", newline="") as stream:
        for row in csv.reader(stream):
            if row:
                species = row[4].removeprefix("Iris-").capitalize()
                groups.setdefault(species, []).append(Decimal(row[2]))
    with dest.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            ["Species", "Plants", "Mean (cm)", "Minimum (cm)", "Maximum (cm)"]
        )
        for species, values in groups.items():
            writer.writerow(
                [
                    species,
                    len(values),
                    f"{sum(values) / len(values):.3f}",
                    min(values),
                    max(values),
                ]
            )


if __name__ == "__main__":
    summarize(Path(sys.argv[1]) if len(sys.argv) == 2 else ROOT / "summary.csv")
