import math

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
