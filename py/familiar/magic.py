"""魔法判定エンジン（Spell Parser + Magic Judge + Narrator）。カエルとは独立。

parse(詠唱) → 属性・動作・対象・修飾・特殊語を辞書の最長一致で取り出す（解析不能でも止まらない）。
judge(解析結果, 目的, seed) → 判定（正常発動・変異発動・ファンブル・特殊発動・不発）と効果。
同じ詠唱・目的・seed なら同じ結果になる。

判定の考え方（仕様書 4章）:
- ファンブルはただの運ではなく「実際の効果がプレイヤーの目的に反している」ときに起きる
  （敵を回復する、味方や自分を攻撃する、など）。
- 属性と動作がちぐはぐ（氷で癒やす、雷で眠らせる）なら変異。組み合わせ表に載っていれば専用の結果。
- 特殊語（プリン・猫…）が入っていれば特殊発動。
- 何も読み取れない詠唱は「未知魔法」。不発か、ごくまれに謎の効果。
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field

from .lexicon import (ACTION_JA, ACTION_KIND, ACTIONS, DEFAULT_ACTION, ELEMENT_JA, ELEMENTS,
                      MODIFIERS, NATURAL, SPECIALS, TARGET_JA, TARGETS)

VERDICTS = ("正常発動", "変異発動", "ファンブル", "特殊発動", "不発")
GOALS = ("attack", "heal")          # 目的: 敵を倒したい / 自分たちを回復したい


@dataclass
class Parsed:
    text: str
    element: str | None = None
    action: str | None = None
    target: str | None = None
    modifiers: list[str] = field(default_factory=list)
    specials: list[str] = field(default_factory=list)
    words: list[str] = field(default_factory=list)       # 読み取れた表記（順番どおり）

    @property
    def empty(self) -> bool:
        return not (self.element or self.action or self.target or self.specials)


def parse(text: str) -> Parsed:
    p = Parsed(text=text if isinstance(text, str) else "")
    tables = [(ELEMENTS, "element"), (ACTIONS, "action"), (TARGETS, "target")]
    words = sorted({*ELEMENTS, *ACTIONS, *TARGETS, *MODIFIERS, *SPECIALS}, key=len, reverse=True)
    i, t = 0, p.text.lower()                    # 英語は大文字小文字を区別しない（日本語は変わらない）
    while i < len(t):
        w = next((w for w in words if t.startswith(w, i) and _boundary_ok(t, i, w)), None)
        if not w:
            i += 1
            continue
        p.words.append(w)
        for table, attr in tables:
            if w in table and getattr(p, attr) is None:      # 最初に出てきたものを採る
                setattr(p, attr, table[w])
        if w in MODIFIERS and MODIFIERS[w] not in p.modifiers:
            p.modifiers.append(MODIFIERS[w])
        if w in SPECIALS and SPECIALS[w] not in p.specials:
            p.specials.append(SPECIALS[w])
        i += len(w)
    return p


def _is_latin(c: str) -> bool:
    return c.isascii() and c.isalpha()


def _boundary_ok(t: str, i: int, w: str) -> bool:
    """英単語は単語の頭からだけ当てる（enemy の中の me を拾わない）。
    3文字以下の英単語は単語全体が一致したときだけ（me/my/all/foe）。日本語の語は制限なし。"""
    if not _is_latin(w[0]):
        return True
    if i > 0 and _is_latin(t[i - 1]):
        return False
    end = i + len(w)
    return len(w) > 3 or end >= len(t) or not _is_latin(t[end])


@dataclass
class Result:
    verdict: str
    effect: dict
    lines: list[str]
    parsed: dict
    goal: str
    seed: int

    def to_dict(self) -> dict:
        return asdict(self)


# 属性×動作のちぐはぐな組み合わせのうち、専用の結果があるもの
# 属性×動作のちぐはぐな組み合わせのうち、専用の結果があるもの。
# (アイコン, 文, 効果の種類, 状態) — 効果データ（HP・状態・ターン）は表示と同じこの定義から作る。
COMBOS = {
    ("ice", "heal"): ("🍧", "{t}の目の前にかき氷が現れた。{t}はおいしく食べて、HPが{n}回復した。", "help", None),
    ("fire", "heal"): ("🍠", "{t}の手元に焼きいもが現れた。ほくほく。HPが{n}回復した。", "help", None),
    ("thunder", "sleep"): ("⚡", "{t}が感電して、{k}ターン動けなくなった。", "control", "shock"),
    ("fire", "freeze"): ("♨️", "炎と氷がぶつかって湯気が立ちこめた。{t}の視界が{k}ターン悪くなった。", "control", "fog"),
    ("dark", "heal"): ("🌙", "{t}はぐっすり眠って、HPが{n}回復した（{k}ターン寝ている）。", "help", "sleep"),
    ("water", "burn"): ("🫧", "お湯が沸いた。{t}に{n}ダメージ（ぬるめ）。", "harm", None),
    ("earth", "heal"): ("🌱", "{t}の足もとに薬草が生えた。HPが{n}回復した。", "help", None),
    ("light", "sleep"): ("😴", "まぶしすぎて{t}は目をつぶり、そのまま{k}ターン寝てしまった。", "control", "sleep"),
}
# 特殊語: (アイコン, 文, 効果の種類, 状態)。help は HP 回復、control は状態＋ターン、field は場の変化＋ターン
SPECIAL_FX = {
    "pudding": ("🍮", "戦場が巨大なプリンに覆われた。敵も味方も{k}ターン動きが遅くなる。", "field", "pudding"),
    "cat": ("🐈", "どこからか猫が現れて{t}の膝に乗った。{t}は{k}ターン動けない（動きたくない）。", "control", "cat"),
    "frog": ("🐸", "カエルの大合唱が始まった。{t}は{k}ターン耳をふさいでいる。", "control", "chorus"),
    "onigiri": ("🍙", "{t}におにぎりが配られた。HPが{n}回復した。", "help", None),
    "kakigori": ("🍧", "{t}の頭上にかき氷が降ってきた。キーンとして{k}ターン動けない。", "control", "brainfreeze"),
    "marshmallow": ("☁️", "{t}がマシュマロに埋もれた。ふかふかで{k}ターン出てこない。", "control", "fluffy"),
    "bread": ("🍞", "{t}の前に焼きたてのパンが並んだ。HPが{n}回復した。", "help", None),
}
UNKNOWN_FX = [
    ("❓", "何も起きなかった……と思ったら、{t}の靴ひもがほどけた。"),
    ("🌈", "空に小さな虹がかかった。効果はない。きれい。"),
    ("🎵", "どこからか拍手が聞こえた。魔法としては不発。"),
]
CAT_HELPED_ENEMY = ["「あと少しで倒せたのにィィィ！！」", "「それは敵にやるやつじゃない！」", "「ケロッじゃないのよ！」"]
CAT_HIT_FRIEND = ["「なんで味方を狙うの！？」", "「こっち！こっち向いてる！」", "「ケロッじゃないのよ！」"]


def _benefit(kind: str, target: str, goal: str) -> str:
    """good / bad / mixed / neutral（プレイヤーの目的から見た効果の向き）。"""
    enemy_side = target == "enemy"
    both = target in ("all", "area")
    if kind in ("harm", "control"):
        return "mixed" if both else ("good" if enemy_side else "bad")
    if kind == "help":
        if both:
            return "mixed"
        if enemy_side:
            return "bad"
        return "good" if goal == "heal" else "neutral"     # 攻撃したい時の回復・防御は「目的に反しない」
    return "neutral"                                      # field（場の変化）は向きを持たない


def judge(p: Parsed, goal: str = "attack", seed: int = 0) -> Result:
    if goal not in GOALS:
        raise ValueError("goal must be attack or heal")
    rng = random.Random(f"judge:{seed}")
    power = 1.0
    if "strong" in p.modifiers:
        power *= 1.5
    if "soft" in p.modifiers or "gentle" in p.modifiers:
        power *= 0.7
    turns_bonus = 2 if "long" in p.modifiers else 0
    n = max(1, round(30 * power * rng.uniform(0.8, 1.2)))
    k = 2 + turns_bonus + rng.randrange(2)
    parsed = asdict(p)
    head = f"🐸「{p.text}」"

    if p.specials:                        # 特殊語が最優先。効果の向きが目的に反すればファンブル
        sp = p.specials[0]
        icon, msg, kind, status = SPECIAL_FX[sp]
        tgt = p.target or ("self" if kind == "help" else "enemy")
        if kind == "field":                   # 場の変化（プリン）はいつも全体にかかる。表示もそう書いてある
            tgt = "all"
        who = "みんな" if tgt in ("all", "area") else TARGET_JA[tgt]
        lines = [head, f"{icon} " + msg.format(t=who, n=n, k=k)]
        effect = _effect(kind, tgt, n, k, status, special=sp)
        b = _benefit(kind, tgt, goal)
        verdict = "ファンブル" if b == "bad" else "特殊発動"
        if verdict == "ファンブル":
            lines.append("🐱" + rng.choice(CAT_HELPED_ENEMY if tgt == "enemy" else CAT_HIT_FRIEND))
        lines.append(f"判定：{verdict}")
        return Result(verdict, effect, lines, parsed, goal, seed)

    if p.empty:
        if rng.random() < 0.3:
            icon, msg = rng.choice(UNKNOWN_FX)
            lines = [head, f"{icon} 未知の魔法。" + msg.format(t="敵")]
            return Result("特殊発動", {"kind": "unknown"}, lines + ["判定：特殊発動"], parsed, goal, seed)
        lines = [head, "💨 詠唱が意味をなさず、魔法は形にならなかった。", "判定：不発"]
        return Result("不発", {"kind": "none"}, lines, parsed, goal, seed)

    element = p.element
    action = p.action or (DEFAULT_ACTION[element] if element else None)
    if action is None:                       # 対象だけ・修飾だけ等
        lines = [head, "💨 誰に何をするかは伝わったが、魔法の力が足りなかった。", "判定：不発"]
        return Result("不発", {"kind": "none"}, lines, parsed, goal, seed)
    kind = ACTION_KIND[action]
    target = p.target or ("self" if kind == "help" else "enemy")
    natural = element is None or action in NATURAL[element]
    combo = COMBOS.get((element, action)) if element else None

    who = TARGET_JA[target]
    el = ELEMENT_JA.get(element, "魔力")
    status = None
    if combo:
        icon, msg, kind, status = combo
        lines = [head, f"{icon} " + msg.format(t=who, n=n, k=k)]
    else:
        lines = [head]
        if kind == "harm":
            lines.append(f"{_icon(element)} {el}が{who}を{ACTION_JA[action]}！ {who}に{n}ダメージ。")
        elif action == "heal":
            lines.append(f"{_icon(element)} {el}が{who}を{ACTION_JA[action]}。{who}のHPが{n}回復した。")
        elif kind == "help":
            kind, status = "buff", "shield"
            lines.append(f"{_icon(element)} {el}の盾が{who}を守る。{k}ターン、受けるダメージが半分になる。")
        elif kind == "control":
            status = action
            lines.append(f"{_icon(element)} {el}が{who}を{ACTION_JA[action]}。{who}は{k}ターン動けない。")
        else:
            status = action
            lines.append(f"{_icon(element)} {el}が{who}を{ACTION_JA[action]}。{k}ターンのあいだ、場のようすが変わった。")
    effect = _effect(kind, target, n, k, status, element=element, action=action)
    if kind == "buff":
        kind = "help"                            # 判定上は「助ける」魔法

    b = _benefit(kind, target, goal)
    if b == "bad":
        verdict = "ファンブル"
        lines.append("🐱" + rng.choice(CAT_HELPED_ENEMY if target == "enemy" else CAT_HIT_FRIEND))
    elif not natural or b == "mixed":
        verdict = "変異発動"
    else:
        verdict = "正常発動"
    lines.append(f"判定：{verdict}")
    return Result(verdict, effect, lines, parsed, goal, seed)


def _effect(kind: str, target: str, n: int, k: int, status: str | None, **extra) -> dict:
    """表示と同じ定義から効果データを作る。hp は常に {enemy/self/ally: 増減} の形。"""
    e = {"kind": kind, "target": target, **{a: v for a, v in extra.items() if v is not None}}
    if kind == "harm":
        e["hp"] = _spread(target, -n)
    elif kind == "help":
        e["hp"] = _spread(target, n)
    if status:
        e["status"] = status
        e["turns"] = k
    elif kind in ("control", "field", "buff"):
        e["turns"] = k
    return e


def _spread(target: str, delta: int) -> dict:
    if target in ("all", "area"):
        return {"enemy": delta, "self": delta, "ally": delta}
    return {target: delta}


def _icon(element: str | None) -> str:
    return {"fire": "🔥", "ice": "❄️", "thunder": "⚡", "wind": "🌪️", "water": "💧",
            "light": "✨", "dark": "🌑", "earth": "🪨"}.get(element, "✴️")


def cast(text: str, goal: str = "attack", seed: int = 0) -> Result:
    return judge(parse(text), goal, seed)
