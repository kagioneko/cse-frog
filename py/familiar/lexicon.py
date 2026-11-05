"""魔法の辞書（判定エンジン側の知識）。カエルはこれを知らない。

表記 → 意味ラベル。解析は長い表記から先に当てる（最長一致）。
"""

ELEMENTS = {
    "聖なる光": "light", "光": "light", "閃光": "light",
    "炎": "fire", "火": "fire", "焔": "fire", "業火": "fire",
    "氷": "ice", "吹雪": "ice", "雪": "ice", "氷河": "ice",
    "雷": "thunder", "稲妻": "thunder", "雷鳴": "thunder",
    "風": "wind", "嵐": "wind", "竜巻": "wind",
    "水": "water", "雨": "water", "波": "water", "泉": "water",
    "闇": "dark", "影": "dark", "深淵": "dark", "夜": "dark",
    "大地": "earth", "岩": "earth", "土": "earth", "石": "earth",
}
ELEMENT_JA = {"fire": "炎", "ice": "氷", "thunder": "雷", "wind": "風", "water": "水",
              "light": "光", "dark": "闇", "earth": "大地"}

# 動詞は語幹で当てる（活用の揺れを吸収）。kind: harm=ダメージ / help=回復・防御 / control=行動不能 / field=場の変化
ACTIONS = {
    "焼き尽く": "burn", "焼き払": "burn", "焼": "burn", "燃や": "burn", "燃え": "burn",
    "凍らせ": "freeze", "凍て": "freeze", "凍れ": "freeze", "凍": "freeze",
    "撃ち抜": "smash", "砕": "smash", "貫": "smash", "打ち砕": "smash", "穿": "smash",
    "吹き飛ば": "blast", "薙ぎ払": "blast", "切り裂": "blast", "押し流": "blast",
    "癒": "heal", "治": "heal", "回復": "heal", "満た": "heal",
    "守": "guard", "護": "guard", "防": "guard",
    "眠らせ": "sleep", "眠れ": "sleep", "眠": "sleep",
    "痺れ": "stun", "縛": "stun", "止め": "stun",
    "包": "wrap", "覆": "wrap", "沈め": "wrap",
    "照ら": "shine", "輝": "shine", "清め": "shine", "浄": "shine",
}
ACTION_KIND = {"burn": "harm", "freeze": "harm", "smash": "harm", "blast": "harm",
               "heal": "help", "guard": "help", "sleep": "control", "stun": "control",
               "wrap": "field", "shine": "field"}
ACTION_JA = {"burn": "焼く", "freeze": "凍らせる", "smash": "砕く", "blast": "吹き飛ばす",
             "heal": "癒やす", "guard": "守る", "sleep": "眠らせる", "stun": "痺れさせる",
             "wrap": "包む", "shine": "照らす"}

TARGETS = {
    "敵": "enemy", "魔物": "enemy", "奴": "enemy", "悪": "enemy", "あいつ": "enemy",
    "我が": "self", "我": "self", "自分": "self", "私": "self", "この身": "self",
    "仲間": "ally", "味方": "ally", "友": "ally",
    "全て": "all", "すべて": "all", "世界": "all", "皆": "all", "みんな": "all",
    "戦場": "area", "周囲": "area", "あたり": "area", "空": "area",
}
TARGET_JA = {"enemy": "敵", "self": "自分", "ally": "味方", "all": "全員", "area": "周囲"}

MODIFIERS = {"激しく": "strong", "烈しく": "strong", "猛き": "strong", "静かに": "soft",
             "そっと": "soft", "優しく": "gentle", "永遠に": "long", "とこしえに": "long"}

SPECIALS = {"プリン": "pudding", "猫": "cat", "ねこ": "cat", "カエル": "frog", "かえる": "frog",
            "おにぎり": "onigiri", "かき氷": "kakigori", "マシュマロ": "marshmallow", "パン": "bread"}

# 属性の「らしい」動作（これ以外の組み合わせは変異）
NATURAL = {
    "fire": {"burn", "blast", "shine"}, "ice": {"freeze", "guard", "stun"},
    "thunder": {"smash", "stun", "blast"}, "wind": {"blast", "guard", "wrap"},
    "water": {"heal", "wrap", "smash"}, "light": {"heal", "shine", "guard"},
    "dark": {"wrap", "sleep", "smash"}, "earth": {"smash", "guard", "wrap"},
}
DEFAULT_ACTION = {"fire": "burn", "ice": "freeze", "thunder": "stun", "wind": "blast",
                  "water": "wrap", "light": "heal", "dark": "sleep", "earth": "smash"}

# 英語の詠唱用（大文字小文字は区別しない。3文字以下の語は単語全体が一致したときだけ）
ELEMENTS.update({"fire": "fire", "flame": "fire", "ice": "ice", "frost": "ice", "snow": "ice",
                 "thunder": "thunder", "lightning": "thunder", "wind": "wind", "storm": "wind",
                 "water": "water", "rain": "water", "wave": "water", "light": "light", "holy": "light",
                 "dark": "dark", "darkness": "dark", "shadow": "dark", "earth": "earth", "stone": "earth"})
ACTIONS.update({"burn": "burn", "freeze": "freeze", "smash": "smash", "strike": "smash",
                "pierce": "smash", "blow": "blast", "sweep": "blast", "heal": "heal", "cure": "heal",
                "protect": "guard", "guard": "guard", "shield": "guard", "sleep": "sleep",
                "bind": "stun", "stun": "stun", "wrap": "wrap", "cover": "wrap", "shine": "shine"})
TARGETS.update({"enemy": "enemy", "enemies": "enemy", "foe": "enemy", "foes": "enemy",
                "me": "self", "myself": "self", "ally": "ally", "allies": "ally",
                "friend": "ally", "friends": "ally", "all": "all", "world": "all",
                "everyone": "all", "battlefield": "area", "field": "area"})
MODIFIERS.update({"fiercely": "strong", "gently": "gentle", "softly": "soft", "forever": "long"})
SPECIALS.update({"pudding": "pudding", "cat": "cat", "frog": "frog", "riceball": "onigiri",
                 "marshmallow": "marshmallow", "bread": "bread"})

# すべての表記（分かち書きで、途中で切らない語）
ALL_WORDS = sorted({*ELEMENTS, *ACTIONS, *TARGETS, *MODIFIERS, *SPECIALS}, key=len, reverse=True)
