import math

import pytest

from cse import END, Frog


def trained():
    return Frog().learn(["右右下右右下右右下", "右右下右右下"], epochs=5)


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
