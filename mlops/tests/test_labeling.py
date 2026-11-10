import json
from aspects import ASPECTS
from label_reviews import parse_labels

good = {a: "none" for a in ASPECTS} | {"battery": "negative"}

def test_parses_valid_and_drops_invalid():
    raw = "<think>hmm</think>```json\n" + json.dumps([good, {"battery": "meh"}]) + "\n```"
    out = parse_labels(raw, 3)
    assert out[0]["battery"] == "negative" and out[1] is None and out[2] is None

def test_garbage_reply_is_safe():
    assert parse_labels("sorry, I cannot", 2) == [None, None]
