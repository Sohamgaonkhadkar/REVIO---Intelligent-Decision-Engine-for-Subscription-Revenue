"""Determinism core — keyed RNG (recoverysim pattern, DATASET_BUILD_REPORT §3).

Every stochastic draw is content-addressable: keyed(seed_key, *labels) →
blake2b digest → PCG64 stream. Same key ⇒ same draws ⇒ the same seeded world
behaves identically across runs (paired policy comparisons depend on this).
"""
from __future__ import annotations

import hashlib
from typing import Sequence

import numpy as np


def stream(seed_key: str, *labels: Sequence[str | int | float]) -> np.random.Generator:
    digest = hashlib.blake2b(
        "|".join([seed_key, *[str(x) for x in labels]]).encode(), digest_size=16
    ).digest()
    return np.random.Generator(np.random.PCG64(np.frombuffer(digest, dtype=np.uint64)))


def uniform(seed_key: str, *labels: Sequence[str | int | float]) -> float:
    return float(stream(seed_key, "uniform", *labels).random())


def bernoulli(seed_key: str, p: float, *labels: Sequence[str | int | float]) -> bool:
    if p <= 0.0:
        return False
    if p >= 1.0:
        return True
    return bool(uniform(seed_key, "bern", p, *labels) < p)
