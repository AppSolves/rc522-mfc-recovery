from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import KeyType, RecoveryState


def export_json(state: RecoveryState, output: Path) -> Path:
    output.write_text(json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def export_csv(state: RecoveryState, output: Path) -> Path:
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sector", "key_a", "key_b", "source_a", "source_b"])
        for sector in range(16):
            a = state.get_verified(sector, KeyType.A)
            b = state.get_verified(sector, KeyType.B)
            writer.writerow(
                [
                    sector,
                    a.value if a else "",
                    b.value if b else "",
                    a.source if a else "",
                    b.source if b else "",
                ]
            )
    return output


def export_mct_keys(state: RecoveryState, output: Path) -> Path:
    output.write_text("\n".join(state.unique_key_values()) + "\n", encoding="utf-8")
    return output
