# 開発メモ(配布前)

## 決定済み(2026-10-03)
- **名前**: パッケージ名・import名は `cse`(`from cse import Frog`)。PyPI で `cse` が登録できない場合は、配布名だけを変える(例 `cse-lm`)。import名は `cse` のまま。
- **ライセンス**: MIT。著作権表示 `Copyright (c) 2026 Emilia Lab / 鍵乃ねこ (kagioneko)`。再配布・公開時はこの表示を残す(MITの条件)。
- **系列の終わり**: 専用の目印 `cse.END`(表示は `<END>`)。利用者の記号とはぶつからない。
- **研究版との一致**: README に一文だけ書く。一致テスト本体は配布しない。
- **エンジン**: `src/cse/_engine.py` は講座版エンジン `course/cse_course_engine.py`(研究リポジトリ)の無変更のコピー。sha256(LF改行) `a7af714753e4e0a260b354fd280f77444f93b44957b2e2af432b04bc8f2d87c9`。研究版の `cse/` パッケージ・`chain_spike_phase0.py` は含めない。

## 保留・後回し
- **FTO(他社特許の侵害予防調査)**: 有償化・商用利用の前に弁理士へ(講座版エンジンに含まれる機能の範囲で)。AIとの検索は代わりにならない。
- **初心者向けの既定値**: 今の5項目のまま(2026-10-03ユーザー決定: 「壊して遊ぶ」が基本なので、設定を `Frog(...)` で簡単にいじれればよい)。READMEに「設定をいじって壊して遊ぶ」の節を追加。

## 公開前に直す・書くこと(エンジンの癖)
- エンジンを作ると `random.seed` / `np.random.seed` がプロセス全体で呼ばれ、利用者の乱数がリセットされる。
- `next_node_distribution` は呼ぶたびに内部状態を変える(スレッドセーフでない)。
- `max_nodes` が語彙の上限で、`max_nodes × max_nodes` の行列を最初に確保する。
- 開発時の注意: 研究リポジトリの中では、研究版の `cse/` が先に読み込まれるので、この配布版を試さない。

## 公開の手順(すべて明示のOKをもらってから)
1. GitHub の公開リポジトリ作成 → 2. TestPyPI → `pip install` と Colab で確認 → 3. 本番 PyPI。

## 既定値についての訂正(2026-10-03)
- `Frog()` が変えるのは `refractory_steps=0`・`history_boost=0.0`・`pair_context_capacity=2048`・`pair_context_boost=1.0`・`max_nodes=256` の5項目だけ。他は講座版エンジンの既定値(`probability_mode="softmax"`・温度0.8・`top_k_edges=3`・`max_edge_weight=10`・`weight_decay=0.9995` など)。
- **研究の107の構成とは別物**(107は linear・`top_k_edges=50`・`max_edge_weight=100`・`weight_decay=1.0`・`normalize_direct_scores=True` など。講座版エンジンには `distribution_backoff_mix` 自体がない)。以前「107型」と書いたのは不正確だった。
- 既定値の決め方(案): 小さなデモ課題(右右下、故障の系列、じゃんけん など)と選び方の基準を先に書いてから候補を比べ、変な予測が一番少ないものにする。
