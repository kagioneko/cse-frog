"""cse — 順番のあるデータを覚えて「次に何が来そうか」を予測する、小さな学習用AI。

中身は Chain-Spike Engine (CSE) 講座版エンジン(`_engine.py`、無変更)です。
このファイルは、初心者がつまずきやすい点を吸収する薄い入口 `Frog` だけを足しています。

    from cse import Frog
    frog = Frog()
    frog.learn([["右", "右", "下"]] * 10)
    frog.predict(["右", "右"])        # -> "下"
"""
from __future__ import annotations

import random
import threading
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

    def top(self, prefix: SequenceLike = (), k: int = 3) -> List[tuple]:
        """確率の高い順に k 個、(記号, 確率) を返します。"""
        items = sorted(self.probabilities(prefix).items(), key=lambda kv: -kv[1])
        return items[:k]

    def predict(self, prefix: SequenceLike = ()) -> Token:
        """prefix の次に一番来そうな記号を1つ返します(END、表示は <END> なら「ここで終わりそう」)。"""
        return self.top(prefix, k=1)[0][0]

    def __repr__(self) -> str:
        return f"Frog(覚えた記号={len(self._to_char)}個)"
