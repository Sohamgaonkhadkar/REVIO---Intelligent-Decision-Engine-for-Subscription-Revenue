"""Deterministic randomness.

Two primitives only:
  stream_rng(master_seed, name)      -> order-independent named stream
  keyed(master_seed, *keys)          -> content-addressable Generator
Everything else in the project draws through these. The stdlib `random`
module is banned. Keyed streams make the same (customer, day, purpose)
produce the same draw in every policy run (common random numbers).
"""

import hashlib

import numpy as np


def _key_int(*keys) -> int:
    digest = hashlib.blake2b("|".join(map(str, keys)).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "little")


def stream_rng(master_seed: int, stream_name: str) -> np.random.Generator:
    child = np.random.SeedSequence([master_seed, _key_int(stream_name) % (2**31)])
    return np.random.Generator(np.random.PCG64(child))


def keyed(master_seed: int, *keys) -> np.random.Generator:
    child = np.random.SeedSequence([master_seed, _key_int(*keys) % (2**31)])
    return np.random.Generator(np.random.PCG64(child))
