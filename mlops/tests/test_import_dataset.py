import pandas as pd
import pytest

from import_dataset import clean


def test_clean_filters_dedupes_and_limits():
    df = pd.DataFrame({"Review": [
        "The battery lasts two days and the screen is lovely.", "The battery lasts two days and the screen is lovely.",
        "ok", "Delivery was quick and the packaging was neat and tidy.", "Camera photos are sharp in daylight, great phone.", None]})
    out = clean(df, "Review", limit=10)
    assert out["review_text"].tolist() == ["The battery lasts two days and the screen is lovely.", "Camera photos are sharp in daylight, great phone."]
    assert len(clean(df, "Review", limit=10, keyword_filter=False)) == 3
    assert len(clean(df, "Review", limit=1)) == 1


def test_wrong_column_gives_a_clear_error():
    with pytest.raises(SystemExit):
        clean(pd.DataFrame({"a": ["x"]}), "Review")


def test_exclude_keeps_gold_disjoint_from_training():
    df = pd.DataFrame({"Review": ["The battery lasts two days and the screen is lovely.", "Camera photos are sharp in daylight, great phone."]})
    out = clean(df, "Review", exclude=["Camera photos are sharp in daylight, great phone."])
    assert out["review_text"].tolist() == ["The battery lasts two days and the screen is lovely."]
