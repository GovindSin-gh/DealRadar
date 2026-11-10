import make_demo_data as d
import train
from aspects import ASPECTS

def test_pipeline_on_demo_data(tmp_path):
    d.write(tmp_path / "t.csv", d.build(d.TRAIN, d.FILL_TRAIN, 300, 1))
    d.write(tmp_path / "g.csv", d.build(d.GOLD, d.FILL_GOLD, 80, 2))
    texts, labels = train.load(tmp_path / "t.csv")
    art = train.fit(texts, labels, "test")
    gt, gl = train.load(tmp_path / "g.csv")
    res = train.evaluate(art, gt, gl)
    assert set(res["per_aspect"]) == set(ASPECTS) and res["f1_macro"] > 0.78
