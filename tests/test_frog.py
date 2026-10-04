import math
import random

import pytest

from cse import END, Frog


def trained():
    return Frog().learn([list("右右下右右下右右下"), list("右右下右右下")], epochs=5)


def test_right_right_down():
    f = trained()
    assert f.predict(["右", "右"]) == "下"
    assert f.predict(["右", "右", "下"]) == "右"


def test_plain_string_prefix_and_input():
    f = trained()
    assert f.predict("右右") == "下"


def test_multichar_tokens_stay_intact():
    f = Frog().learn([["正常", "正常", "温度上昇", "振動増加", "停止"]] * 3)
    assert f.predict(["正常", "温度上昇", "振動増加"]) == "停止"
    assert "停止" in f.probabilities(["振動増加"])


def test_probabilities_sum_to_one():
    f = trained()
    for prefix in ([], ["右"], ["右", "右"], ["右", "右", "下"]):
        assert math.isclose(sum(f.probabilities(prefix).values()), 1.0, abs_tol=1e-9)


def test_end_sentinel_is_none():
    f = Frog().learn([["a", "b"]] * 5)
    assert repr(END) == "<END>" and str(END) == "<END>" and END != "<END>"
    assert f.predict(["a", "b"]) is END


def test_unknown_token_error():
    f = trained()
    with pytest.raises(ValueError, match="まだ覚えていない"):
        f.predict(["左"])


def test_unknown_setting_error():
    with pytest.raises(ValueError, match="知らない設定"):
        Frog(not_a_setting=1)


def test_top_sorted():
    t = trained().top(["右"], k=2)
    assert len(t) == 2 and t[0][1] >= t[1][1]


def test_overrides_change_behaviour():
    data = [["右", "右", "下"] * 5]
    assert Frog().config.refractory_steps == 0
    f = Frog(refractory_steps=2).learn(data)
    assert f.config.refractory_steps == 2
    assert f.predict(["右", "右", "下"]) is END        # the refractory trap, reproduced on purpose
    assert Frog().learn(data).predict(["右", "右", "下"]) == "右"


def test_user_random_state_is_not_reset():
    import random
    import numpy as np
    random.seed(123)
    np.random.seed(123)
    expected_py, expected_np = random.random(), np.random.rand()
    random.seed(123)
    np.random.seed(123)
    Frog()                                         # the engine seeds globally inside; Frog must restore
    assert random.random() == expected_py and np.random.rand() == expected_np


def test_predictions_do_not_drift_and_are_thread_safe():
    from concurrent.futures import ThreadPoolExecutor
    f = Frog().learn([["右", "右", "下"] * 5, ["正常", "温度上昇", "振動増加", "停止"] * 3])
    prefixes = [["右", "右"], ["右", "右", "下"], ["正常", "温度上昇"], ["振動増加"]] * 25
    sequential = [f.probabilities(p) for p in prefixes]
    assert sequential[:4] == sequential[4:8]       # repeated calls give identical results (no hidden drift)
    with ThreadPoolExecutor(max_workers=8) as ex:
        parallel = list(ex.map(f.probabilities, prefixes))
    assert parallel == sequential


def test_learn_input_shapes():
    flat = Frog().learn(["右", "右", "下"] * 3)                 # one flat list = ONE sequence (beginner trap fixed)
    nested = Frog().learn([["右", "右", "下"] * 3])
    string = Frog().learn("右右下" * 3)
    assert flat.probabilities(["右", "右"]) == nested.probabilities(["右", "右"]) == string.probabilities("右右")
    assert flat.predict(["右", "右"]) == "下"
    many = Frog().learn([["正常", "温度上昇", "停止"], ["右", "右", "下"]])
    assert many.predict(["正常", "温度上昇"]) == "停止" and many.predict(["右", "右"]) == "下"
    import pytest
    with pytest.raises(ValueError):
        Frog().learn([["右"], "下"])                          # mixed shapes are rejected with a Japanese message


import pytest


@pytest.mark.parametrize("overrides", [
    {},
    {"refractory_steps": 2},
    {"history_boost": 0.35},
    {"context_trace_decay": 0.9, "context_projection_boost": 0.5},
    {"normalize_direct_scores": True, "probability_mode": "linear"},
    {"pair_context_capacity": 0, "pair_context_boost": 0.0},
])
def test_explain_matches_engine(overrides):
    data = [["右", "右", "下"] * 5, ["正常", "温度上昇", "振動増加", "停止"] * 3]
    f = Frog(**overrides).learn(data)
    for prefix in (["右", "右"], ["右", "右", "下"], ["正常", "温度上昇"], ["停止"]):
        rows = f.explain(prefix, k=100)                # _inside() raises if the rebuilt score != engine score
        probs = f.probabilities(prefix)
        scores = f.scores(prefix)
        for r in rows:
            parts = r["direct"] + r["history"] + r["pair"] + r["trace"]
            if r["blocked"]:
                assert r["score"] == 0.0 and parts > 0
            else:
                assert abs(r["score"] - parts) < 1e-12
                assert scores[r["token"]] == r["score"]
        # explain's probabilities are the engine's (renormalized without <START>/<UNK> in probabilities())
        total = sum(r["prob"] for r in rows if r["prob"] > 0)
        for r in rows:
            if r["prob"] > 0:
                assert abs(probs[r["token"]] - r["prob"] / total) < 1e-12


def test_refractory_block_is_visible():
    f = Frog(refractory_steps=2).learn([["右", "右", "下"] * 5])
    rows = {r["token"]: r for r in f.explain(["右", "右", "下"], k=10)}
    assert rows["右"]["blocked"] and rows["右"]["score"] == 0.0
    assert f.predict(["右", "右", "下"]) is END


def test_edges_and_explain_errors():
    f = Frog().learn([["右", "右", "下"] * 5])
    assert {t for t, _ in f.edges("右")} == {"右", "下"}
    with pytest.raises(ValueError):
        f.edges("左")


def test_explain_detects_a_mismatch():
    f = Frog().learn([["右", "右", "下"] * 5])
    original = f._engine._candidate_scores

    def tampered(current_id):                         # negative control: engine score off by a tiny amount
        s = original(current_id)
        s[s > 0] += 1e-9
        return s
    f._engine._candidate_scores = tampered
    with pytest.raises(RuntimeError):
        f.explain(["右", "右"])


def test_save_load_roundtrip_is_exact(tmp_path):
    import random
    import numpy as np
    data = [["右", "右", "下"] * 5, ["正常", "温度上昇", "振動増加", "停止"] * 3, [1, 2, 3, 1, 2, 3]]
    a = Frog(pair_context_capacity=4).learn(data)          # small capacity: eviction order matters
    a.save(tmp_path / "f.cse")
    random.seed(7)
    expected = random.random()
    random.seed(7)
    b = Frog.load(tmp_path / "f.cse")
    assert random.random() == expected                     # loading does not reset the user's RNG
    for prefix in (["右", "右"], ["正常", "温度上昇"], [1, 2], ["停止"]):
        assert a.probabilities(prefix) == b.probabilities(prefix)
        assert a.explain(prefix, k=50) == b.explain(prefix, k=50)
    more = [["右", "下", "右"] * 4, [3, 2, 1] * 3]          # continuing to learn gives identical results
    a.learn(more)
    b.learn(more)
    for prefix in (["右", "下"], [3, 2], ["右", "右"]):
        assert a.probabilities(prefix) == b.probabilities(prefix)
    assert np.array_equal(a._engine.weights, b._engine.weights)
    assert list(a._engine.pair_context_weights) == list(b._engine.pair_context_weights)


def test_save_rejects_unsupported_tokens_and_load_rejects_other_files(tmp_path):
    f = Frog().learn([[("x", 1), ("y", 2)]])
    with pytest.raises(ValueError):
        f.save(tmp_path / "bad.cse")
    import zipfile
    with zipfile.ZipFile(tmp_path / "other.cse", "w") as z:
        z.writestr("meta.json", '{"format": "something-else"}')
    with pytest.raises(ValueError):
        Frog.load(tmp_path / "other.cse")


def test_generate_greedy_follows_predict_and_stops_at_end():
    f = Frog().learn([["右", "右", "下"]] * 3)
    out = f.generate(["右"], n=10, greedy=True)
    seq = ["右"]
    for tok in out:                                   # every greedy step equals predict() on the sequence so far
        assert f.predict(seq) == tok
        seq.append(tok)
    assert f.predict(seq) is END                      # stopped because the next one is <END>
    assert END not in out and len(out) <= 10


def test_generate_types_limits_and_errors():
    f = Frog().learn("あいうえお")
    s = f.generate("あ", n=3, greedy=True)
    assert isinstance(s, str) and len(s) <= 3 and s == "いうえ"
    assert f.generate("あ", n=0) == ""
    assert f.generate(["あ"], n=2, greedy=True) == ["い", "う"]
    with pytest.raises(ValueError):
        f.generate("あ", n=-1)
    with pytest.raises(ValueError):
        f.generate("か")                              # unknown symbol


def test_generate_seed_is_reproducible_and_keeps_user_random_state():
    f = Frog(temperature=2.0).learn([["A", "B"]] * 5 + [["A", "C"]] * 4 + [["A", "D"]] * 3)
    random.seed(123)
    before = random.random()
    random.seed(123)
    a = f.generate(["A"], n=5, seed=7)
    b = f.generate(["A"], n=5, seed=7)
    assert a == b
    assert random.random() == before                 # the user's global random state was not touched


def test_generate_sampling_follows_probabilities():
    f = Frog().learn([["右", "右", "下"]] * 3)
    p = f.probabilities(["右", "右"])
    draws = [f.generate(["右", "右"], n=1, seed=i) for i in range(3000)]
    share = sum(d == ["下"] for d in draws) / len(draws)
    assert abs(share - p["下"]) < 0.03
