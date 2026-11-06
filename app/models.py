from dataclasses import asdict, dataclass, field
from enum import Enum


class Level(str, Enum):
    HIGH = "high"            # strong evidence of a scam
    CAUTION = "caution"      # several red flags
    LOW = "low"              # no red flags found (never "safe")
    UNVERIFIED = "unverified"  # could not load or check


@dataclass
class Signal:
    code: str
    weight: int
    en: str            # reason shown to the user, English
    sw: str            # reason shown to the user, Swahili
    strong: bool = False  # one strong signal is enough for HIGH


@dataclass
class CheckResult:
    input: str
    final_url: str | None = None
    chain: list[str] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    entities: dict[str, list[str]] = field(default_factory=dict)
    score: int = 0
    level: Level = Level.UNVERIFIED
    fetched: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["level"] = self.level.value
        return d
