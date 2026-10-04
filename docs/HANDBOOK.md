# CSE Technical Handbook 🐸
## Build, Break, Grow Your Frog

**Version:** Draft 0.4  
**Target:** CSE Course Edition / `Frog` API  
**Concept:** A hands-on handbook for building, modifying, observing, breaking, and growing a tiny language model.

---

# 0. Evidence Labels

このHandbookでは、記述の根拠を明確に分離します。

**[CODE]**  
Course Editionの実コードから直接確認できること。

**[DOC]**  
README / API Referenceに明記されていること。

**[EXP-C]**  
Course Edition / `Frog` で実際に確認した結果。

**[EXP-R]**  
Research Editionで行われ、監査済みの実験結果。

**[IDEA]**  
まだ標準実装・性能優位が確認されていない拡張案。

「実装されている」「講座版で再現した」「研究版で確認した」「まだアイデア」を混同しないことが、このHandbookの基本ルールです。

---

# 1. この本は何？

[DOC]

CSE Course Editionは、順番のあるデータを学習して「次に何が来そうか」を予測する、小さな学習用AIです。

READMEでは、巨大LLMの代替ではなく、

> **中身を全部開いて、壊して学べる「LMの素体」**

として位置付けられています。

このHandbookはAPI一覧ではありません。APIの正確な仕様は`REFERENCE.md`が担当します。

ここでやるのは、

```text
作る
 ↓
覚えさせる
 ↓
観察する
 ↓
設定を変える
 ↓
壊す
 ↓
理由を見る
 ↓
機能を足す
 ↓
比較する
```

です。

---

# 2. CSEを一言でいうと

[CODE][DOC]

CSEは、

> **小さく、逐次学習でき、内部状態を観察でき、設定を変更しながら実験できる系列予測モデル**

です。

巨大な事前学習済みLMを、

```text
Load
 ↓
Prompt
 ↓
Output
```

として使うのとは少し違います。CSEでは、

```text
Empty Frog
   ↓
Learn
   ↓
Predict
   ↓
Inspect
   ↓
Learn More
   ↓
Predict Again
```

という成長過程そのものを触れます。

---

# 3. 「LM界のStable Diffusion」という遊び方

[IDEA]

これはCSEとStable Diffusionが同じアーキテクチャだという意味ではありません。似ているのは**遊び方・拡張思想**です。

```text
CSE Core
 │
 ├─ Pair Context
 ├─ History
 ├─ Slow Trace
 ├─ Refractory
 ├─ Top-K
 ├─ Temperature
 │
 └─ External Extensions
      ├─ Top-p
      ├─ Retrieval
      ├─ Surprise
      ├─ Router
      └─ Multi-Frog
```

[CODE]

`Frog`は生の候補scoreと確率を外へ出せるため、Top-pなどの出力ポリシーを外側から実装できます。

つまり、

> **使うLMではなく、組んで育てるLM。**

というのが、このHandbookでのCSEの見方です。

---

# 4. 最初の🐸

[CODE][DOC][EXP-C]

```python
from cse import Frog

frog = Frog()

frog.learn([
    ["右", "右", "下"],
    ["右", "右", "下"],
    ["右", "右", "下"],
])

print(frog.predict(["右", "右"]))
```

確認結果:

```text
下
```

`Frog`はCourse Edition本体`ChainSpikeEngine`を初心者向けに包む薄い入口です。

---

# 5. 🐸の中身

[CODE]

Course Editionには、

- Hebbian learning
- activation injection
- activation decay
- activation cap
- Top-K propagation
- activation history
- refractory inhibition
- ordered-pair context
- optional slow context trace
- softmax / linear probabilities
- sampled generation
- greedy generation
- teacher-forced scoring

が存在します。大まかな流れは、

```text
Input
 ↓
Symbol / Node
 ↓
Learned Edges
 ↓
Contextual State
 ↓
Candidate Score
 ↓
Top-K
 ↓
Softmax / Linear
 ↓
Probability Distribution
 ↓
Prediction
```

です。

---

# 6. CSEと大きなLMの機能対応

[DOC]

ここでいう「対応」は同じアルゴリズムという意味ではありません。

| LM機能 | CSE | Transformer系LM |
|---|---|---|
| 入力単位化 | Symbol / Frog mapping | Tokenizer |
| 学習 | Hebbian edge update | Gradient descent |
| 学習済み状態 | Edge weights | Parameters |
| 文脈利用 | Activation / Pair Context / Trace | Attention等 |
| 候補評価 | Candidate score | Logits |
| 確率化 | Softmax / Linear | Softmax |
| 温度 | `temperature` | Temperature |
| 候補制限 | `top_k_edges` | Top-k |
| 反復抑制 | Refractory | Repetition penalty等 |
| 系列終了 | `cse.END` | EOS |
| 出力選択 | `predict()` / 外部Sampler | Decoder / sampler |

特に、

```text
CSE Pair Context ≠ Self-Attention
```

です。ただし、

> **過去の文脈によって次予測を条件付ける**

という機能領域では比較できます。

---

# 7. Engine CapabilityとFrog APIは別

[CODE]

`_engine.py`には、

```text
generate()
generate_greedy()
score_text()
```

などがあります。しかし現在の`Frog`公開APIは、それらをそのまま公開していません。したがって、

```text
Course Engine
     ↓
Frog Public API
     ↓
User Extension
```

を区別します。現在の`Frog`で生成を行うなら、

```text
Frog
 ↓
probabilities()
 ↓
External Sampler
 ↓
next token
 ↓
loop
```

のように、自分でループを組みます。

[IDEA]

将来的な公開API候補:

```python
frog.generate(...)
frog.score(...)
```

---

# 8. Config — 🐸の挙動を変える

[CODE][DOC]

```python
frog = Frog(
    temperature=1.5,
    top_k_edges=5,
    refractory_steps=0,
)
```

Course Editionでは多数の内部Configを直接変更できます(全23項目は`REFERENCE.md`)。

---

# 9. Temperature

[CODE]

```python
Frog(temperature=0.05)
Frog(temperature=0.8)
Frog(temperature=10.0)
```

softmax時の温度です。概念的には、

```text
logits = scores / temperature
softmax(logits)
```

です。

[EXP-C]

教材例では、

```text
temperature = 0.05
→ 下 ≈ 1.0

temperature = 10
→ 下 ≈ 0.525
```

となりました。低温では分布が尖り、高温では平坦化します。

---

# 10. Top-K

[CODE]

```python
top_k_edges = 3
```

この設定は二つの役割を持ちます。

### Probability Top-K

候補scoreの上位K個だけを確率化します。

### Propagation Top-K

各Nodeから活性を伝播させるEdgeも上位K本へ制限します。

したがって`top_k_edges`は、単なる出力Sampler設定ではありません。

> **CSE内部の情報伝播量そのものにも影響するConfig**

です。

---

# 11. Refractory — 何個前まで禁止する？

[CODE]

```python
Frog(refractory_steps=2)
```

`refractory_steps`は、最近発火したNodeを何個前まで出力候補から禁止するかを決めます。

一般的なrepetition penaltyのように「少し点数を下げる」のではなく、対象候補のscoreを0にします。つまり、

```text
soft penalty
```

というより、

```text
temporary ban
```

に近い仕組みです。

[EXP-C]

同じ学習データに対して`refractory_steps`だけを変えると、次のようになりました。

| `refractory_steps` | 「右右」の次 | 「右右下」の次 | 何が禁止されたか |
|---:|---|---|---|
| `0` | 下 0.777 / 右 0.223 | 右 0.865 | 何も禁止されない |
| `1` | 下 1.0 | 右 0.865 | 直前の1個だけ |
| `2` | 下 1.0 | `<END>` 1.0 | 直前の2個。「右右下」の後でも右が出せない |
| `5` | 下 1.0 | `<END>` 1.0 | この例では`2`と同じ |

この表から二つのことが分かります。

### Top-1だけ見ていると変化を見逃す

`refractory_steps=0`と`1`では、`右右 → 下`というTop-1 prediction自体は同じです。しかし分布は、

```text
steps=0:
下 0.777 / 右 0.223

steps=1:
下 1.0
```

へ変わっています。

> **predict()の答えが同じでも、内部の選択肢は変化している。**

### 1と2では「壊れる場所」が変わる

`steps=1`なら直前の1記号だけが禁止されるため、`右 → 右 → 下`の後では`右`を再び出せます。

ところが`steps=2`では直前2個に`右`が含まれるため、`右右下 → 右`という必要な繰返しまで禁止され、`<END> = 1.0`になりました。

> **Configを1だけ変えると、モデルが壊れる位置そのものが変わる。**

---

# 12. Pair Context

[CODE]

```text
pair_context_capacity
pair_context_boost
```

CSEは直前2つの記号の組を覚えます。`右 → 右 → 下`なら、

```text
("右", "右") → "下"
```

という情報を保持できます。

[EXP-C]

Pair Contextを切ると、

```text
下 0.5
右 0.5
```

となり、この教材例では候補を区別できなくなりました。Pair Contextの効果を見る非常に分かりやすいablationです。

---

# 13. Slow Context Trace

[CODE]

```text
context_trace_decay
context_projection_boost
```

Slow Traceはactivationそのものを保存する機構ではありません。Course Editionでは、

```text
context_trace *= decay
context_trace[appeared_symbol] += 1
```

という形で、

> **過去に出現した記号の痕跡**

を別状態として保持します。その痕跡をEdge構造へ投影し、候補scoreへ加算します。

[DOC]

Course Editionではデフォルト無効です。

[EXP-C]

単純な「右右下」教材例では、Slow TraceをONにしても予測結果に変化はありませんでした。

[EXP-R]

Research EditionのQ57gおよび097–100では、研究版Trace機構は概ね負方向または明確な利得なしという結果でした。ただしResearch EditionのTraceには、Course Editionにはない追加機構があります。したがって、

> **Research EditionでのTrace結果を、そのままCourse EditionのSlow Trace性能とみなしてはいけません。**

現在言えるのは、

```text
Course Edition:
教材例では変化なし

Research Edition:
追加機構を含むTrace構成で主に負方向
```

です。

[IDEA]

どんな系列条件ならCourse EditionのSlow Traceが有効になるかは、良い探索課題です。

---

# 14. 🐸の頭を見る

[CODE]

```python
frog.show(prefix)
```

候補ごとに、

```text
direct
history
pair
trace
score
probability
```

を確認できます。概念的には、

```text
score =
    direct
  + history
  + pair
  + trace
```

です(不応期で禁止された候補は0)。`explain()`では、この内訳の合計がEngine本体のscoreと一致することを毎回検査しています。

CSEでは「何がこの予測scoreを作ったか」を直接観察できます。

---

# 15. Frog Presets

## Vanilla Frog

[DOC]

```python
Frog()
```

## Cold Frog

[EXP-C]

```python
Frog(
    temperature=0.05
)
```

候補差を強調します。

## Hot Frog

[EXP-C]

```python
Frog(
    temperature=10.0
)
```

候補分布を平坦化します。

## No-Context Frog

[EXP-C]

```python
Frog(
    pair_context_capacity=0,
    pair_context_boost=0,
)
```

教材例では`下 0.5 / 右 0.5`となりました。

## Forgetful Frog

単純に、

```python
frog.learn(dataset_a)
frog.learn(dataset_b)
```

とするだけでは、古い予測が変化しない場合があります。例えば、

```text
A:
朝 → 起きる → 歯磨き

B:
夜 → 寝る → 夢
```

のようにAとBが別のPrefixを使っている場合です。AのEdge weightが弱くなっていても、`朝 → 起きる`の次候補が依然として`歯磨き`しか存在しなければ、

```text
P(歯磨き) = 1.0
```

のままです。

> **重みが弱くなることと、正規化後の確率が変わることは同じではありません。**

忘却を観察するには、同じPrefixから別のContinuationを競合させます。

[EXP-C]

```python
from cse import Frog

A = [["朝", "起きる", "歯磨き"] * 4]
B = [["朝", "起きる", "二度寝"] * 4]

frog = Frog(weight_decay=0.99)

frog.learn(A, epochs=10)
frog.learn(B, epochs=3)

print(frog.top(["朝", "起きる"]))
```

確認された結果:

| `weight_decay` | Bを3epoch追加後 |
|---|---|
| `1.0` | 歯磨き ≈ 0.985 |
| `0.9995` | 歯磨き ≈ 0.981 |
| `0.99` | 歯磨き ≈ 0.79 / 二度寝 ≈ 0.21 |

さらにraw scoreでは、古い候補の絶対scoreも`3.26 → 2.29`へ低下しました(`weight_decay=0.99`)。

> **忘却は「重みが減った」だけでは出力に見えない。競合候補が現れたとき、初めて確率分布上に見えやすくなる。**

## Trace Frog

[CODE]

```python
Frog(
    context_trace_decay=0.8,
    context_projection_boost=0.5,
)
```

[EXP-C]

単純な教材系列では結果が変わらない場合があります。

> **機構を有効化したことと、そのDatasetで役立ったことは別です。**

---

# 16. Top-pを追加する

[CODE][DOC]

```python
frog.scores(...)
frog.probabilities(...)
```

を使えばSamplerを外部実装できます。

```python
import random

def top_p(frog, prefix, p=0.9):
    items = sorted(
        frog.probabilities(prefix).items(),
        key=lambda kv: -kv[1],
    )

    keep = []
    total = 0.0

    for token, prob in items:
        keep.append((token, prob))
        total += prob

        if total >= p:
            break

    tokens, weights = zip(*keep)

    return random.choices(
        tokens,
        weights=weights,
    )[0]
```

---

# 17. Sampler Pack

[IDEA]

Frog APIだけでも、

```text
Greedy
Top-p
Weighted Random
Temperature + Top-p
Custom Rules
```

などの出力ポリシーを作れます。ただし現在のFrogには、`frog.generate(...)`という標準公開APIはありません。

---

# 18. 🐸を育てる

[CODE][DOC]

```python
frog.learn(dataset_a)
frog.predict(...)

frog.learn(dataset_b)
frog.predict(...)
```

という逐次学習ができます。さらに、

```python
frog.save("my_frog.cse")
frog = Frog.load("my_frog.cse")
frog.learn(dataset_c)
```

と、保存後も続きを学習できます(保存形式はpickleを使わず、JSONと数値配列のzip)。

---

# 19. RAGっぽい構成

[IDEA]

```text
Query
 ↓
External Retriever
 ↓
Relevant Knowledge
 ↓
CSE
 ↓
Prediction
```

という構成を考えられます。ただし、

> **CSE自身をRetrieverとして使う**

方向には既存の否定的証拠があります。

[EXP-R]

研究Q94では、Research Edition CSEによるquery-conditioned retrievalはTF-IDFに大きく負けました。

```text
CSE R@1   ≈ 0.125
TF-IDF    ≈ 0.814
```

したがって現時点では、

```text
❌ CSEに検索まで全部やらせる

✅ Retrievalは検索が得意な手法へ任せる
   CSEは別の役割を担当する
```

という設計の方が研究結果と整合します。

---

# 20. Anomaly Frog

[IDEA]

例えば、

```text
Normal:
A → B → C

Observed:
A → B → X
```

で`P(X | A,B)`が低ければ、

```text
Surprise = -log2(P)
```

として驚き量を計算できます。

[CODE]

現在の`Frog`には、`frog.surprise(...)`という公開APIはありません。現状では、

```python
probs = frog.probabilities(prefix)
p = probs.get(actual, 0.0)
```

から自分で計算します。

[IDEA]

次期API候補:

```python
frog.surprise(
    prefix=["正常", "正常"],
    actual="異常",
)
```

[EXP-R]

100-question challengeでは、CSEは「系列の変化・異常を見る」方向で特徴的な結果を示しました。ただしこれはResearch Editionの結果であり、Course Editionの`Frog`で同一性能が保証されるという意味ではありません。

---

# 21. 🐸 on 🐸 / CSE Colony

[IDEA]

```text
        Router Frog
        /    |    \
       /     |     \
  Frog A   Frog B   Frog C
       \     |     /
        \    |    /
         Selector
```

のような複数CSE構成を作ることはできます。しかし性能主張とは分離します。

[EXP-R]

- H-COL-1では、Colonyの改善は与えられたラベル情報で説明でき、同じラベルを利用するcountingでも同等でした。
- H-COL-2では、同じラベル情報を単体モデルへ与えるとColonyと同スコアになりました。
- H-COL-3では、確率推定の質についてcounting baselineがColonyを上回りました。

したがって、

> **複数Frog化そのものによる性能優位は、現時点では確認されていません。**

それでも、

[IDEA]

- 分業
- Router設計
- Agent構成
- Failure isolation
- Modularity

を試す教材・研究テーマとしては面白いです。

> **🐸 on 🐸は面白い。だが、今のところ強いとは言っていない。**

---

# 22. Agent Frog

[IDEA]

CSEの記号は自然言語である必要はありません。例えば、

```python
[
    "SEARCH",
    "READ",
    "CHECK",
    "ANSWER",
]
```

のような行動系列も扱えます。

```text
Current State
 ↓
CSE
 ↓
Next Action Symbol
 ↓
External Tool
 ↓
New State
```

というAgent-like構成を試すことはできます。ただし現在のCourse Editionに、

- Tool runtime
- Planner
- Agent loop
- Permission system

が標準搭載されているわけではありません。

---

# 23. CSEが苦手なこと

[DOC]

現在の講座版は基本的に局所系列予測器です。遠距離文脈や検索などは得意ではありません。

[EXP-R]

Research Editionの比較では、n-gramなどの既存手法に対して、精度・速度・メモリ・較正等の古典的評価軸で一般的な比較優位は確認されていません。

またH-COL-3では、確率分布について、

> **正解以外の動詞へ約36%の確率質量を与える**

挙動が確認されました。これは「情報を36%失った」という意味ではありません。

> **確率massが誤った候補へ漏れている**

という意味です。

[EXP-R]

H-LEAK-1は事後監査をPASSし、結果が凍結されました。漏れた**確率質量**(正解以外の候補へ行った確率)を、確率を作る3つの成分に分けると、

```text
direct(今の記号「を」だけを見る)  : 約87〜91%
backoffの混合(全候補に薄く配る)   : 約9〜13%
pair(「N_FOOD を」の並び)         : 0   ← 正解のカテゴリだけを指していた
```

でした。この条件では、

```text
「を」
 ↓
複数カテゴリの動詞へdirect edge
```

という構造により、直前1記号だけを見る`direct`成分が複数カテゴリの動詞へscoreを広げていました。一方、Pair Contextは正解のカテゴリだけを指していました。

これはCourse Editionでも、

```text
score =
 direct
 + pair
 + ...
```

という基本構造を`show()`で観察できるため、非常に良い教材テーマになります。ただし、

> **87〜91%という数値はResearch Editionの特定実験条件(107構成、backoffの混合あり)で得られた結果**

であり、Course Edition(backoffの混合なし)のすべてのDatasetで同じ割合になるという意味ではありません。介入はしていないので、「directが原因」とまでは言っていません。

---

# 24. CSEが面白いところ

## Observable

[CODE]

Edge、score、context contributionを直接観察できます。

## Incremental

[CODE]

あとから追加学習できます。

## Configurable

[CODE]

内部挙動をConfigで変更できます。

## Composable

[CODE][IDEA]

score / probabilitiesを外へ出し、Samplerや外部処理を追加できます。

## Hackable

[DOC]

中身を見て、壊して学ぶための設計です。

## Manageably Small

[CODE]

単純に「小さい」とだけ言うより、

> **内部状態を人間が直接追跡・観察しやすい規模**

と表現する方が正確です。`max_nodes`を増やすと主要matrixのサイズは概ね二乗で増えます。

---

# 25. 失敗も結果

このHandbookでは、

```text
Extension ON
 ↓
性能向上！
```

だけを成功とはしません。

```text
Trace ON
 ↓
変化なし
```

も結果。

```text
Colony
 ↓
単体と差なし
```

も結果。

```text
CSE Retriever
 ↓
TF-IDFに負けた
```

も結果です。さらに、

```text
weight_decayを強くした
 ↓
weightは減った
 ↓
でも候補が1つなので確率は100%のまま
```

も重要な結果です。そして、`refractory_steps`を`0 → 1`ではTop-1は同じでも分布が変わり、`1 → 2`では正常な繰返しそのものが禁止されました。

目的は、

> **何を変えると、どの内部量が変わり、それがいつ出力へ現れるのかを見ること。**

です。

---

# 26. Modding Tree

```text
CSE Core
│
├─ Learning Mods
│   ├─ learning_rate
│   ├─ weight_decay
│   └─ temporal learning
│
├─ Context Mods
│   ├─ pair context
│   ├─ history
│   └─ slow trace
│
├─ Prediction Mods
│   ├─ Top-K
│   ├─ temperature
│   └─ probability mode
│
├─ Output Extensions
│   ├─ Top-p
│   ├─ custom sampler
│   └─ generation loop
│
├─ Analysis Extensions
│   ├─ surprise
│   ├─ anomaly score
│   └─ calibration
│
├─ External Systems
│   ├─ Retriever
│   ├─ Memory
│   └─ Tools
│
└─ Multi-CSE
    ├─ Router
    ├─ Colony
    └─ Agent-like systems
```

---

# 27. Recommended Experiments

## Experiment 01 — Cold vs Hot

Temperatureを変更する。

## Experiment 02 — Remove Pair Context

Pair Contextを切り、曖昧化を見る。

## Experiment 03 — Refractory Ladder

`refractory_steps = 0, 1, 2, 5`を順番に変更し、二つのPrefix(`右右`、`右右下`)を同時に測定して、

- Top-1
- probability distribution
- blocked candidate

を比較する。目的は、

> **何個前まで禁止すると、どの位置から系列が壊れるか**

を見ることです。

## Experiment 04 — Competitive Forgetting

```text
A:
朝 → 起きる → 歯磨き

B:
朝 → 起きる → 二度寝
```

のように同一Prefixで競合させる。さらに`probabilities()`と`scores()`の両方を記録し、

> **絶対scoreの低下と正規化後確率の変化**

を別々に見る。

## Experiment 05 — Trace Ablation

Slow Trace ON/OFFで比較。「変化なし」も保存。

## Experiment 06 — Top-p Extension

外部Samplerを追加。

## Experiment 07 — Surprise Extension

`-log2(p)`を計算。

## Experiment 08 — External Retrieval

TF-IDF / BM25等と接続。

## Experiment 09 — Single Frog vs Colony

必ず、**同じ情報を持つ単体モデル**をbaselineに置く。

## Experiment 10 — Direct vs Pair Leakage

[IDEA]

同じ直前Tokenを共有し、より前の文脈だけが異なる系列を学習させ、`direct`・`pair`・final probabilityを`explain()`で比較する。

[EXP-R]

Research EditionではH-LEAK-1により、漏れた確率質量のうち

```text
direct         ≈ 87〜91%
backoffの混合  ≈ 9〜13%
pair           = 0
```

という偏りが確認されています。Course Editionで同様の現象を再現できるかは、別途実験します。

---

# 28. Handbookの研究ルール

Modを追加するときは、

```text
1. Baselineを作る
2. 変更点を1つにする
3. 同じDatasetで比較する
4. Configを保存する
5. scoreとprobabilityを混同しない
6. Top-1だけでなく分布も見る
7. 失敗結果も残す
8. Course / Research Editionを区別する
9. [CODE]/[DOC]/[EXP-C]/[EXP-R]/[IDEA]を付ける
```

ことを推奨します。特に重要なのが、

> **Top-1が同じでも、内部scoreや確率分布は変化している可能性がある。**

という点です。RefractoryとForgetful Frogの両方が、その良い例です。

---

# 29. CSEの最終的な見方

```text
              Extensions
                  │
      ┌───────────┼───────────┐
      │           │           │
   Sampler      Memory      Analysis
      │           │           │
      └───────────┼───────────┘
                  │
               CSE Core
                  │
       Learn / State / Predict
```

CSEは現在、

> **最も正確なLanguage Model**

ではありません。

> **最も巨大なLanguage Model**

でもありません。このHandbookで重視するのは、

> **中身を理解しながら、構成を変え、能力を足し、失敗まで観察できるLanguage Modelの素体**

としての性格です。

---

# Appendix A — ドキュメントの役割

```text
README.md
 └─ 🐸とは何か

docs/REFERENCE.md
 └─ API / Configの正確な仕様

docs/HANDBOOK.md
 └─ 遊び方
    壊し方
    改造方法
    実験方法

Research Reports
 └─ Benchmarks
    Ablations
    Failure Cases
    Comparative Experiments
```

---

# Appendix B — Capability Status

| 機能 | Engine | Frog API | Evidence |
|---|---:|---:|---|
| 学習 | ✅ | ✅ | [CODE][EXP-C] |
| Next-symbol prediction | ✅ | ✅ | [CODE][EXP-C] |
| Probability distribution | ✅ | ✅ | [CODE][EXP-C] |
| Score inspection | ✅ | ✅ | [CODE][EXP-C] |
| Pair Context | ✅ | Config経由 | [CODE][EXP-C] |
| Slow Trace | ✅ | Config経由 | [CODE][EXP-C: 教材例で変化なし] |
| Research Trace | Researchのみ拡張あり | — | [EXP-R: 主に負方向] |
| Refractory | ✅ | Config経由 | [CODE][EXP-C] |
| Save / Load | Wrapper実装 | ✅ | [CODE][EXP-C] |
| Sample generation | ✅ | ❌ direct API | [CODE] |
| Greedy generation | ✅ | ❌ direct API | [CODE] |
| Teacher-forced scoring | ✅ | ❌ direct API | [CODE] |
| Top-p | ❌ built-in | 外部実装可能 | [CODE] |
| Surprise | ❌ public API | ❌ | [IDEA] |
| Retrieval | ❌ standard | ❌ | [EXP-R: CSE retriever不利] |
| Colony | Python上で可能 | 複数Frog可能 | [EXP-R: 性能優位未確認] |
| Agent runtime | ❌ | ❌ | [IDEA] |

---

# Closing

🐸は、何でもできるから面白いのではありません。

**何をすると、何が変わって、何が変わらず、なぜそうなったかを見られる。**

そこが面白い。

```text
Build.
Teach.
Inspect.
Break.
Measure.
Modify.
Repeat.
```

**Welcome to CSE Modding. 🐸🔧**
