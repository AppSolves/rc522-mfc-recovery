from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class KeyType(StrEnum):
    A = "A"
    B = "B"


class NonceType(StrEnum):
    WEAK = "weak"
    HARD = "hard"
    STATIC = "static"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class CardInfo:
    uid: str
    atqa: str = "0400"
    sak: str = "08"
    card_type: str = "MIFARE Classic 1K"
    reader_version: str | None = None
    nonce_type: NonceType = NonceType.UNKNOWN

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["nonce_type"] = self.nonce_type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CardInfo:
        return cls(
            uid=str(data["uid"]).upper(),
            atqa=str(data.get("atqa", "0400")).upper(),
            sak=str(data.get("sak", "08")).upper(),
            card_type=str(data.get("card_type", data.get("type", "MIFARE Classic 1K"))),
            reader_version=data.get("reader_version"),
            nonce_type=NonceType(data.get("nonce_type", "unknown")),
        )


@dataclass(slots=True)
class KeyRecord:
    sector: int
    key_type: KeyType
    value: str
    source: str
    verified: bool = True
    discovered_at: str | None = None

    def __post_init__(self) -> None:
        self.value = normalize_key(self.value)
        if not 0 <= self.sector <= 15:
            raise ValueError("sector must be between 0 and 15")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["key_type"] = self.key_type.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KeyRecord:
        return cls(
            sector=int(data["sector"]),
            key_type=KeyType(data["key_type"]),
            value=str(data["value"]),
            source=str(data.get("source", "unknown")),
            verified=bool(data.get("verified", False)),
            discovered_at=data.get("discovered_at"),
        )


@dataclass(slots=True)
class RecoveryState:
    schema_version: int
    card: CardInfo
    keys: dict[str, dict[str, KeyRecord]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def get(self, sector: int, key_type: KeyType) -> KeyRecord | None:
        return self.keys.get(str(sector), {}).get(key_type.value)

    def get_verified(self, sector: int, key_type: KeyType) -> KeyRecord | None:
        record = self.get(sector, key_type)
        if record is None or not record.verified:
            return None
        return record

    def put(self, record: KeyRecord) -> None:
        self.keys.setdefault(str(record.sector), {})[record.key_type.value] = record

    def all_records(self) -> list[KeyRecord]:
        records: list[KeyRecord] = []
        for sector in range(16):
            for key_type in (KeyType.A, KeyType.B):
                record = self.get(sector, key_type)
                if record is not None:
                    records.append(record)
        return records

    def verified_records(self) -> list[KeyRecord]:
        return [record for record in self.all_records() if record.verified]

    def unique_key_values(self) -> list[str]:
        return sorted({record.value for record in self.verified_records()})

    def complete(self) -> bool:
        return all(self.get_verified(sector, kind) is not None for sector in range(16) for kind in KeyType)

    def has_key_for_every_sector(self) -> bool:
        return all(
            self.get_verified(sector, KeyType.A) is not None
            or self.get_verified(sector, KeyType.B) is not None
            for sector in range(16)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "card": self.card.to_dict(),
            "keys": {
                sector: {kind: record.to_dict() for kind, record in kinds.items()}
                for sector, kinds in self.keys.items()
            },
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryState:
        keys: dict[str, dict[str, KeyRecord]] = {}
        for sector, kinds in data.get("keys", {}).items():
            keys[str(sector)] = {kind: KeyRecord.from_dict(record) for kind, record in kinds.items()}
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            card=CardInfo.from_dict(data["card"]),
            keys=keys,
            notes=list(data.get("notes", [])),
        )


def normalize_key(value: str) -> str:
    clean = value.replace(" ", "").replace(":", "").upper()
    if len(clean) != 12 or any(character not in "0123456789ABCDEF" for character in clean):
        raise ValueError("MIFARE Classic keys must contain exactly 12 hexadecimal characters")
    return clean


def parse_known_key(value: str) -> tuple[int, KeyType, str]:
    """Parse ``SECTOR:TYPE=KEY``."""
    try:
        left, key = value.split("=", 1)
        sector_text, type_text = left.split(":", 1)
        sector = int(sector_text)
        key_type = KeyType(type_text.upper())
    except (ValueError, TypeError) as error:
        raise ValueError("known key must look like 4:A=FFFFFFFFFFFF") from error
    if not 0 <= sector <= 15:
        raise ValueError("known key sector must be between 0 and 15")
    return sector, key_type, normalize_key(key)


def parse_sector_expression(expression: str) -> list[int]:
    values: set[int] = set()
    for item in expression.split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"invalid sector range: {item}")
            values.update(range(start, end + 1))
        else:
            values.add(int(item))
    if not values:
        raise ValueError("no sectors selected")
    invalid = sorted(value for value in values if value < 0 or value > 15)
    if invalid:
        raise ValueError(f"only MIFARE Classic 1K sectors 0-15 are supported: {invalid}")
    return sorted(values)
