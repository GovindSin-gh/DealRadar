from aspects import ASPECTS
import retrain


def test_new_reviews_skips_known_and_duplicates():
    assert retrain.new_reviews(["a", "b", " b ", "c", ""], ["a"]) == ["b", "c"]


def test_label_all_drops_failed_batches():
    ok = {a: "none" for a in ASPECTS}
    def fake(chunk):
        if "bad" in chunk:
            raise RuntimeError("quota")
        return [ok for _ in chunk]
    rows = retrain.label_all(["x", "y", "bad", "z"], fake, batch=2, sleep=0)
    assert [r["review_text"] for r in rows] == ["x", "y"]
