# CSE Config Modding Guide 🐸🎛️
## 23 Parameters to Tune, Break, and Study

**Version:** Draft 0.2
**Target:** CSE Course Edition / `Frog`
**Companion:** [`HANDBOOK.md`](HANDBOOK.md) Draft 0.4 / [`REFERENCE.md`](REFERENCE.md)

---

# 0. このGuideの目的

CSEには23個のConfigがあります。

API Referenceは、

> **「この設定は何をするか」**

を説明します。

このModding Guideは、

> **「いじると何が起こるか」**
> **「どのスイッチをONにすると効き始めるか」**
> **「どこまでいじると壊れるか」**
> **「何を観察すると面白いか」**

を扱います。

各Configを、

| 観点 | 意味 |
|---|---|
| **低くすると** | 値を小さくしたときの方向 |
| **高くすると** | 値を大きくしたときの方向 |
| **Prerequisite** | その設定が予測へ効くための前提条件 |
| **何が壊れる？** | 極端な設定で起こりうること |
| **おすすめ実験** | 効果を見るための教材実験 |
| **Evidence** | 実装・講座版実験・研究版実験の根拠 |

で見ていきます。

Evidence LabelはHandbookと共通です。

**[CODE]** 実コード
**[DOC]** README / REFERENCE
**[EXP-C]** Course Editionで確認
**[EXP-R]** Research Editionで確認
**[IDEA]** 未検証の実験案

---

# 1. 重要：Configには「前提スイッチ」がある

[CODE][EXP-C]

CSEのConfigは、すべてが独立して働くわけではありません。

例えば、

```text
activation_decay
```

を変更しても、Frogの標準設定では予測が変わりません。

なぜなら、

```text
activation
 ↓
history term
 ↓
candidate score
```

という経路でしかactivationが予測scoreへ入らないのに、

```text
history_boost = 0
```

がFrogの既定だからです。

つまり、

> **部品は動いていても、その出力先のスイッチがOFFなら最終予測には届かない。**

これはCSEの構造を理解するうえで重要です。

---

# 2. Prerequisite Map

[CODE][EXP-C]

| Setting | Frog既定で効きにくい理由 | 効き始める条件 |
|---|---|---|
| `activation_decay` | activationがscoreへ入るhistory経路がOFF | `history_boost > 0` |
| `threshold` | 同上 | `history_boost > 0` |
| `activation_cap` | 同上 | `history_boost > 0` |
| `top_k_edges`の**spreading側** | propagation結果がhistory経由でscoreへ入らない | `history_boost > 0` |
| `max_consecutive_repeats` | refractoryの例外規則だから | `refractory_steps > 0` |
| `context_trace_decay` | Trace単体ではscoreへ入らない | `context_projection_boost > 0` |
| `temporal_learning_decay` | 距離2以上を学ばないと距離減衰が発生しない | `temporal_learning_window >= 2` |
| `direct_learning_window` | 距離2以上を学ばないと境界の意味がない | `temporal_learning_window >= 2` |

さらに`top_k_edges`には別の仕事があります。

候補確率を上位K個へ絞る機能は、

> **positive candidateがK個を超えたとき**

に初めて違いが表面化します。

つまり同じConfigでも、

```text
top_k_edges
├─ candidate limiting
└─ activation spreading
```

で発動条件が異なります。

---

# 3. Config Map

```text
Prediction
├─ probability_mode
├─ temperature
├─ top_k_edges
├─ history_boost
├─ refractory_steps
└─ max_consecutive_repeats

Context
├─ pair_context_capacity
├─ pair_context_boost
├─ context_trace_decay
└─ context_projection_boost

Learning
├─ learning_rate
├─ max_edge_weight
├─ weight_decay
├─ weight_decay_scope
├─ temporal_learning_window
├─ direct_learning_window
├─ temporal_learning_decay
└─ normalize_direct_scores

Activation
├─ activation_decay
├─ threshold
└─ activation_cap

System
├─ max_nodes
└─ seed
```

---

# 4. 全23Config早見表

| Config | Frog既定 | 低くすると | 高くすると | Prerequisite / 注意 | Evidence |
|---|---:|---|---|---|---|
| `probability_mode` | `"softmax"` | — | — | Top-`top_k_edges`候補だけを確率化 | [CODE] |
| `temperature` | `0.8` | 分布が尖る | 平坦化 | `softmax`時のみ | [EXP-C] |
| `top_k_edges` | `3` | 候補・伝播を絞る | 多く残す | spreadingは`history_boost>0`で予測へ反映。候補制限はpositive候補>Kで発動 | [CODE][EXP-C] |
| `history_boost` | `0.0` | 履歴効果減少 | 最近の記号を押し上げる | これ自体がactivation系の主スイッチ | [EXP-C][EXP-R] |
| `refractory_steps` | `0` | 禁止範囲減少 | 過去記号を長く禁止 | — | [EXP-C] |
| `max_consecutive_repeats` | `2` | 反復を早く止める | 反復を許す | `refractory_steps>0` | [CODE][EXP-C] |
| `pair_context_capacity` | `2048` | Pair減少 | Pair増加 | 0で無効 | [EXP-C] |
| `pair_context_boost` | `1.0` | Pair影響減少 | Pair影響増加 | Pairは合計1へ正規化後に加算 | [CODE] |
| `context_trace_decay` | `0.0` | 痕跡が早く消える | 長く残る | `context_projection_boost>0` | [EXP-C][EXP-R] |
| `context_projection_boost` | `0.0` | Trace影響減少 | Trace影響増加 | 既存positive候補だけへ加算 | [CODE] |
| `learning_rate` | `0.1` | 学習遅い | 学習速い | — | [CODE] |
| `max_edge_weight` | `10.0` | 早く飽和 | 大きなweight許可 | — | [CODE] |
| `weight_decay` | `0.9995` | direct/context忘却が速い | 1.0で減衰なし | **Pair memoryは減衰しない** | [CODE][EXP-C] |
| `weight_decay_scope` | `"global"` | — | — | direct/context weightの減衰範囲 | [CODE] |
| `temporal_learning_window` | `1` | 近距離のみ | 遠距離も学習 | — | [CODE] |
| `direct_learning_window` | `2` | direct範囲縮小 | direct範囲拡大 | `temporal_learning_window>=2` | [CODE] |
| `temporal_learning_decay` | `0.5` | 遠距離を弱く学習 | 遠距離も強く学習 | `temporal_learning_window>=2` | [CODE] |
| `normalize_direct_scores` | `False` | — | — | Trueでdirect行を合計1へ正規化 | [CODE] |
| `activation_decay` | `0.6` | 活性が早く消える | 長く残る | `history_boost>0` | [EXP-C] |
| `threshold` | `0.05` | 弱い活性も伝播 | 強い活性だけ伝播 | `history_boost>0` | [EXP-C] |
| `activation_cap` | `0.0` | 小さいcapでclip | 大きいcap | `history_boost>0` | [EXP-C] |
| `max_nodes` | `256` | 軽量・語彙減 | 語彙増・RAM増 | memory ≈ O(N²) | [CODE][DOC] |
| `seed` | `42` | — | — | deterministic Frog APIでは通常影響なし | [CODE][DOC] |

---

# 5. `probability_mode`

**Default:** `"softmax"`

[CODE][DOC]

```python
Frog(probability_mode="softmax")
Frog(probability_mode="linear")
```

どちらの場合も、まずcandidate scoreが計算されます。

そして、

> **positive scoreの上位`top_k_edges`候補だけ**

が確率化されます。

つまり、

```text
scores
 ↓
Top-K candidate selection
 ↓
softmax OR linear normalization
```

です。

## softmax

```text
score / temperature
 ↓
exp()
 ↓
normalize
```

## linear

```text
score
 ↓
normalize
```

### 注意

`linear`にするとTop-Kが無効になるわけではありません。

**softmaxでもlinearでもTop-K candidate selectionは先に行われます。**

### おすすめ実験

同じ`scores()`に対して、

```text
softmax
vs
linear
```

の`probabilities()`を比較。

---

# 6. `temperature`

**Default:** `0.8`

[CODE][EXP-C]

`probability_mode="softmax"`時のみ有効です。

## 低くすると

確率分布が尖ります。

## 高くすると

分布が平坦化します。

[EXP-C]

```text
0.05 → 下 ≈ 1.0
10.0 → 下 ≈ 0.525
```

### Prerequisite

```text
probability_mode = "softmax"
```

`linear`ではtemperatureは使われません。

### おすすめ実験

```text
0.05
0.2
0.8
2
10
```

を比較。

---

# 7. `top_k_edges`

**Default:** `3`

[CODE]

CSEで最も注意が必要な名前の一つです。

二つの役割があります。

## A. Candidate Limiting

positive candidateのうち、上位K個だけを確率化します。

これは、

```text
positive candidates > top_k_edges
```

のときに初めて結果差が出ます。

## B. Activation Spreading

各Nodeから活性を広げるとき、強いK本のEdgeだけを使用します。

### Prerequisite

[EXP-C]

Frog既定では、

```text
history_boost = 0
```

なので、activation propagationを変えても、その差がcandidate scoreへ入りません。

Spreading側の効果を見るなら、

```python
Frog(
    history_boost=0.35,
    top_k_edges=...
)
```

のようにする必要があります。

### 何が壊れる？

Kが小さすぎる:

> 有望な候補や伝播経路を早期に切る。

Kが大きすぎる:

> 弱い候補やEdgeも残る。

---

# 8. `history_boost`

**Frog default:** `0.0`
**Engine default:** `0.35`

[CODE]

activation historyをcandidate scoreへ足す倍率です。

このConfigはactivation系設定の**主電源**に近い存在です。

```text
activation
 ↓
× history_boost
 ↓
candidate score
```

## 0

Frog既定。

Activationは内部で存在しても、history termとしてscoreへ入りません。

## 正にすると

最近活性化した記号を押し上げます。

## 負にすると

[EXP-C]

`history_boost=-0.3`では、教材実験で候補scoreがすべて消え、

```text
<END> = 1.0
```

となりました。

つまり負値は、

> 最近の記号を抑制する

程度では済まず、candidate set全体を消す場合があります。

### Research Result

[EXP-R]

H-GEN-2では、

```text
history_boost = 0.35
        ↓
history_boost = 0
```

へ変更すると、**最初の生成逸脱が遅れました**。

つまりこの実験では、

> History termを外した方が生成崩壊が遅くなった

という結果です。

「Historyを入れると必ず悪い」という一般則ではありません。

---

# 9. `refractory_steps`

**Default:** `0`

[CODE][EXP-C]

最近出た記号を何個前まで禁止するか。

| steps | 「右右」の次 | 「右右下」の次 |
|---:|---|---|
| 0 | 下 0.777 / 右 0.223 | 右 0.865 |
| 1 | 下 1.0 | 右 0.865 |
| 2 | 下 1.0 | `<END>` 1.0 |
| 5 | 下 1.0 | `<END>` 1.0 |

非常に良い教材Configです。

---

# 10. `max_consecutive_repeats`

**Default:** `2`

[CODE]

Refractoryの例外規則です。

### Prerequisite

```text
refractory_steps > 0
```

でなければ意味を持ちません。

これは、

> 「禁止されているけど、学習済みself-loopなら何回まで許す？」

を決めます。

### おすすめ実験

```text
A → A → A → B
```

を学習して、

```text
refractory_steps = 2
max_consecutive_repeats = 1 / 2 / 3
```

を比較。

---

# 11. `pair_context_capacity`

**Frog default:** `2048`

[CODE][EXP-C]

直前2Tokenの組を何種類保存するか。

`0`で無効。

[EXP-C]

No-Context Frogでは教材例が、

```text
下 0.5
右 0.5
```

になりました。

Capacityが満杯になると、弱いPairから追い出されます。

---

# 12. `pair_context_boost`

**Default:** `1.0`

[CODE]

ここはScaleに注意が必要です。

Pair rowは使用時に、

```text
pair_scores / pair_total
```

と合計1へ正規化されます。

そのあと、

```text
× pair_context_boost
```

してcandidate scoreへ加えられます。

一方、Frog既定ではDirect scoreは、

```text
raw edge weight
```

のままです。

Edge weightは最大`10.0`まで持てます。

したがって標準状態では、

> **DirectとPairはそもそも同じScaleではありません。**

### `normalize_direct_scores=True`

これをONにするとDirect側も合計1へ正規化され、

```text
Direct : normalized
Pair   : normalized
```

となります。

このとき両者は比較しやすいScaleになります。

### Research connection

[EXP-R]

H-LEAK-1のResearch Editionでは`normalize_direct_scores=True`を使用していました。

そこでは誤候補への最終probability massについて、

```text
direct         : 約87〜91%
backoff mixing : 約9〜13%
pair memory    : 0%
```

でした。

Pair Memoryは正しいカテゴリだけを指し、漏洩源になりませんでした。

ただしResearch EditionにはCourse Editionに存在しないbackoff mixingがあります。

---

# 13. `context_trace_decay`

**Default:** `0.0`

[CODE]

Traceが1Tokenごとにどれだけ残るか。

### Prerequisite

```text
context_projection_boost > 0
```

でなければ、Traceを変更してもpredictionへ反映されません。

これは非常に重要です。

```text
Traceを作る
 ↓
projectionがOFF
 ↓
scoreへ入らない
 ↓
predictは変わらない
```

### Evidence

[EXP-C]

単純な教材例ではTraceを有効化しても変化なし。

[EXP-R]

Research Editionの追加Trace機構も主に負方向。

両者は同じ機構ではないので結果を混同しません。

---

# 14. `context_projection_boost`

**Default:** `0.0`

[CODE]

TraceをEdge構造へ投影し、candidate scoreへ足す倍率です。

ただし重要な制約があります。

Projectionは、

> **すでにpositive scoreを持つcandidate**

にしか加算されません。

つまり、

```text
score = 0
```

だった全く新しいcandidateを、Traceだけで突然生み出すことはできません。

概念的には、

```text
existing candidates
       ↓
Traceが順位・scoreを補正
```

です。

### 何が壊れる？

Boostを上げても、

> Candidate generation能力そのものが増える

わけではありません。

既存候補間のbiasが強まります。

---

# 15. `learning_rate`

**Default:** `0.1`

[CODE]

1回観測するたびにEdgeをどれだけ増やすか。

低い:

> ゆっくり学習。

高い:

> 少数観測で強く学習。

高すぎると`max_edge_weight`へ早く到達します。

---

# 16. `max_edge_weight`

**Default:** `10.0`

[CODE]

Direct / Context / Pair learningの上限。

低いと早く飽和。

高いと頻度差を長く保持できます。

---

# 17. `weight_decay`

**Default:** `0.9995`

ここは重要な修正点です。

[CODE][EXP-C]

`weight_decay`が減衰させるのは、

```text
direct weights
context weights
```

です。

**Pair Context Memoryにはweight_decayが適用されません。**

つまり、

```text
Direct / Context
 ↓
decay

Pair Memory
 ↓
decayしない
```

です。

[EXP-C]

`x → y → z`を3系列×3エポック(36学習step)、`weight_decay=0.9`で学習した実験では、

- Direct weightの合計は、減衰なし(`1.0`)の`3.6`に対して`0.98`まで減衰
- Pair Memoryの合計は`2.7`(= 0.1 × 27回の更新。減衰なしの値そのもの)

でした。

したがって、

> **FrogのPair Memoryはweight_decayによる忘却をしない。**

正確には、新しいPair学習によって値は更新されますが、`weight_decay`による時間減衰を受けません。

---

## 17.1 Trap A — 重みが減っても確率が変わらない

例えば、

```text
A:
朝 → 起きる → 歯磨き

B:
夜 → 寝る → 夢
```

のようにPrefixが競合しない場合。

古いDirect weightが減っても、

```text
朝 → 起きる
```

の候補が`歯磨き`しかなければ、

```text
P(歯磨き) = 1.0
```

のままです。

> **絶対scoreが下がることと、正規化後確率が下がることは別。**

---

## 17.2 Trap B — 競合すると確率に見える

[EXP-C]

```python
A = [["朝", "起きる", "歯磨き"] * 4]
B = [["朝", "起きる", "二度寝"] * 4]
```

のように同一Prefixで競合させると、

| decay | B追加後 |
|---|---|
| 1.0 | 歯磨き ≈ 0.985 |
| 0.9995 | 歯磨き ≈ 0.981 |
| 0.99 | 歯磨き ≈ 0.79 / 二度寝 ≈ 0.21 |

となりました。

この**競合実験**で、古い候補のraw scoreは、

```text
3.26 → 2.29
```

へ低下しました。

この数値は、

> 「確率が1.0のままだった非競合ケース」

のものではありません。

---

## 17.3 Pair Memoryが忘れないという意味

ここがCSEとして面白いところです。

同一PrefixのPairを学習している場合、

```text
Direct
 └─ weight_decayを受ける

Pair
 └─ decayしない
```

ので、長期的には両者の相対バランスが変化する可能性があります。

したがってCompetitive Forgettingは、

> **CSE全体が一様に忘れている**

と解釈してはいけません。

より正確には、

> **Direct / Context系は減衰する一方、Pair Memoryはweight_decayでは忘れない。**

です。

これは今後の重要な教材テーマです。

---

# 18. `weight_decay_scope`

**Default:** `"global"`

[CODE]

```text
global
active_rows
```

から選択。

`global`は全Direct / Context weight。

`active_rows`は現在学習に関係するRowだけ。

なお、

> **どちらを選んでもPair Memoryはweight_decay対象外**

です。

---

# 19. `temporal_learning_window`

**Default:** `1`

[CODE]

何個前まで遡って現在Tokenとの関係を学習するか。

```text
1
→ 直前だけ

2
→ 2個前まで

3
→ 3個前まで
```

ただし、すべてが同じMatrixへ入るわけではありません。

Frog既定の、

```text
direct_learning_window = 2
```

では、

```text
distance 1 → direct weight
distance 2 → direct weight
distance 3+ → context weight
```

です。

### 重要

`frog.edges()`が表示するのはDirect Edgeです。

したがって、

```text
A → x → x → B
```

でAからBはdistance 3。

`temporal_learning_window >= 3`なら関係自体は学習できますが、

```text
A → B
```

は**context weightへ入るため`edges("A")`には出ません。**

### おすすめ実験

```text
A B C D E
```

で、

```text
window = 1 / 2 / 3 / 4
```

を変える。

観察:

```text
distance 1–2:
edges()

distance 3+:
Trace + Projectionを有効にして予測への影響を見る
```

---

# 20. `direct_learning_window`

**Default:** `2`

[CODE]

Temporal Learning Window内の関係を、

```text
Direct
or
Context
```

どちらへ保存するかの境界。

### Prerequisite

```text
temporal_learning_window >= 2
```

でなければ実質的な意味がありません。

例えば、

```text
temporal_learning_window = 1
```

ならdistance 2以上をそもそも学習しないため、

```text
direct_learning_window = 1
2
3
```

を変えても差が出ません。

### 低くすると

遠い関係をContext Matrixへ回します。

### 高くすると

遠い関係までDirect Matrixへ入れます。

---

# 21. `temporal_learning_decay`

**Default:** `0.5`

[CODE]

距離が遠い関係をどれだけ弱く学習するか。

### Prerequisite

```text
temporal_learning_window >= 2
```

が必要。

Window=1ならdistance 2以上が存在しないため、Decayを変えても結果は変わりません。

### おすすめ実験

```text
A B C D
```

について、

```text
temporal_learning_window = 3
```

を固定し、

```text
temporal_learning_decay =
0.1
0.5
1.0
```

を比較。

---

# 22. `normalize_direct_scores`

**Default:** `False`

[CODE]

False:

```text
Direct = raw weight
```

True:

```text
Direct row / positive row sum
```

とします。

これはPairとの比較で重要。

Pairは元々、

```text
pair row / positive row sum
```

なので、

```python
normalize_direct_scores=True
```

にすると、

```text
Direct ≈ normalized scale
Pair   ≈ normalized scale
```

になります。

[EXP-R]

H-LEAK-1はこの設定でDirectとPairを比較しています。

---

# 23. `activation_decay`

**Default:** `0.6`

[CODE][EXP-C]

1stepごとにActivationをどれだけ残すか。

### Prerequisite

```text
history_boost > 0
```

Frog既定では`history_boost=0`なので、

> activation_decayだけ変えてもPredictionは変わりません。

これは「設定が壊れている」のではなく、

```text
Activation
 ↓
History Score

History Score × 0
 ↓
0
```

だからです。

### おすすめ実験

```python
Frog(
    history_boost=0.35,
    activation_decay=...
)
```

として、

```text
0.1
0.6
0.9
```

を比較。

---

# 24. `threshold`

**Default:** `0.05`

[CODE][EXP-C]

どのActivationから先へ伝播を許すか。

### Prerequisite

```text
history_boost > 0
```

Predictionへの変化を見るにはHistory pathwayが必要です。

## 低い

弱いactivationも広がる。

## 高い

強いactivationだけ伝播。

### Trap

Frog既定でthresholdだけ変えて、

```text
何も変わらない！
```

となるのは正常です。

---

# 25. `activation_cap`

**Default:** `0.0`

[CODE][EXP-C]

Activationの上限。

`0`は無制限ではなく、自動安全上限。

### Prerequisite

```text
history_boost > 0
```

Predictionへ影響させるにはHistory経路をONにする必要があります。

### 小さくすると

強いactivationを早くclip。

### 高くすると

より大きなactivationを残せる。

---

# 26. `max_nodes`

**Frog default:** `256`

[CODE][DOC]

利用者Tokenは、

```text
256 - 3 special nodes
= 253
```

まで。

Main matricesは概ね、

```text
N × N
```

なので、メモリは二乗で増えます。

---

# 27. `seed`

**Default:** `42`

[CODE][DOC]

Frogの通常の、

```text
learn
predict
top
probabilities
```

は決定論的。

seedを変えても通常結果は変わりません。

Engine内部のsample generation等で乱数を使う場合に意味を持ちます。

---

# 28. Config Dependency Graph

今回の実験で、Configを単独のツマミとして見るだけでは不十分なことが分かりました。

```text
activation_decay ─┐
threshold ─────────┼──► activation
activation_cap ────┘        │
                            ▼
                     history_boost
                            │
                            ▼
                     candidate score


context_trace_decay
        │
        ▼
 context_trace
        │
        ▼
context_projection_boost
        │
        ▼
 existing candidates only


temporal_learning_window
        │
        ├──► temporal_learning_decay
        │
        └──► direct_learning_window
                  │
             ┌────┴────┐
             ▼         ▼
          direct     context


refractory_steps
        │
        ▼
 candidate blocking
        │
        └── max_consecutive_repeats
             （例外規則）
```

Configは、

> **23個の独立したノブ**

ではありません。

むしろ、

> **依存関係を持つ小さな回路**

です。

---

# 29. 「何も変わらない」には2種類ある

これは今回かなり重要な発見です。

## Type A — 内部では変化したが、出力に見えない

例:

```text
weight_decay
```

scoreは減っている。

しかし候補が1つなので、

```text
probability = 1.0
```

のまま。

---

## Type B — そもそもPrediction経路がOFF

例:

```text
activation_decay
```

だけ変更。

しかし、

```text
history_boost = 0
```

なのでActivation差がscoreへ届かない。

この場合は、

> **本当にPredictionへは何も起きていない。**

---

この二つを区別します。

```text
predict()同じ
       │
       ├─ scoreは変わった？
       │      ├─ YES → Type A
       │      └─ NO
       │
       └─ prerequisiteはON？
              ├─ NO → Type B
              └─ YES → 別の理由を調査
```

これはCSEを解剖する際の重要な診断フローです。

---

# 30. Recommended Experiment Pack

## 01 Temperature Ladder

```text
0.05 → 0.2 → 0.8 → 2 → 10
```

---

## 02 Refractory Ladder

```text
0 → 1 → 2 → 5
```

---

## 03 Pair Context ON/OFF

```text
capacity 2048
vs
0
```

---

## 04 Competitive Forgetting

同じPrefixに別Continuationを学習。

さらに、

```text
Direct
Pair
Probability
```

を別々に観察。

---

## 05 Activation Wake-Up

まず、

```text
history_boost = 0
```

で、

```text
activation_decay
threshold
activation_cap
```

を変更。

→ Prediction変化なし。

その後、

```text
history_boost = 0.35
```

へ変更。

→ Activation系Configが「生きる」かを見る。

これはPrerequisiteの概念を理解する最良の教材候補です。

---

## 06 Trace Wake-Up

```text
context_projection_boost = 0
```

の状態で`context_trace_decay`を変更。

→ Prediction変化なし。

次にProjectionをON。

```text
context_projection_boost > 0
```

→ TraceがPredictionへ届く。

---

## 07 Temporal Wake-Up

```text
temporal_learning_window = 1
```

で、

```text
temporal_learning_decay
direct_learning_window
```

を変更。

→ 差なし。

次に、

```text
temporal_learning_window = 3
```

へ。

→ 距離2・3の学習差を見る。

---

## 08 Direct vs Pair Scale

```text
normalize_direct_scores = False
```

と、

```text
True
```

を比較。

`explain()`で、

```text
direct
pair
score
probability
```

を見る。

---

# 31. 実験するときのチェックリスト

Configを変えたら、

```text
□ そのConfigのPrerequisiteはONか？
□ predict()だけで判断していないか？
□ top()で分布を見たか？
□ scores()でraw scoreを見たか？
□ explain()で成分を分解したか？
□ DirectとPairを混同していないか？
□ weight decay対象のMemoryか？
□ Course EditionとResearch Editionを混ぜていないか？
```

を確認します。

---

# 32. Config Difficulty

| Level | Config |
|---|---|
| 🐸 Easy | `temperature`, `refractory_steps`, `pair_context_capacity`, `weight_decay` |
| 🐸🐸 Medium | `top_k_edges`, `pair_context_boost`, `learning_rate`, `max_nodes`, `probability_mode` |
| 🐸🐸🐸 Advanced | `history_boost`, `context_trace_decay`, `context_projection_boost`, `activation_decay`, `threshold`, `activation_cap` |
| 🔬 Research | `temporal_learning_window`, `direct_learning_window`, `temporal_learning_decay`, `normalize_direct_scores`, `weight_decay_scope`, `max_edge_weight` |

---

# 33. 23 Config Checklist

| # | Config |
|---:|---|
| 1 | `max_nodes` |
| 2 | `learning_rate` |
| 3 | `max_edge_weight` |
| 4 | `weight_decay` |
| 5 | `weight_decay_scope` |
| 6 | `activation_decay` |
| 7 | `activation_cap` |
| 8 | `threshold` |
| 9 | `top_k_edges` |
| 10 | `temperature` |
| 11 | `probability_mode` |
| 12 | `history_boost` |
| 13 | `refractory_steps` |
| 14 | `max_consecutive_repeats` |
| 15 | `temporal_learning_window` |
| 16 | `direct_learning_window` |
| 17 | `temporal_learning_decay` |
| 18 | `context_trace_decay` |
| 19 | `context_projection_boost` |
| 20 | `normalize_direct_scores` |
| 21 | `pair_context_capacity` |
| 22 | `pair_context_boost` |
| 23 | `seed` |

**23 / 23 covered. 🐸✅**

---

# Closing

最初は23個のConfigが、

```text
23個のツマミ
```

に見えます。

でも実際には、

```text
Switch
 ↓
Subsystem
 ↓
Another Config
 ↓
Candidate Score
 ↓
Top-K
 ↓
Probability
```

という依存構造を持っています。

だから、

> **設定を変えたのに何も起きない**

こと自体がバグとは限りません。

前提となる回路がOFFなのかもしれない。

逆に、

> **predict()は同じなのに、中では大きく変わっている**

こともあります。

CSE Moddingでは、

**Outputを見る。
Scoreを見る。
Componentを見る。
そして、回路を見る。**

それが🐸の解剖です。

**Tune it. Wake it. Break it. Explain it. 🐸🎛️🔬**
