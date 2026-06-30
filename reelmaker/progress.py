from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_PROGRESS_PREFIX = "@@REELMAKER_PROGRESS@@"


def default_timing_history_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Reelmaker" / "timing_history.json"
    return Path.home() / ".reelmaker" / "timing_history.json"


class TimingHistory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_timing_history_path()
        self.data: dict[str, Any] = {"version": 1, "metrics": {}}
        self._load()

    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("metrics"), dict):
                self.data = raw
        except Exception:
            pass

    def estimate_seconds(self, key: str, units: float) -> float | None:
        samples = self.data.get("metrics", {}).get(key, {}).get("seconds_per_unit", [])
        valid = [float(value) for value in samples if isinstance(value, (int, float)) and value > 0]
        if not valid or units <= 0:
            return None
        return statistics.median(valid[-20:]) * units

    def record(self, key: str, *, elapsed_seconds: float, units: float) -> None:
        if elapsed_seconds <= 0 or units <= 0:
            return
        metrics = self.data.setdefault("metrics", {})
        entry = metrics.setdefault(key, {"seconds_per_unit": []})
        samples = entry.setdefault("seconds_per_unit", [])
        samples.append(round(elapsed_seconds / units, 6))
        entry["seconds_per_unit"] = samples[-20:]
        entry["updated_at"] = int(time.time())
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass


@dataclass
class StageState:
    name: str
    label: str
    total: float
    history_key: str | None
    history_units: float
    started_at: float = field(default_factory=time.monotonic)
    completed: float = 0.0
    initial_estimate: float | None = None


class ProgressReporter:
    """Emit machine-readable progress while keeping the CLI human-readable."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        history_path: Path | None = None,
        use_history: bool = True,
    ) -> None:
        self.enabled = enabled
        self.history = TimingHistory(history_path) if use_history else None
        self.stage: StageState | None = None
        self.run_started_at = time.monotonic()

    def _emit(self, event: dict[str, Any]) -> None:
        if not self.enabled:
            return
        payload = {
            "timestamp": time.time(),
            "run_elapsed_seconds": round(time.monotonic() - self.run_started_at, 2),
            **event,
        }
        print(_PROGRESS_PREFIX + json.dumps(payload, ensure_ascii=False), flush=True)

    def start_stage(
        self,
        name: str,
        label: str,
        *,
        total: float = 1.0,
        history_key: str | None = None,
        history_units: float | None = None,
    ) -> None:
        units = float(history_units if history_units is not None else total)
        estimate = self.history.estimate_seconds(history_key, units) if self.history and history_key else None
        self.stage = StageState(
            name=name,
            label=label,
            total=max(0.0001, float(total)),
            history_key=history_key,
            history_units=max(0.0001, units),
            initial_estimate=estimate,
        )
        self._emit(
            {
                "event": "stage_start",
                "stage": name,
                "label": label,
                "current": 0,
                "total": self.stage.total,
                "progress": 0.0,
                "eta_seconds": round(estimate, 1) if estimate is not None else None,
            }
        )

    def update(self, current: float, *, message: str | None = None) -> None:
        if self.stage is None:
            return
        self.stage.completed = max(0.0, min(float(current), self.stage.total))
        elapsed = time.monotonic() - self.stage.started_at
        progress = self.stage.completed / self.stage.total
        eta: float | None = None
        if progress > 0.02:
            eta = max(0.0, elapsed * (1.0 - progress) / progress)
        elif self.stage.initial_estimate is not None:
            eta = max(0.0, self.stage.initial_estimate - elapsed)
        self._emit(
            {
                "event": "stage_progress",
                "stage": self.stage.name,
                "label": self.stage.label,
                "current": round(self.stage.completed, 3),
                "total": round(self.stage.total, 3),
                "progress": round(progress, 4),
                "stage_elapsed_seconds": round(elapsed, 2),
                "eta_seconds": round(eta, 1) if eta is not None else None,
                "message": message or "",
            }
        )

    def finish_stage(self, *, record_history: bool = True, message: str | None = None) -> None:
        if self.stage is None:
            return
        elapsed = time.monotonic() - self.stage.started_at
        self.stage.completed = self.stage.total
        self._emit(
            {
                "event": "stage_end",
                "stage": self.stage.name,
                "label": self.stage.label,
                "current": self.stage.total,
                "total": self.stage.total,
                "progress": 1.0,
                "stage_elapsed_seconds": round(elapsed, 2),
                "eta_seconds": 0.0,
                "message": message or "",
            }
        )
        if record_history and self.history and self.stage.history_key:
            self.history.record(
                self.stage.history_key,
                elapsed_seconds=elapsed,
                units=self.stage.history_units,
            )
        self.stage = None

    def fail(self, message: str) -> None:
        self._emit({"event": "run_error", "message": message})

    def finish_run(self, *, success: bool = True, message: str = "") -> None:
        self._emit(
            {
                "event": "run_end",
                "success": success,
                "message": message,
                "progress": 1.0 if success else None,
            }
        )


PROGRESS_PREFIX = _PROGRESS_PREFIX
