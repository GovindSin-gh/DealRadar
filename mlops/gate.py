"""Champion vs challenger quality gate. Pure function, easy to test."""


def decide(challenger: dict, champion: dict | None, min_f1=0.78, min_gain=0.01, max_aspect_drop=0.03):
    """Each argument looks like {"f1_macro": 0.82, "per_aspect": {"battery": 0.8, ...}}.
    Returns (promote: bool, reasons: list[str])."""
    reasons = []
    ok = True
    if challenger["f1_macro"] < min_f1:
        ok = False
        reasons.append(f"F1 {challenger['f1_macro']:.3f} is below the minimum {min_f1}")
    if champion is not None:
        gain = challenger["f1_macro"] - champion["f1_macro"]
        if gain < min_gain - 1e-9:
            ok = False
            reasons.append(f"gain {gain:+.3f} is below the required {min_gain:+.2f}")
        for a, c in champion["per_aspect"].items():
            drop = c - challenger["per_aspect"].get(a, 0)
            if drop > max_aspect_drop + 1e-9:
                ok = False
                reasons.append(f"{a} dropped {drop:.3f} (max {max_aspect_drop})")
    else:
        reasons.append("no champion yet")
    if ok:
        reasons.append("all checks passed")
    return ok, reasons
