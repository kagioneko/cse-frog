"""モードA: 魔法実験室（CLI）。

  python -m familiar teach "炎よ、敵を焼き尽くせ！"     詠唱を教える（data/memory.json）
  python -m familiar summon [-n 3] [--seed S] [--goal attack|heal] [--no-seeds]
                                                         使い魔を召喚して唱えさせ、判定する（data/log.jsonl に記録）
  python -m familiar cast "氷よ、敵を癒せ！" [--goal …] [--seed S]  詠唱を直接判定する（カエルなし）
  python -m familiar list                                教えた詠唱を見る

学習データ = お手本の詠唱（seeds.py）＋教えた詠唱。--no-seeds で教えた詠唱だけにする。
同じ学習データ（version）・seed・goal なら、生成も判定も同じになる。
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from pathlib import Path

from .magic import GOALS, judge, parse
from .memory import SpellMemory, version
from .seeds import SEED_SPELLS
from .summon import summon

DATA = Path("data")


def corpus(mem: SpellMemory, use_seeds: bool = True) -> list[str]:
    return (list(SEED_SPELLS) if use_seeds else []) + [t for t in mem.texts() if t not in SEED_SPELLS]


def run_summon(spells: list[str], seed: int, goal: str) -> dict:
    s = summon(spells, seed)
    r = judge(parse(s.text), goal, seed)
    return {"dataset_version": version(spells), "seed": seed, "goal": goal,
            "spell": s.text, "chunks": s.chunks, "copied": s.copied,
            "verdict": r.verdict, "effect": r.effect, "parsed": r.parsed, "lines": r.lines}


def main(argv=None, data: Path = DATA, out=print) -> int:
    p = argparse.ArgumentParser(prog="familiar")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("teach")
    t.add_argument("text")
    s = sub.add_parser("summon")
    s.add_argument("-n", type=int, default=1)
    s.add_argument("--seed", type=int)
    s.add_argument("--goal", choices=GOALS, default="attack")
    s.add_argument("--no-seeds", action="store_true")
    c = sub.add_parser("cast")
    c.add_argument("text")
    c.add_argument("--goal", choices=GOALS, default="attack")
    c.add_argument("--seed", type=int, default=0)
    sub.add_parser("list")
    a = p.parse_args(argv)
    mem = SpellMemory(data / "memory.json")

    if a.cmd == "teach":
        ok, msg = mem.add(a.text)
        out(("🐸 " if ok else "🐸💦 ") + msg)
        return 0 if ok else 1
    if a.cmd == "list":
        for x in mem.load():
            out(f"{x['id']:>4}  {x['text']}")
        return 0
    if a.cmd == "cast":
        for line in judge(parse(a.text), a.goal, a.seed).lines:
            out(line)
        return 0
    spells = corpus(mem, not a.no_seeds)
    if not spells:
        out("🐸💦 覚える詠唱がない（teach で教えてね）")
        return 1
    if not 1 <= a.n <= 20:
        out("-n は 1〜20")
        return 2
    base = a.seed if a.seed is not None else secrets.randbelow(1 << 30)
    data.mkdir(parents=True, exist_ok=True)
    out(f"（学習した詠唱 {len(spells)} 個 / データ版 {version(spells)}）")
    for i in range(a.n):
        rec = run_summon(spells, base + i, a.goal)
        rec["at"] = time.time()
        with open(data / "log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out(f"--- 召喚 seed={rec['seed']}" + ("（覚えた詠唱そのまま）" if rec["copied"] else ""))
        for line in rec["lines"]:
            out(line)
        out("🐸 …（使い魔は消えた）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
