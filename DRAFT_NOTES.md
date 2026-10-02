# 開発メモ(配布前)

## 決定済み(2026-10-03)
- **名前**: パッケージ名・import名は `cse`(`from cse import Frog`)。PyPI で `cse` が登録できない場合は、配布名だけを変える(例 `cse-lm`)。import名は `cse` のまま。
- **ライセンス**: MIT。著作権表示 `Copyright (c) 2026 Emilia Lab / 鍵乃ねこ (kagioneko)`。再配布・公開時はこの表示を残す(MITの条件)。
- **系列の終わり**: 専用の目印 `cse.END`(表示は `<END>`)。利用者の記号とはぶつからない。
- **研究版との一致**: README に一文だけ書く。一致テスト本体は配布しない。
- **エンジン**: `src/cse/_engine.py` は講座版エンジン `course/cse_course_engine.py`(研究リポジトリ)の無変更のコピー。sha256(LF改行) `a7af714753e4e0a260b354fd280f77444f93b44957b2e2af432b04bc8f2d87c9`。研究版の `cse/` パッケージ・`chain_spike_phase0.py` は含めない。

## 保留・後回し
- **FTO(他社特許の侵害予防調査)**: 有償化・商用利用の前に弁理士へ(講座版エンジンに含まれる機能の範囲で)。AIとの検索は代わりにならない。
- **初心者向けの既定値**(`Frog()` の `_SAFE_DEFAULTS`: `refractory_steps=0`、`history_boost=0.0`、pair context 2048/1.0、`max_nodes=256`)は再検討中。

## 公開前に直す・書くこと(エンジンの癖)
- エンジンを作ると `random.seed` / `np.random.seed` がプロセス全体で呼ばれ、利用者の乱数がリセットされる。
- `next_node_distribution` は呼ぶたびに内部状態を変える(スレッドセーフでない)。
- `max_nodes` が語彙の上限で、`max_nodes × max_nodes` の行列を最初に確保する。
- 開発時の注意: 研究リポジトリの中では、研究版の `cse/` が先に読み込まれるので、この配布版を試さない。

## 公開の手順(すべて明示のOKをもらってから)
1. GitHub の公開リポジトリ作成 → 2. TestPyPI → `pip install` と Colab で確認 → 3. 本番 PyPI。
