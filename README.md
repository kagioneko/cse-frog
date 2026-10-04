# cse 🐸

[![GitHub Sponsors](https://img.shields.io/github/sponsors/kagioneko?label=Sponsor&logo=githubsponsors&color=EA4AAA)](https://github.com/sponsors/kagioneko)

順番のあるデータを覚えて「次に何が来そうか」を予測する、**学習用の小さなAI**です。
Pythonの練習や、言語モデル(LM)の仕組みを手で触って理解するために作りました。

**これはLLMの代わりではありません。** 中身が全部見えて、壊して学べることが目的です。

## 🐸 解剖用の「LMの素体」
理科の授業でカエルを解剖するのは、カエルが一番強いからではなく、**体のつくりが一通りそろっていて、しかも見やすいから**です。
cse も同じで、言語モデル(LM)に必要な臓器を一通り持った、**全部開いて見られる最小の体**です。
(しかも何度解剖しても `Frog()` でもう1匹出てきます)

| LMの臓器 | 🐸 CSE では | 大きな LLM では |
|---|---|---|
| 入力を記号にする | 1文字=1記号(`Frog` なら1要素=1記号) | トークナイザー |
| 覚える | ヘブ則で結びつきが強くなる | 勾配降下で重みを直す |
| 文脈を持つ | 活性の残り・直前2つの並び | アテンション |
| 予測する | 点数 → softmax / linear で確率に | logits → softmax |
| 抑える | 不応期 | 繰り返しペナルティ |
| 選ぶ | (自分で作る! Top-p など) | サンプラー |

右の列の「本物の臓器」が何のためにあるのかを、左の小さな体で先に触って理解できます。
たとえば 🐸 の文脈は直前2つまでしか見えません。だから大きな LLM は、遠くを見るためにアテンションを持っています。

**立ち位置**: 数え上げ(n-gram)より動く部分が多く(発火・伝播・減衰・不応期)、LLM より中身が見える。
予測の精度では数え上げに負けることもあります。それも含めて全部見せるのが、この 🐸 の役目です。

### いじる設定 ↔ LLM で似ているもの
`Frog(設定名=値)` で変えて、`frog.show(...)` で点数と確率の変化を見てみてください。

| 🐸 でいじる設定 | LLM で似ているもの | いじるとどうなる |
|---|---|---|
| `temperature` | temperature(そのまま同じ!) | 下げると自信満々、上げると迷いがち |
| `top_k_edges` | Top-k(①の役割) | 2つの役割: ① 確率にする候補を上位 k 個に絞る ② 活性を広げるとき、各記号から強い順に k 本のつながりだけを使う |
| `refractory_steps` | 繰り返しペナルティ | 同じ記号を続けて出さなくなる(🐸 は完全に禁止するので、点数を下げるだけのペナルティより極端) |
| `pair_context_capacity` / `pair_context_boost` | コンテキストの長さ | 🐸 は直前2つまで。0 にすると「右右 → 下」が覚えられない |
| `max_nodes` | 語彙サイズ | 覚えられる記号の数 |
| `learn(..., epochs=)` | 学習のステップ数 | 何周くり返して覚えるか |
| `history_boost` | 今の LLM の標準的な設定にはない。近いのは**マイナスの presence_penalty**(OpenAI の API などで、使った言葉を出やすくする方向)や、昔の**キャッシュ言語モデル**(最近出た単語の確率を上げる方法) | 少し前に出た記号が出やすくなる(研究では、生成を崩す方向に効いていた: H-GEN-2) |

あくまで「似た働き」です。違い(不応期は禁止、文脈は2つだけ、など)も含めて比べてみてください。

## クイックスタート
インストール(PyPI に `cse-frog` として登録するまでは GitHub から。使うときの名前は `from cse import Frog`):
```bash
pip install git+https://github.com/kagioneko/cse-frog.git
```

全機能・全設定の一覧は [docs/REFERENCE.md](docs/REFERENCE.md)、遊び方・壊し方・改造のしかたは [docs/HANDBOOK.md](docs/HANDBOOK.md)、設定をいじると何が起こるかは [docs/CONFIG_GUIDE.md](docs/CONFIG_GUIDE.md) にあります。

```python
from cse import Frog
frog = Frog()                                # 🐸 を1匹つくる
frog.learn([["右", "右", "下"]] * 10)         # 行動の系列を覚えさせる
print(frog.predict(["右", "右"]))             # -> 下
print(frog.top(["右"], k=2))                 # 確率の高い順に2つ
```

- `learn()` の渡し方は3通り: 文字列1つ `"右右下"`(1文字=1記号の1本の系列)、リスト1つ `["正常", "温度上昇", "停止"]`(1要素=1記号の1本の系列。「停止」は「停」と「止」に分かれません)、リストのリスト `[[...], [...]]`(何本もの系列)。
- `learn(データ, epochs=20)` のように、同じデータを何周くり返して覚えるかも決められます(既定 3)。
- `predict()` が `cse.END`(表示は `<END>`)を返したら「ここで系列が終わりそう」という意味です。
- 覚えていない記号を渡すと、日本語のエラーで教えてくれます。

## ノートブックで遊ぶ 🐸

| ノートブック | 中身 |
|---|---|
| [00_hello_frog](notebooks/00_hello_frog.ipynb) | 🐸を作る・覚えさせる・中を見る・保存する |
| [01_prediction_knobs](notebooks/01_prediction_knobs.ipynb) | temperature / probability_mode / top_k_edges |
| [02_context_and_inhibition](notebooks/02_context_and_inhibition.ipynb) | 並びの記憶 / 不応期 / history_boost |
| [03_memory_and_forgetting](notebooks/03_memory_and_forgetting.ipynb) | 忘却の2つの罠 / 並びの記憶は忘れない / 遠くを学ぶ |
| [04_break_your_frog](notebooks/04_break_your_frog.ipynb) | 壊し放題実験場・「何も変わらない」の診断器・自作top-p |

各ノートブックの先頭に「Open in Colab」ボタンがあります。

## 正直な限界

- **局所的な予測器です。** 既定の設定では、基本的に「今の記号」と「直前2つの並び」から次を予測します。n-gram(数え上げ)に近い性質です。
- 研究(Chain-Spike Engine の検証)では、古典的な評価軸(精度・メモリ・速度・較正など)で、n-gram などの既存手法に対する**比較優位は見つかりませんでした**。遠くの文脈を使う問題(検索など)は苦手です。
- エンジンは本来**文字単位**です。`Frog` は単語などの記号を内部で1文字に置き換えて、この制約を吸収しています。
- 既定の設定(`refractory_steps=0` など)は、素直に予測するための設定です。`Frog(refractory_steps=2)` のように変えると、元の仕組み(不応期)の挙動を観察できます。

## 品質について
研究で使ったエンジンと同じ計算結果になることを、開発時にテストで確認しています(そのテストは配布物に含めていません)。

## ライセンス
MIT License。Copyright (c) 2026 Emilia Lab / 鍵乃ねこ (kagioneko)。
再配布・公開するときは、`LICENSE` の著作権表示とライセンス文を含めてください。

## 🐸 を保存する
```python
frog.save("my_frog.cse")            # 覚えたことをファイルに保存
frog = Frog.load("my_frog.cse")     # 次の日に読み込んで、続きから学習も予測もできる
```
- 保存したファイルは JSON と数値の配列だけです(pickle は使わないので、人の 🐸 を読み込んでも安全です)。
- 記号として保存できるのは、文字列・整数・小数・True/False・None です。
- 読み込んだ 🐸 は、保存する前の 🐸 と予測も続きの学習もビット単位で同じになります(テストで確認)。

## 設定をいじって壊して遊ぶ 🐸
`Frog(設定名=値)` で、エンジンの設定を1つずつ変えられます。今の設定は `frog.config` で見られます。知らない設定名を書くと、使える名前の一覧つきでエラーになります。

```python
from cse import Frog
data = [["右", "右", "下"] * 5]

Frog().learn(data).top(["右", "右", "下"])                    # 右 0.87 / <END> 0.13   (素直)
Frog(refractory_steps=2).learn(data).top(["右", "右", "下"])  # <END> 1.0             (不応期: 直前に出た「右」を出せない!)
Frog(probability_mode="linear").learn(data).top(["右", "右", "下"])  # 右 0.80 / <END> 0.20 (確率の出し方を変える)
Frog(temperature=2.0).learn(data).top(["右", "右", "下"])    # 右 0.68 / <END> 0.32   (温度を上げると自信が弱まる)
```

- `refractory_steps`: 直前に出た記号を、しばらく出さない仕組み(不応期)。既定は 0(オフ)。
- `history_boost`: 少し前の記号の「残り香」で点数を盛る。既定は 0.0(オフ)。
- `temperature` / `probability_mode`: 点数を確率に変える方法。温度が低いほど、確率が 0 か 1 に張り付きやすい。
- `pair_context_capacity` / `pair_context_boost`: 直前2つの並びを覚える量と、その使い方の強さ。0 にすると「右右 → 下」が覚えにくくなる。
- `max_nodes`: 覚えられる記号の数の上限(+3)。

## 安心して使うために
- `Frog()` を作っても、あなたのプログラムの乱数(`random` / `numpy.random`)の状態は変わりません。
- 同じ `Frog` を複数のスレッドから同時に使っても、予測は壊れません(学習と予測は1つずつ順番に処理されます)。
- 覚えられる記号の数には上限があります(`max_nodes − 3` 個。既定 253 個)。こえるとエラーで知らせます。`Frog(max_nodes=1000)` のように増やせますが、メモリは `max_nodes` の2乗で増えます。

## 中身をのぞく(中級〜上級)🔍
大きなLLMではできない、「どこで・なぜその予測をしたか」を数字で見られます。

```python
from cse import Frog
frog = Frog(refractory_steps=2).learn([["右", "右", "下"] * 5])
frog.show(["右", "右", "下"])
# 🐸 ['右', '右', '下'] の次の候補
# 候補            直接      履歴      並び      痕跡      合計点      確率
# <END>      0.298   0.000   0.200   0.000    0.498   1.000
# 右          1.186   0.000   0.800   0.000    0.000   0.000  ← 不応期で消された
```

- `frog.explain(prefix, k=5)`: 候補ごとの点数の内訳(直接のつながり・履歴・直前2つの並び・文脈の痕跡)と確率。内訳の合計がエンジンの点数とぴったり一致することを、毎回確認しています。
- `frog.scores(prefix)`: 確率に変える**前**の生の点数。これを使って Top-p や Top-k のサンプラーを自分で作れます。
- `frog.edges("右")`: その記号から出ている「直接のつながり」と強さ(何を覚えたか)。

### 例: Top-p サンプラーを自分で作る
```python
import random
def top_p(frog, prefix, p=0.9):
    items = sorted(frog.probabilities(prefix).items(), key=lambda kv: -kv[1])
    keep, total = [], 0.0
    for tok, prob in items:
        keep.append((tok, prob)); total += prob
        if total >= p:
            break
    tokens, weights = zip(*keep)
    return random.choices(tokens, weights=weights)[0]
```

## 応援する 🐸
cse は Emilia Lab / 鍵乃ねこ が個人で研究・開発しています。気に入ったら [GitHub Sponsors](https://github.com/sponsors/kagioneko) で応援してもらえると、🐸の研究と教材づくりの続きに使わせていただきます。
