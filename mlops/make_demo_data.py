"""Creates SYNTHETIC labeled reviews so the whole pipeline can run before you have real data.
Metrics on this data are NOT meaningful (the sentences are templated). Replace it with
real reviews labeled by label_reviews.py plus a hand-checked gold set."""
import argparse
import csv
import pathlib
import random

from aspects import ASPECTS

TRAIN = {
    "battery": (["Battery easily lasts a full day.", "Great battery life, I charge it every two days.", "The battery backup is excellent.", "Battery holds up well even with heavy use."],
                ["Battery drains fast on 5G.", "Battery life is disappointing, dead by evening.", "The battery backup is poor.", "Battery percentage drops quickly while streaming."]),
    "display": (["The display is stunning and very bright.", "Screen colours are vivid and sharp.", "Love the AMOLED display, great outdoors.", "The screen is smooth and a joy to watch videos on."],
                ["The display looks dull and washed out.", "Screen is too dim in sunlight.", "Display has a yellow tint and uneven brightness.", "The screen scratches easily and reflects a lot."]),
    "performance": (["Performance is smooth, no lag in daily use.", "Apps open instantly and multitasking is fast.", "Very fast processor, handles everything easily.", "Runs smoothly even with many apps open."],
                    ["It lags a lot when switching apps.", "Performance is sluggish and slow after the update.", "Apps freeze and the phone stutters often.", "Slow processor, heavy apps take forever to load."]),
    "heating": (["Stays cool even during long sessions.", "No heating issues at all, even while charging.", "Thermals are well managed, never gets warm.", "Does not heat up while gaming."],
                ["Gets hot while gaming, frame rate drops.", "The phone heats up a lot when charging.", "Overheating is a real problem after 20 minutes.", "It becomes very warm and uncomfortable to hold."]),
    "camera": (["Daylight camera photos are excellent.", "The camera takes sharp, detailed pictures.", "Great camera, night mode works well.", "Photos look amazing and the video is stable."],
               ["Camera struggles in low light, photos look soft.", "The camera quality is average and grainy.", "Photos look blurry and colours are off.", "Disappointing camera, autofocus keeps missing."]),
    "value_for_money": (["Totally worth the money, great value.", "Excellent value at this price.", "Best phone you can get for this budget.", "Very reasonably priced for what it offers."],
                        ["Overpriced for what it offers.", "Not worth the money at this price.", "Too expensive compared to similar phones.", "Poor value, I regret paying this much."]),
}
NOUN = {"battery": "battery", "display": "screen", "performance": "performance", "heating": "thermals", "camera": "camera", "value_for_money": "value"}
for _a, (_p, _n) in TRAIN.items():  # shared sentiment words, so the model learns "superb"/"awful" for every aspect
    _p += [f"Superb {NOUN[_a]}.", f"Beautiful {NOUN[_a]}, really happy.", f"Impressive {NOUN[_a]}, works great."]
    _n += [f"Awful {NOUN[_a]}.", f"Bad {NOUN[_a]}, very disappointing.", f"Terrible {NOUN[_a]}, not good."]
GOLD = {
    "battery": (["The battery lasts two days, excellent backup.", "Great battery, holds a full day easily."], ["Battery drains quickly, poor backup.", "Disappointing battery, dead by evening."]),
    "display": (["Gorgeous screen, colours really pop.", "The display is crisp, bright and vivid."], ["Screen quality is poor and looks dull.", "The display is too dim and washed out."]),
    "performance": (["Performance is fast and smooth, apps open instantly.", "No lag at all, very fast and smooth."], ["Performance is slow, the phone lags and stutters.", "Apps freeze and it feels sluggish and slow."]),
    "heating": (["It stays cool, no heating at all.", "Never gets warm, thermals are great."], ["Gets very hot while gaming.", "It heats up badly when charging, overheating."]),
    "camera": (["The camera takes sharp, excellent photos.", "Great camera, photos look amazing."], ["The camera is bad, photos look blurry and grainy.", "Disappointing camera, low light photos are soft."]),
    "value_for_money": (["Fantastic value, definitely worth the money.", "Excellent value for this price."], ["Overpriced, not worth the money.", "Too expensive, poor value."]),
}
FILL_TRAIN = ["Delivered on time.", "Packaging was fine.", "Bought it last month.", "Using it for two weeks now.", "Came with the cable only.", ""]
FILL_GOLD = ["Arrived a day early.", "Box was sealed properly.", "Got it during the sale.", "Been using it daily.", ""]


def build(pools, fills, n, seed):
    rng, rows = random.Random(seed), []
    for _ in range(n):
        k = rng.choices([0, 1, 2, 3], weights=[1, 5, 3, 1])[0]
        chosen = rng.sample(ASPECTS, k)
        labels, parts = {a: "none" for a in ASPECTS}, []
        for a in chosen:
            pos = rng.random() < 0.5
            labels[a] = "positive" if pos else "negative"
            parts.append(rng.choice(pools[a][0 if pos else 1]))
        parts.append(rng.choice(fills))
        rng.shuffle(parts)
        rows.append({"review_text": " ".join(p for p in parts if p) or rng.choice(fills[:-1]), **labels})
    return rows


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["review_text", *ASPECTS])
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data")
    out = pathlib.Path(ap.parse_args().out)
    write(out / "train_v1.csv", build(TRAIN, FILL_TRAIN, 600, 1))
    write(out / "gold.csv", build(GOLD, FILL_GOLD, 150, 2))
    print("wrote", out / "train_v1.csv", "and", out / "gold.csv", "(synthetic demo data)")
