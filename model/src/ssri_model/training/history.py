"""Training history tracking for SSRI."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EpochRecord:
    """Metrics recorded for a single training epoch."""

    epoch: int
    train_loss: float
    validation_loss: float
    learning_rate: float
    accuracy: float
    macro_f1: float
    mean_iou: float
    epoch_seconds: float = 0.0

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> EpochRecord:
        """Restore an epoch record, accepting legacy field names."""
        return cls(
            epoch=int(payload["epoch"]),
            train_loss=float(payload["train_loss"]),
            validation_loss=float(payload["validation_loss"]),
            learning_rate=float(payload["learning_rate"]),
            accuracy=float(
                payload.get("accuracy", payload.get("validation_accuracy", 0.0))
            ),
            macro_f1=float(
                payload.get("macro_f1", payload.get("validation_mean_f1", 0.0))
            ),
            mean_iou=float(
                payload.get("mean_iou", payload.get("validation_mean_iou", 0.0))
            ),
            epoch_seconds=float(payload.get("epoch_seconds", 0.0)),
        )


@dataclass
class TrainingHistory:
    """Structured, JSON-serializable training history."""

    epochs: list[EpochRecord] = field(default_factory=list)
    best_epoch: int | None = None
    best_metric: float | None = None
    best_metric_name: str | None = None
    total_epochs: int = 0

    def add_epoch(self, record: EpochRecord) -> None:
        """Append an epoch record to the history."""
        self.epochs.append(record)
        self.total_epochs = len(self.epochs)

    def update_best(
        self,
        *,
        epoch: int,
        metric_value: float,
        metric_name: str,
        higher_is_better: bool,
    ) -> bool:
        """Update best-metric tracking and return True when improved."""
        if self.best_metric is None:
            self.best_epoch = epoch
            self.best_metric = metric_value
            self.best_metric_name = metric_name
            return True

        improved = (
            metric_value > (self.best_metric + 0.0)
            if higher_is_better
            else metric_value < self.best_metric
        )
        if improved:
            self.best_epoch = epoch
            self.best_metric = metric_value
            self.best_metric_name = metric_name
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable history dictionary."""
        return {
            "epochs": [asdict(record) for record in self.epochs],
            "best_epoch": self.best_epoch,
            "best_metric": self.best_metric,
            "best_metric_name": self.best_metric_name,
            "total_epochs": self.total_epochs,
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize the training history to JSON."""
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TrainingHistory:
        """Restore training history from a serialized dictionary."""
        records = [EpochRecord.from_dict(record) for record in payload.get("epochs", [])]
        return cls(
            epochs=records,
            best_epoch=payload.get("best_epoch"),
            best_metric=payload.get("best_metric"),
            best_metric_name=payload.get("best_metric_name"),
            total_epochs=int(payload.get("total_epochs", len(records))),
        )

    def save_json(self, path: Path) -> None:
        """Write training history to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load_json(cls, path: Path) -> TrainingHistory:
        """Load training history from a JSON file."""
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    @property
    def best_validation_loss(self) -> float | None:
        """Return the lowest validation loss observed in history."""
        if not self.epochs:
            return None
        return min(record.validation_loss for record in self.epochs)
