"""cse — 順番のあるデータを覚えて「次に何が来そうか」を予測する、小さな学習用AI。

中身は Chain-Spike Engine (CSE) 講座版エンジン(`_engine.py`、無変更)です。
このファイルは、初心者がつまずきやすい点を吸収する薄い入口 `Frog` だけを足しています。

    from cse import Frog
    frog = Frog()
    frog.learn([["右", "右", "下"]] * 10)
    frog.predict(["右", "右"])        # -> "下"
"""
from __future__ import annotations

import dataclasses
import io
import json
import random
import threading
import zipfile
from pathlib import Path
from typing import Dict, Hashable, Iterable, List, Optional, Sequence, Union

import numpy as np

from ._engine import ChainSpikeEngine, CSEConfig

__all__ = ["Frog", "END"]
__version__ = "0.0.1.dev0"

class _EndMarker:
    """「ここで系列が終わる」を表す特別な目印。表示は <END>。利用者の記号(文字列など)とはぶつかりません。"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<END>"

    __str__ = __repr__

    def __reduce__(self):
        return (_EndMarker, ())


#: 「ここで系列が終わる」を表す値。predict() が END を返したら「もう続きはなさそう」という意味です。
END = _EndMarker()

# 素直に予測するための既定の設定。変えるのは下の5項目だけで、他はエンジン(講座版)の既定値のまま
# (注意: 研究の107の構成とは別物。107はlinear・top_k_edges=50などで、講座版エンジンにはbackoffの混合もない)
#  - refractory_steps=0 : 直前に出た記号を一時的に出さない仕組み(不応期)を切る
#                         (切らないと「右右下」の次に右を予測できない、などの変な挙動になる)
#  - history_boost=0.0  : 活性の履歴で点数を盛る仕組みを切る
#  - pair_context_*     : 直前2つの並びを覚える(「右右」の次は「下」を覚えるのに必要)
_SAFE_DEFAULTS = dict(
    refractory_steps=0,
    history_boost=0.0,
    pair_context_capacity=2048,
    pair_context_boost=1.0,
    max_nodes=256,
)

_SPECIAL = ("<START>", "<END>", "<UNK>")
_PRIVATE_USE_BASE = 0xE000

Token = Hashable
SequenceLike = Union[str, Sequence[Token]]


class Frog:
    """🐸 小さな予測AIを1匹つくります。

    Frog(**overrides) で、エンジンの設定(CSEConfig の項目)を上書きできます。
    何も指定しなければ、素直に予測する設定になります。

    系列の渡し方:
      - 文字列 "右右下"            → 1文字ずつの系列として扱います
      - リスト ["正常", "停止"]     → 1要素を1つの記号として扱います(「停止」は「停」と「止」に分かれません)
    """

    def __init__(self, **overrides):
        known = set(CSEConfig.__dataclass_fields__)
        unknown = sorted(set(overrides) - known)
        if unknown:
            raise ValueError(f"知らない設定の名前です: {unknown}。使える名前: {sorted(known)}")
        settings = dict(_SAFE_DEFAULTS)
        settings.update(overrides)
        self.config = CSEConfig(**settings)
        # エンジンは作られるときに random.seed / np.random.seed をプロセス全体に対して呼ぶ。
        # 利用者の乱数を巻き込まないよう、作る前の乱数の状態を保存して、作った後に元へ戻す。
        py_state, np_state = random.getstate(), np.random.get_state()
        try:
            self._engine = ChainSpikeEngine(self.config)
        finally:
            random.setstate(py_state)
            np.random.set_state(np_state)
        # エンジンは予測のたびに内部の状態(活性など)を書き換えるので、同じ Frog を複数のスレッドから
        # 同時に使っても壊れないよう、学習と予測を1つずつ順番に通す。
        self._lock = threading.Lock()
        self._to_char: Dict[Token, str] = {}
        self._to_token: Dict[str, Token] = {}

    # ------------------------------------------------------------ 内部の変換
    @staticmethod
    def _as_tokens(seq: SequenceLike) -> List[Token]:
        if isinstance(seq, str):
            return list(seq)
        return list(seq)

    def _encode(self, tokens: Iterable[Token], allow_new: bool) -> str:
        chars = []
        for tok in tokens:
            if tok not in self._to_char:
                if not allow_new:
                    raise ValueError(f"「{tok}」はまだ覚えていない記号です。learn() で覚えさせてから使ってください。")
                limit = self.config.max_nodes - len(_SPECIAL)
                if len(self._to_char) >= limit:
                    raise ValueError(f"覚えられる記号の数({limit})をこえました。Frog(max_nodes=…) で大きくしてください。")
                ch = chr(_PRIVATE_USE_BASE + len(self._to_char))
                self._to_char[tok] = ch
                self._to_token[ch] = tok
            chars.append(self._to_char[tok])
        return "".join(chars)

    # ------------------------------------------------------------ 公開API
    def learn(self, data, epochs: int = 3) -> "Frog":
        """系列を覚えます。渡し方は3通りです(predict と同じ考え方)。

        - 文字列1つ        frog.learn("右右下右右下")                 → 1本の系列。1文字が1記号
        - リスト1つ        frog.learn(["正常", "温度上昇", "停止"])    → 1本の系列。1要素が1記号
        - リストのリスト   frog.learn([["右", "右", "下"], ["正常", "停止"]])  → 何本もの系列

        epochs は同じデータを何周くり返して覚えるか(既定 3)。多いほど強く覚えます。
        """
        sequences = self._as_sequences(data)
        with self._lock:                       # 記号の対応表の更新も含めて1つずつ
            texts = [self._encode(self._as_tokens(s), allow_new=True) for s in sequences]
            self._engine.train_corpus([t for t in texts if t], epochs=epochs)
        return self

    @staticmethod
    def _as_sequences(data) -> List[SequenceLike]:
        """learn() の入力を「系列のリスト」にそろえる。"""
        if isinstance(data, str):
            return [data]
        items = list(data)
        nested = [isinstance(x, (list, tuple)) for x in items]
        if items and all(nested):
            return items                       # リストのリスト = 何本もの系列
        if any(nested):
            raise ValueError("リストの中に、リストとそれ以外がまざっています。"
                             "1本だけなら [\"右\", \"右\", \"下\"]、何本もなら [[...], [...]] のようにそろえてください。")
        return [items]                         # リスト1つ = 1本の系列(1要素が1記号)

    def probabilities(self, prefix: SequenceLike = ()) -> Dict[Token, float]:
        """prefix の次に来る記号の確率を返します。キー END(表示は <END>)は「ここで終わり」。

        確率の合計は 1 です(<START>・<UNK> は除いて、残りで割り直しています)。
        """
        with self._lock:                       # 対応表の読み取り・エンジンの予測・読み戻しを1つずつ
            text = self._encode(self._as_tokens(prefix), allow_new=False)
            raw = self._engine.next_node_distribution(text)
            out: Dict[Token, float] = {}
            for sym, p in raw.items():
                if sym in ("<START>", "<UNK>"):
                    continue
                key = END if sym == "<END>" else self._to_token[sym]
                out[key] = out.get(key, 0.0) + p
        total = sum(out.values())
        if total <= 0:
            return {END: 1.0}
        return {k: v / total for k, v in out.items()}

    # ------------------------------------------------------------ 保存と読み込み
    _FORMAT = "cse-frog/1"
    _TOKEN_TYPES = (str, int, float, bool, type(None))

    def save(self, path) -> None:
        """覚えたことをファイルに保存します(例: frog.save("my_frog.cse"))。

        中身は JSON と数値の配列だけです(pickle は使いません。他の人の 🐸 を読み込んでも安全です)。
        記号として使えるのは 文字列・整数・小数・True/False・None です。
        """
        with self._lock:
            tokens = list(self._to_char)
            bad = [t for t in tokens if type(t) not in self._TOKEN_TYPES]
            if bad:
                raise ValueError(f"保存できない種類の記号があります: {bad[:3]}。文字列・数・True/False・None だけが保存できます。")
            e = self._engine
            pair_keys = list(e.pair_context_weights)          # 入れた順番も保存する(容量が一杯のときの追い出しに効く)
            meta = {"format": self._FORMAT, "cse_version": __version__,
                    "config": dataclasses.asdict(self.config),
                    "tokens": [[t, self._to_char[t]] for t in tokens],
                    "id_to_symbol": list(e.id_to_symbol),
                    "recent_fired": list(e.recent_fired),
                    "total_training_steps": int(e.total_training_steps),
                    "pair_keys": [list(k) for k in pair_keys]}
            arrays = {"weights": e.weights, "context_weights": e.context_weights, "activation": e.activation,
                      "context_trace": e.context_trace, "frequency": e.frequency,
                      "pair_rows": (np.stack([e.pair_context_weights[k] for k in pair_keys]) if pair_keys
                                    else np.zeros((0, self.config.max_nodes), dtype=np.float32))}
            path = Path(path)
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("meta.json", json.dumps(meta, ensure_ascii=False))
                for name, arr in arrays.items():
                    buf = io.BytesIO()
                    np.save(buf, np.ascontiguousarray(arr), allow_pickle=False)
                    z.writestr(f"{name}.npy", buf.getvalue())

    @classmethod
    def load(cls, path) -> "Frog":
        """save() したファイルから 🐸 を読み込みます(例: frog = Frog.load("my_frog.cse"))。"""
        with zipfile.ZipFile(Path(path)) as z:
            meta = json.loads(z.read("meta.json").decode("utf-8"))
            if meta.get("format") != cls._FORMAT:
                raise ValueError(f"cse の 🐸 ファイルではないか、形式が違います(format={meta.get('format')!r})。")
            arrays = {n[:-4]: np.load(io.BytesIO(z.read(n)), allow_pickle=False) for n in z.namelist() if n.endswith(".npy")}
        frog = cls(**meta["config"])                      # 乱数の状態は __init__ の中で元に戻る
        e, n = frog._engine, frog.config.max_nodes
        for name, dtype in (("weights", np.float32), ("context_weights", np.float32), ("activation", np.float32),
                            ("context_trace", np.float32), ("frequency", np.int64)):
            arr = arrays[name]
            if arr.dtype != dtype or arr.shape != getattr(e, name).shape:
                raise ValueError(f"ファイルの中身が壊れています({name})。")
            setattr(e, name, arr.copy())
        e.id_to_symbol = list(meta["id_to_symbol"])
        e.symbol_to_id = {sym: i for i, sym in enumerate(e.id_to_symbol)}
        rows = arrays["pair_rows"]
        if rows.shape != (len(meta["pair_keys"]), n) or rows.dtype != np.float32:
            raise ValueError("ファイルの中身が壊れています(pair_rows)。")
        e.pair_context_weights = {tuple(k): rows[i].copy() for i, k in enumerate(meta["pair_keys"])}
        e.recent_fired = list(meta["recent_fired"])
        e.total_training_steps = int(meta["total_training_steps"])
        frog._to_char = {tok: ch for tok, ch in meta["tokens"]}
        frog._to_token = {ch: tok for tok, ch in meta["tokens"]}
        return frog

    # ------------------------------------------------------------ 中身をのぞく(上級向け)
    def _key(self, sym: str) -> Token:
        return END if sym == "<END>" else self._to_token[sym]

    def _inside(self, prefix: SequenceLike):
        """予測と同じ手順で状態を作り、点数の内訳を読み取る(エンジンは変えない)。ロックの中で呼ぶ。"""
        e = self._engine
        text = self._encode(self._as_tokens(prefix), allow_new=False)
        current = e.prime(text)                    # next_node_distribution と同じ手順
        e._inject(current, 1.0)
        e._propagate_once()
        final = e._candidate_scores(current)       # エンジン自身の点数
        n, cfg = e.node_count, e.cfg
        direct = e.weights[current, :n].astype(np.float64).copy()
        if cfg.normalize_direct_scores:
            total = direct[direct > 0].sum()
            if total > 0:
                direct /= total
        history = e.activation[:n].astype(np.float64).copy()
        for sym in ("<START>", "<UNK>"):
            history[e.symbol_to_id[sym]] = 0.0
        if direct[e.symbol_to_id["<END>"]] <= 0:
            history[e.symbol_to_id["<END>"]] = 0.0
        history_term = cfg.history_boost * history
        pair_term = np.zeros(n)
        if cfg.pair_context_boost > 0.0:
            if len(e.recent_fired) >= 2:
                pair = (e.recent_fired[-2], e.recent_fired[-1])
            elif len(e.recent_fired) == 1:
                pair = (e.symbol_to_id["<START>"], e.recent_fired[-1])
            else:
                pair = None
            row = e.pair_context_weights.get(pair) if pair else None
            if row is not None:
                ps = row[:n].astype(np.float64)
                pt = ps[ps > 0].sum()
                if pt > 0.0:
                    pair_term = cfg.pair_context_boost * (ps / pt)
        trace_term = np.zeros(n)
        if cfg.context_projection_boost > 0:
            reachable = (direct + history_term + pair_term) > 0
            trace = e.context_trace[:n].astype(np.float64).copy()
            trace[current] = 0.0
            for sym in ("<START>", "<END>", "<UNK>"):
                trace[e.symbol_to_id[sym]] = 0.0
            proj = trace @ (e.weights[:n, :n].astype(np.float64) + e.context_weights[:n, :n].astype(np.float64))
            proj[~reachable] = 0.0
            for sym in ("<START>", "<END>", "<UNK>"):
                proj[e.symbol_to_id[sym]] = 0.0
            trace_term = cfg.context_projection_boost * proj
        rebuilt = direct.copy()                     # エンジンと同じ順番で足す
        rebuilt += history_term
        rebuilt += pair_term
        rebuilt += trace_term
        rebuilt[e.symbol_to_id["<START>"]] = 0.0
        blocked = (rebuilt != 0) & (final == 0)     # 不応期で 0 にされた候補
        rebuilt[blocked] = 0.0
        if not np.array_equal(rebuilt, final):      # 内訳がエンジンの計算とずれていたら知らせる
            raise RuntimeError("内訳の再計算がエンジンの点数と一致しませんでした(cse のバグです。報告してください)")
        probs = e._probabilities(final)
        return dict(final=final, direct=direct, history=history_term, pair=pair_term, trace=trace_term,
                    blocked=blocked, probs=probs)

    def scores(self, prefix: SequenceLike = ()) -> Dict[Token, float]:
        """確率に変える「前」の生の点数を返します(0 より大きいものだけ、高い順)。

        確率は、この点数の上位 top_k_edges 個を softmax(温度 temperature)か linear で変換したものです。
        自分でサンプラー(Top-p など)を作るときの材料にどうぞ。
        """
        with self._lock:
            d = self._inside(prefix)
            e = self._engine
            out = {self._key(e.id_to_symbol[i]): float(v) for i, v in enumerate(d["final"])
                   if v > 0 and e.id_to_symbol[i] not in ("<START>", "<UNK>")}
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    def explain(self, prefix: SequenceLike = (), k: int = 5) -> List[dict]:
        """次の記号の点数が「どこから来たか」を、候補ごとに分けて返します(点数の高い順に k 個)。

        - direct  : 今の記号からの直接のつながり(学習で強くなった結びつき)
        - history : 少し前の記号の活性の残り(history_boost が 0 なら 0)
        - pair    : 直前2つの並びの記憶
        - trace   : ゆっくり残る文脈の痕跡(context_projection_boost が 0 なら 0)
        - score   : 合計点(= 上の4つの和。不応期で消された候補は 0)
        - blocked : 不応期で 0 にされたか
        - prob    : 最終的な確率
        """
        with self._lock:
            d = self._inside(prefix)
            e = self._engine
            rows = []
            for i in range(e.node_count):
                sym = e.id_to_symbol[i]
                if sym in ("<START>", "<UNK>"):
                    continue
                parts = (d["direct"][i], d["history"][i], d["pair"][i], d["trace"][i])
                if d["final"][i] <= 0 and not d["blocked"][i]:
                    continue
                rows.append({"token": self._key(sym), "direct": float(parts[0]), "history": float(parts[1]),
                             "pair": float(parts[2]), "trace": float(parts[3]), "score": float(d["final"][i]),
                             "blocked": bool(d["blocked"][i]), "prob": float(d["probs"][i])})
        rows.sort(key=lambda r: (-r["score"], -sum((r["direct"], r["history"], r["pair"], r["trace"]))))
        return rows[:k]

    def show(self, prefix: SequenceLike = (), k: int = 5) -> None:
        """explain() の結果を表で表示します。"""
        print(f"🐸 {list(self._as_tokens(prefix))} の次の候補")
        print(f"{'候補':<8}{'直接':>8}{'履歴':>8}{'並び':>8}{'痕跡':>8}{'合計点':>9}{'確率':>8}")
        rows = self.explain(prefix, k)
        if not any(r["score"] > 0 for r in rows):
            print("(点数がプラスの候補が1つもありません → エンジンは <END> を確率1で返します)")
        for r in rows:
            mark = "  ← 不応期で消された" if r["blocked"] else ""
            print(f"{str(r['token']):<8}{r['direct']:>8.3f}{r['history']:>8.3f}{r['pair']:>8.3f}{r['trace']:>8.3f}"
                  f"{r['score']:>9.3f}{r['prob']:>8.3f}{mark}")

    def edges(self, token: Token, k: int = 10) -> List[tuple]:
        """その記号から出ている「直接のつながり」と強さを、強い順に k 個返します(何を覚えたか)。"""
        with self._lock:
            if token not in self._to_char:
                raise ValueError(f"「{token}」はまだ覚えていない記号です。")
            e = self._engine
            i = e.symbol_to_id[self._to_char[token]]
            row = e.weights[i, :e.node_count]
            out = [(self._key(e.id_to_symbol[j]), float(row[j])) for j in np.argsort(-row)
                   if row[j] > 0 and e.id_to_symbol[j] not in ("<START>", "<UNK>")]
        return out[:k]

    def top(self, prefix: SequenceLike = (), k: int = 3) -> List[tuple]:
        """確率の高い順に k 個、(記号, 確率) を返します。"""
        items = sorted(self.probabilities(prefix).items(), key=lambda kv: -kv[1])
        return items[:k]

    def predict(self, prefix: SequenceLike = ()) -> Token:
        """prefix の次に一番来そうな記号を1つ返します(END、表示は <END> なら「ここで終わりそう」)。"""
        return self.top(prefix, k=1)[0][0]

    def __repr__(self) -> str:
        return f"Frog(覚えた記号={len(self._to_char)}個)"
