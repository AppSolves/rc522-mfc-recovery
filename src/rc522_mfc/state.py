from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .models import CardInfo, RecoveryState


class StateStore:
    def __init__(self, card_dir: Path) -> None:
        self.card_dir = card_dir
        self.path = card_dir / "state.json"

    def load_or_create(self, card: CardInfo) -> RecoveryState:
        self.card_dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            return RecoveryState(schema_version=1, card=card)
        state = RecoveryState.from_dict(json.loads(self.path.read_text(encoding="utf-8")))
        if state.card.uid != card.uid:
            raise RuntimeError(f"state belongs to UID {state.card.uid}, not {card.uid}")
        state.card = card
        return state

    def load(self) -> RecoveryState:
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        return RecoveryState.from_dict(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, state: RecoveryState) -> None:
        self.card_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(state.to_dict(), indent=2, sort_keys=True) + "\n"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.card_dir,
            prefix=".state.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            temporary = Path(handle.name)
        temporary.replace(self.path)
