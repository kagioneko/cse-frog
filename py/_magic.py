"""魔法実験室ページ用の橋渡し。JS とは JSON 文字列でやりとりする。

中身は cse-frog-familiar（familiar パッケージ）そのもの。ここでは入力の検査と呼び出しだけをする。
教えた詠唱はブラウザ側（JS）が持っていて、召喚のたびに渡される。どこにも送信しない。
"""
import json

from familiar.lab import run_summon
from familiar.magic import GOALS, cast as _cast
from familiar.memory import MAX_LEN, check as _check
from familiar.seeds import SEED_SPELLS

MAX_TAUGHT = 200


def seeds(_arg="{}"):
    return json.dumps(SEED_SPELLS, ensure_ascii=False)


def check(arg):
    a = json.loads(arg)
    return json.dumps({"reason": _check(a.get("text"))}, ensure_ascii=False)


def _goal(a):
    g = a.get("goal", "attack")
    if g not in GOALS:
        raise ValueError("goal")
    return g


def _seed(a):
    s = a.get("seed")
    if not isinstance(s, int) or isinstance(s, bool) or not 0 <= s < 2 ** 31:
        raise ValueError("seed は 0〜2147483647 の整数")
    return s


def summon(arg):
    a = json.loads(arg)
    taught = a.get("taught") or []
    if not isinstance(taught, list) or len(taught) > MAX_TAUGHT:
        raise ValueError("教えた詠唱が多すぎます")
    taught = [t.strip() for t in taught if isinstance(t, str) and _check(t) is None]
    spells = (list(SEED_SPELLS) if a.get("use_seeds", True) else []) + \
        [t for t in taught if t not in SEED_SPELLS]
    if not spells:
        raise ValueError("覚える詠唱がありません（詠唱を教えるか、お手本を使ってください）")
    rec = run_summon(spells, _seed(a), _goal(a))
    rec["count"] = len(spells)
    return json.dumps(rec, ensure_ascii=False)


def cast(arg):
    a = json.loads(arg)
    text = a.get("text")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_LEN:
        raise ValueError(f"1〜{MAX_LEN}文字で入力してください")
    r = _cast(text.strip(), _goal(a), _seed(a))
    return json.dumps({"verdict": r.verdict, "lines": r.lines, "effect": r.effect}, ensure_ascii=False)
