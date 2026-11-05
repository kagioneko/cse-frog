"""Spell Memory: 教えた詠唱の保存（JSON ファイル1つ）。保存するのは詠唱の文字列だけで、カエルそのものではない。

- 受け付けるのは 2〜60 文字の1行。URL・メールアドレス・4桁以上の数字（電話番号などの個人情報っぽいもの）は断る。
- 同じ詠唱は1つにまとめる。上限 MAX_SPELLS を超えたら古いものから消す。
- version は「件数-内容のハッシュ先頭」。ログに残して、どのデータで召喚したかを再現できるようにする。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path

MAX_LEN = 60
MIN_LEN = 2
MAX_SPELLS = 500
_BAD = [
    (re.compile(r"https?://|www\.|[a-z0-9-]+\.(com|net|org|jp|io|co)\b", re.I), "URLっぽい"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "メールアドレスっぽい"),
    (re.compile(r"\d{4,}|[０-９]{4,}"), "長い数字（電話番号など）っぽい"),
]


def check(text: str) -> str | None:
    """問題があれば理由を返す。なければ None。"""
    if not isinstance(text, str):
        return "文字列ではない"
    t = text.strip()
    if not MIN_LEN <= len(t) <= MAX_LEN:
        return f"{MIN_LEN}〜{MAX_LEN}文字にしてね"
    if any(ord(c) < 32 or ord(c) == 127 for c in t):
        return "改行や制御文字は使えない"
    for rx, why in _BAD:
        if rx.search(t):
            return why + "ので覚えない"
    return None


class SpellMemory:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        d = json.loads(self.path.read_text(encoding="utf-8"))
        return [s for s in d.get("spells", []) if isinstance(s, dict) and isinstance(s.get("text"), str)]

    def texts(self) -> list[str]:
        return [s["text"] for s in self.load()]

    def add(self, text: str, now=time.time) -> tuple[bool, str]:
        why = check(text)
        if why:
            return False, why
        t = text.strip()
        spells = self.load()
        if any(s["text"] == t for s in spells):
            return False, "もう覚えている"
        nid = max((s.get("id", 0) for s in spells), default=0) + 1
        spells.append({"id": nid, "text": t, "at": now()})
        spells = spells[-MAX_SPELLS:]
        self._save(spells)
        return True, f"覚えた（{len(spells)}個目）"

    def _save(self, spells: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".mem-")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"spells": spells}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)


def version(spells: list[str]) -> str:
    h = hashlib.sha256("\n".join(spells).encode("utf-8")).hexdigest()[:12]
    return f"{len(spells)}-{h}"
