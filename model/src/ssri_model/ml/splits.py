"""Deterministic dataset split utilities for SSRI."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal, Sequence

from ssri_model.ml.constants import DEFAULT_RANDOM_SEED, DEFAULT_SPLIT

SplitName = Literal["train", "validation", "test"]


@dataclass(frozen=True)
class SplitConfig:
    """Configuration for deterministic train/validation/test splits."""

    train: float = DEFAULT_SPLIT["train"]
    validation: float = DEFAULT_SPLIT["validation"]
    test: float = DEFAULT_SPLIT["test"]
    random_seed: int = DEFAULT_RANDOM_SEED

    def __post_init__(self) -> None:
        total = self.train + self.validation + self.test
        if abs(total - 1.0) > 1e-9:
            raise ValueError(
                f"Split proportions must sum to 1.0, received {total:.6f}"
            )
        for name, value in (
            ("train", self.train),
            ("validation", self.validation),
            ("test", self.test),
        ):
            if value < 0:
                raise ValueError(f"Split proportion '{name}' must be non-negative")


@dataclass(frozen=True)
class DatasetSplit:
    """Deterministic partition of sample identifiers."""

    train: tuple[str, ...]
    validation: tuple[str, ...]
    test: tuple[str, ...]

    @property
    def counts(self) -> dict[SplitName, int]:
        """Return the number of samples in each split."""
        return {
            "train": len(self.train),
            "validation": len(self.validation),
            "test": len(self.test),
        }


def split_sample_ids(
    sample_ids: Sequence[str],
    config: SplitConfig | None = None,
) -> DatasetSplit:
    """Split sample identifiers deterministically into train/validation/test.

    Args:
        sample_ids: Unique sample identifiers to partition.
        config: Optional split configuration. Defaults to ``SplitConfig()``.

    Returns:
        ``DatasetSplit`` with deterministic sample identifier partitions.
    """
    cfg = config or SplitConfig()
    unique_ids = sorted(set(sample_ids))
    total = len(unique_ids)

    if total == 0:
        return DatasetSplit(train=(), validation=(), test=())

    rng = random.Random(cfg.random_seed)
    shuffled = unique_ids.copy()
    rng.shuffle(shuffled)

    train_count = int(total * cfg.train)
    validation_count = int(total * cfg.validation)
    assigned = train_count + validation_count
    test_count = total - assigned

    # Assign remainder to test so all samples are included.
    if assigned + test_count != total:
        test_count = total - assigned

    train = tuple(shuffled[:train_count])
    validation = tuple(shuffled[train_count : train_count + validation_count])
    test = tuple(shuffled[train_count + validation_count :])

    return DatasetSplit(train=train, validation=validation, test=test)
