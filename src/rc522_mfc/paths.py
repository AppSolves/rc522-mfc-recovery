from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_cache_path, user_data_path


@dataclass(frozen=True, slots=True)
class ToolPaths:
    native: Path
    pm3: Path
    data_root: Path
    cache_root: Path

    @classmethod
    def discover(cls) -> ToolPaths:
        prefix = Path(os.environ.get("RC522_MFC_PREFIX", Path.home() / ".local" / "lib" / "rc522-mfc"))
        native = Path(os.environ.get("RC522_MFC_NATIVE", prefix / "bin" / "rc522-mfc-native"))
        pm3 = Path(os.environ.get("RC522_MFC_PM3", prefix / "proxmark3" / "pm3"))
        return cls(
            native=native.expanduser().resolve(),
            pm3=pm3.expanduser().resolve(),
            data_root=user_data_path("rc522-mfc", appauthor=False),
            cache_root=user_cache_path("rc522-mfc", appauthor=False),
        )

    def card_dir(self, uid: str) -> Path:
        return self.data_root / "cards" / uid.upper()
