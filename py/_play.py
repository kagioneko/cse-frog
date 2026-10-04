"""ブラウザ体験ページ用の小さな橋渡し。JS とは JSON 文字列でやりとりする。"""
import dataclasses
import json
import random

from cse import END, Frog

state = {"frog": None, "mode": "chars"}
# 「コードを書く」タブの名前空間。つまみで作った 🐸 は frog という名前で入る
user_ns = {"__name__": "__main__", "Frog": Frog, "END": END}


def _tok(x):
    return "<END>" if x is END else str(x)


def _sequences(text, mode):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if mode == "chars":
        return [list(ln) for ln in lines]
    return [ln.split() for ln in lines]


def _prefix(text, mode):
    text = text.strip()
    return list(text) if mode == "chars" else text.split()


def _need_frog():
    if state["frog"] is None:
        raise ValueError("まだ 🐸 がいません。先に「覚えさせる」を押してください。")
    return state["frog"]


def setup(arg):
    a = json.loads(arg)
    seqs = _sequences(a["data"], a["mode"])
    if not seqs:
        raise ValueError("えさ(学習データ)が空です。1行に1本ずつ系列を書いてください。")
    frog = Frog(**a["config"])
    frog.learn(seqs, epochs=int(a["epochs"]))
    state.update(frog=frog, mode=a["mode"])
    user_ns["frog"] = frog
    symbols = sorted(_tok(t) for t in frog._to_token.values())
    return json.dumps({"count": len(symbols), "symbols": symbols[:300],
                       "config": dataclasses.asdict(frog.config)}, ensure_ascii=False)


def explain(arg):
    a = json.loads(arg)
    frog = _need_frog()
    prefix = _prefix(a["prefix"], state["mode"])
    rows = frog.explain(prefix, k=int(a.get("k", 6)))
    for r in rows:
        r["token"] = _tok(r["token"])
    top = frog.top(prefix, k=1)
    return json.dumps({"prefix": [_tok(t) for t in prefix], "rows": rows,
                       "predict": _tok(top[0][0]) if top else "<END>"}, ensure_ascii=False)


def generate(arg):
    a = json.loads(arg)
    frog = _need_frog()
    seq = _prefix(a["prefix"], state["mode"])
    rng = random.Random(int(a.get("seed", 0)))
    out = []
    for _ in range(max(1, min(int(a.get("n", 20)), 200))):
        probs = frog.probabilities(seq)
        if not probs:
            break
        if a.get("how") == "sample":
            toks, weights = zip(*probs.items())
            nxt = rng.choices(toks, weights=weights)[0]
        else:
            nxt = max(probs.items(), key=lambda kv: kv[1])[0]
        if nxt is END:
            out.append("<END>")
            break
        out.append(_tok(nxt))
        seq = list(seq) + [nxt]
    return json.dumps({"tokens": out}, ensure_ascii=False)


def edges(arg):
    a = json.loads(arg)
    frog = _need_frog()
    return json.dumps({"edges": [[_tok(t), w] for t, w in frog.edges(a["token"], k=8)]}, ensure_ascii=False)
