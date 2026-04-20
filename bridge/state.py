"""Phase state tracking persisted to state.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

PHASES = ("detect", "fetch", "configure", "install", "validate")


class PhaseStatus(str, Enum):
    PENDING = "pending"
    OK = "ok"
    FAILED = "failed"


@dataclass
class PhaseRecord:
    status: PhaseStatus = PhaseStatus.PENDING
    inputs_hash: Optional[str] = None
    ran_at: Optional[str] = None
    error: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "inputs_hash": self.inputs_hash,
            "ran_at": self.ran_at,
            "error": self.error,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PhaseRecord":
        return cls(
            status=PhaseStatus(d.get("status", "pending")),
            inputs_hash=d.get("inputs_hash"),
            ran_at=d.get("ran_at"),
            error=d.get("error"),
            extra=d.get("extra", {}),
        )


class State:
    def __init__(self, path: Path):
        self.path = path
        self.version = 1
        self.phases: dict[str, PhaseRecord] = {p: PhaseRecord() for p in PHASES}
        self.paths: dict[str, str] = {}
        self.secrets: dict[str, str] = {}

    @classmethod
    def load(cls, path: Path) -> "State":
        s = cls(path)
        if not path.exists():
            return s
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return s
        s.version = data.get("version", 1)
        for name, rec in data.get("phases", {}).items():
            if name in s.phases:
                s.phases[name] = PhaseRecord.from_dict(rec)
        s.paths = dict(data.get("paths", {}))
        s.secrets = dict(data.get("secrets", {}))
        return s

    def save(self) -> None:
        data = {
            "version": self.version,
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
            "paths": self.paths,
            "secrets": self.secrets,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2))

    def get_phase(self, name: str) -> PhaseRecord:
        return self.phases[name]

    def set_phase(
        self,
        name: str,
        status: PhaseStatus,
        inputs_hash: Optional[str] = None,
        error: Optional[str] = None,
        **extra,
    ) -> None:
        from datetime import datetime, timezone
        self.phases[name] = PhaseRecord(
            status=status,
            inputs_hash=inputs_hash,
            ran_at=datetime.now(timezone.utc).isoformat(),
            error=error,
            extra=extra,
        )

    def should_run(
        self, name: str, inputs_hash: Optional[str] = None, force: bool = False
    ) -> bool:
        if force:
            return True
        rec = self.phases[name]
        if rec.status != PhaseStatus.OK:
            return True
        if inputs_hash is not None and rec.inputs_hash != inputs_hash:
            return True
        return False

    def set_path(self, key: str, value: str) -> None:
        self.paths[key] = value

    def get_path(self, key: str) -> Optional[str]:
        return self.paths.get(key)

    def set_secret(self, key: str, value: str) -> None:
        self.secrets[key] = value

    def get_secret(self, key: str) -> Optional[str]:
        return self.secrets.get(key)
