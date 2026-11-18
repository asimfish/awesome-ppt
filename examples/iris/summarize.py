"""Rebuild the public Iris talk's source table from the frozen UCI input."""

import argparse
import csv
import hashlib
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "bezdekIris.data"
DIGEST = "0fed2a99db77ec533a62dc66894d3ec6df3b58b6a8f3cf4a6b47e4086b7f97dc"


def summarize(dest, observations=None):
    if hashlib.sha256(INPUT.read_bytes()).hexdigest() != DIGEST:
        raise ValueError("The input differs from the cited UCI snapshot.")
    groups = {}
    specimens = []
    with INPUT.open(encoding="ascii", newline="") as stream:
        for row in csv.reader(stream):
            if row:
                species = row[4].removeprefix("Iris-").capitalize()
                groups.setdefault(species, []).append(Decimal(row[2]))
                specimens.append((str(len(specimens) + 1), species, row[2]))
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
    if observations:
        with observations.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(["Specimen", "Species", "Petal length (cm)"])
            writer.writerows(specimens)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", nargs="?", type=Path)
    parser.add_argument("--observations", type=Path)
    args = parser.parse_args()
    summarize(
        args.summary or ROOT / "summary.csv",
        args.observations
        or (ROOT / "observations.csv" if args.summary is None else None),
    )
