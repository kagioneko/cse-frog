"""詠唱を「言葉のかたまり」に切る（カエルが覚える1記号の単位）。

例: 「炎よ、敵を焼き尽くせ！」 → ["炎よ", "、", "敵を", "焼き尽くせ", "！"]
    "Fire, burn the enemy!" → ["Fire", ",", " ", "burn", " ", "the", " ", "enemy", "!"]
- 句読点・記号は1つで1かたまり。
- スペースも1かたまり（続いたスペースは1つにまとめる。全角スペースも半角1つとして扱う）。
- 助詞（よ を に へ の で と が は も）の直後で切る。ただしかたまりの先頭の文字なら切らない。
- 辞書の語（「おにぎり」など）は途中で切らない（「おに|ぎり」にしない）。
- 修飾語（「静かに」「優しく」「激しく」など）はそれだけで1かたまり。
意味は見ない。どこで切るかだけ。
"""
from __future__ import annotations

from .lexicon import ALL_WORDS, MODIFIERS

PUNCT = set("、。，．,.！!？?…・「」『』（）()～〜")
SPACE = " "
PARTICLES = set("よをにへのでとがはも")


def chunk(text: str) -> list[str]:
    out: list[str] = []
    cur = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isspace():
            if cur:
                out.append(cur)
                cur = ""
            if not out or out[-1] != SPACE:
                out.append(SPACE)
            i += 1
            continue
        if ch in PUNCT:
            if cur:
                out.append(cur)
                cur = ""
            out.append(ch)
            i += 1
            continue
        word = next((w for w in ALL_WORDS if text.startswith(w, i)), None)
        if word:
            i += len(word)
            if word in MODIFIERS:              # 「静かに」「優しく」などは1かたまり（ここで別の詠唱に乗り換えられる）
                if cur:
                    out.append(cur)
                out.append(word)
                cur = ""
            else:
                cur += word
            continue
        cur += ch
        i += 1
        if ch in PARTICLES and len(cur) >= 2:
            out.append(cur)
            cur = ""
    if cur:
        out.append(cur)
    return out
