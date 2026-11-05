"""使い魔の召喚: 新しい cse-frog を1匹生み、詠唱を「言葉のかたまり」単位で覚えさせ、1つ唱えさせて消す。

カエル本体（cse-frog）には手を入れない。ここで作るのはくじの引き方（サンプラー）だけ:
- カエルの予測確率（<END> を含む）に比例して引く。並びを決めてから引くので seed で再現できる。
- 同じかたまりは2回まで続けて良い（3回目は外す）。吸い込まれ対策（曲・顔文字・模様と同じ考え方）。
- 「！」「!」「。」か <END> が出たら唱え終わり。MAX_CHUNKS で打ち切り。
生成された詠唱は改変しない（仕様書 MVP 合格条件7）。
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from cse import END, Frog

from .chunks import chunk

FROG_KW = dict(temperature=0.9, probability_mode="linear", top_k_edges=8)
EPOCHS = 5
MAX_CHUNKS = 14
ENDERS = {"！", "!", "。"}


@dataclass
class Summoned:
    text: str
    chunks: list[str]
    seed: int
    copied: bool            # 学習した詠唱のどれかとまったく同じか


def _pick(probs: dict, rng: random.Random):
    r, acc, k = rng.random() * sum(probs.values()), 0.0, None
    for k, v in sorted(probs.items(), key=lambda kv: str(kv[0])):
        acc += v
        if r < acc:
            return k
    return k


def summon(spells: list[str], seed: int) -> Summoned:
    """spells を覚えた新しいカエルに1つ唱えさせる。spells が空なら ValueError。"""
    seqs = [c for c in (chunk(s) for s in spells) if c]
    if not seqs:
        raise ValueError("覚える詠唱がない")
    rng = random.Random(f"summon:{seed}")
    frog = Frog(**FROG_KW)
    frog.learn(seqs, epochs=EPOCHS)
    starts = sorted({s[0] for s in seqs})
    out = [rng.choice(starts)]
    while len(out) < MAX_CHUNKS and out[-1] not in ENDERS:
        probs = {k: v for k, v in frog.probabilities(out[-2:]).items()
                 if v > 0 and (k is END or isinstance(k, str))}
        if len(out) >= 2 and out[-1] == out[-2]:
            probs.pop(out[-1], None)
        if not probs:
            break
        k = _pick(probs, rng)
        if k is END:
            break
        out.append(k)
    text = "".join(out)
    return Summoned(text=text, chunks=out, seed=seed, copied=text in set(spells))
