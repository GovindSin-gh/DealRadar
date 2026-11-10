from gate import decide

def m(f1, **aspects):
    return {"f1_macro": f1, "per_aspect": {"battery": 0.8, "display": 0.8, **aspects}}

def test_first_model_needs_min_f1():
    assert decide(m(0.80), None)[0] is True
    assert decide(m(0.70), None)[0] is False

def test_needs_gain_over_champion():
    assert decide(m(0.85), m(0.82))[0] is True
    assert decide(m(0.825), m(0.82))[0] is False

def test_single_aspect_drop_blocks():
    ok, why = decide(m(0.90, battery=0.7), m(0.82))
    assert ok is False and any("battery" in w for w in why)
