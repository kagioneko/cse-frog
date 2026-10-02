# DRAFT NOTES (chainspike 0.0.1.dev0, scratchpad draft — not published, not in any git repo)

## Provenance
- `src/chainspike/_engine.py` = unchanged copy of `course/cse_course_engine.py`, sha256 `a7af714753e4e0a260b354fd280f77444f93b44957b2e2af432b04bc8f2d87c9` (copy verified identical). The research `cse/` package and `chain_spike_phase0.py` are NOT included.
- Offline wheel build (`pip wheel . --no-deps --no-build-isolation --no-index`) contains only `chainspike/__init__.py`, `chainspike/_engine.py` + dist-info.

## Decisions the owner must make
1. Final PyPI name (`chainspike` is a placeholder; as of 2026-10-03 `chain-spike`, `chainspike`, `chain-spike-engine`, `frog-lm` were unregistered).
2. License (placeholder "MIT (pending owner decision)"; newer setuptools prefer an SPDX string `license = "MIT"` + `license-files`).
3. FTO by a patent attorney before commercial use, scoped to the course-engine feature set.
4. Default settings for beginners (currently refractory 0, history_boost 0, pair_context 2048/1.0, max_nodes 256).
5. How to represent "end of sequence" (currently `None`, exported as `chainspike.END`).
6. Whether the research-equivalence test of the course engine should be referenced in docs (it is not shipped).

## Engine quirks found
- The course engine allocates `max_nodes x max_nodes` float32 matrices at construction (two of them), so `max_nodes` caps the vocabulary; `Frog` sets 256 (~0.5 MB) and raises a Japanese error if the token count exceeds `max_nodes - 3`.
- The engine is character-level (`encode` iterates characters); `Frog` maps each distinct user token to one private-use character (U+E000+).
- Engine defaults (`refractory_steps=2`, `history_boost=0.35`, no pair context) give surprising predictions on repeat-heavy sequences (e.g. after 右右下 the default predicts `<END>`); `refractory_steps=0` alone predicts 右 after 右右 (0.997). Pair context is needed for 右右→下.
- `next_node_distribution` re-primes the engine (mutates transient state) on every call; fine for single-threaded use, not thread-safe.
- `ChainSpikeEngine.__init__` calls `random.seed`/`np.random.seed` globally (side effect on the user's global RNG). Worth documenting or wrapping before release.
- `Frog.probabilities` drops `<START>`/`<UNK>` and renormalizes; `<UNK>` can only get mass if `max_nodes` overflow mapped tokens to it (prevented by the wrapper's limit).
- `learn()` on a list of strings treats each string as a character sequence; multi-character words need a list of lists. Documented in the class docstring and README.
