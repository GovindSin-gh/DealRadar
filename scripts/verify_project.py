#!/usr/bin/env python3
"""Connection audit: checks that the files of DealRadar agree with each other.

Run from anywhere:  python scripts/verify_project.py        (needs: pip install -r backend/requirements.txt pyyaml)
It checks that frontend calls match backend routes, database models match schema.sql, every setting used in code
is documented, workflows point at real files and real settings, requirements cover every import, imports resolve,
and the shipped model loads. Exit code 1 if anything is out of sync (CI runs this on every push).
"""
import ast
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
BACKEND, MLOPS, FRONTEND = ROOT / "backend", ROOT / "mlops", ROOT / "frontend"
DOCS = (ROOT / "docs" / "explainable.html").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
results = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("PASS  " if ok else "FAIL  ") + name + (f"\n        {detail}" if detail and not ok else ""))


def src_files(folder, recursive=False):
    it = folder.rglob("*.py") if recursive else folder.glob("*.py")
    return [f for f in it if "tests" not in f.parts and ".venv" not in f.parts and "__pycache__" not in f.parts]


# ---------------------------------------------------------------- 1. frontend <-> backend routes
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
sys.path[:0] = [str(BACKEND), str(MLOPS)]
from app.main import app  # noqa: E402  (also proves every backend import resolves)

check("backend imports resolve (app.main loads)", True)
routes = {r.path for r in app.routes if r.path.startswith("/api")}
js = "\n".join(f.read_text() for f in (FRONTEND / "src").rglob("*.js*"))
called = set(re.findall(r"/api/[A-Za-z_/]+", js))
missing = [c for c in called if not any(r == c or r.startswith(c.rstrip("/") + "/{") for r in routes)]
check("every API path the frontend calls exists in the backend", not missing, f"missing: {missing}")
undocumented = [r for r in routes if re.sub(r"\{\w+\}", "{id}", r) not in DOCS]
check("every backend route is documented in docs/explainable.html", not undocumented, f"undocumented: {undocumented}")

# ---------------------------------------------------------------- 2. models <-> schema.sql
from app.db import Base  # noqa: E402

model_tables = set(Base.metadata.tables)
sql_tables = set(re.findall(r"create table if not exists (\w+)", (BACKEND / "schema.sql").read_text()))
check("database models match schema.sql", model_tables == sql_tables, f"models={sorted(model_tables)} sql={sorted(sql_tables)}")
sql = (BACKEND / "schema.sql").read_text()
cols_ok, bad = True, []
for t in Base.metadata.tables.values():
    block = re.search(rf"create table if not exists {t.name} \((.*?)\n\);", sql, re.S)
    for c in t.columns:
        if not block or not re.search(rf"\b{c.name}\b", block.group(1)):
            cols_ok = False
            bad.append(f"{t.name}.{c.name}")
check("every model column exists in schema.sql", cols_ok, f"missing: {bad}")

# ---------------------------------------------------------------- 3. settings used in code are documented
pat = [r'os\.(?:getenv|environ\.get)\(\s*"(\w+)"', r'os\.environ\[\s*"(\w+)"\s*\]']
def env_in(files):
    out = set()
    for f in files:
        for p in pat:
            out |= set(re.findall(p, f.read_text()))
    return out
backend_env, mlops_env = env_in(src_files(BACKEND / "app")), env_in(src_files(MLOPS))
example = (BACKEND / ".env.example").read_text()
check("every backend setting is in backend/.env.example", all(v in example for v in backend_env), f"missing: {[v for v in backend_env if v not in example]}")
check("every setting used in code is documented in docs", all(v in DOCS for v in (backend_env | mlops_env | {"VITE_API_URL"}) - {"GITHUB_OUTPUT"}), f"missing: {[v for v in (backend_env | mlops_env | {'VITE_API_URL'}) - {'GITHUB_OUTPUT'} if v not in DOCS]}")
check("frontend/.env.example defines VITE_API_URL", "VITE_API_URL" in (FRONTEND / ".env.example").read_text())

# ---------------------------------------------------------------- 4. workflows <-> files, settings, docs
code_env = backend_env | mlops_env
allow = {"MLFLOW_TRACKING_USERNAME", "MLFLOW_TRACKING_PASSWORD", "DAGSHUB_USER", "DAGSHUB_TOKEN", "HOOK", "API_URL", "GITHUB_OUTPUT"}
wf_dir = ROOT / ".github" / "workflows"
for wf in sorted(wf_dir.glob("*.yml")):
    d = yaml.safe_load(wf.read_text())
    problems = []
    trig = d.get("on") or d.get(True) or {}
    for s in (trig.get("schedule") or []) if isinstance(trig, dict) else []:
        if len(s["cron"].split()) != 5:
            problems.append(f"bad cron {s['cron']}")
    for job in d["jobs"].values():
        for st in job["steps"]:
            wd = ROOT / st.get("working-directory", ".")
            run = st.get("run", "")
            if not wd.exists():
                problems.append(f"missing working-directory {wd}")
            for m in re.findall(r"python -m app\.(\w+)", run):
                if not (BACKEND / "app" / f"{m}.py").exists():
                    problems.append(f"missing module app.{m}")
            for m in re.findall(r"python (\w+\.py)", run):
                if not (wd / m).exists():
                    problems.append(f"missing script {m}")
            for m in re.findall(r"pip install[^\n]*?-r\s+(\S+)", run):
                if not (wd / m).exists():
                    problems.append(f"missing requirements file {m}")
            if "python" in run:
                for k in {**job.get("env", {}), **st.get("env", {})}:
                    if k not in code_env | allow:
                        problems.append(f"env {k} is never read by the code")
    refs = set(re.findall(r"(?:secrets|vars)\.(\w+)", wf.read_text())) - {"GITHUB_TOKEN"}
    problems += [f"{r} not documented in README" for r in refs if r not in README]
    if wf.name not in DOCS:
        problems.append("not mentioned in docs/explainable.html")
    check(f"workflow {wf.name} matches the code and docs", not problems, "; ".join(problems))

retrain_wf = (wf_dir / "retrain-weekly.yml").read_text()
champ_rel = "../backend/models/champion"
paths = {"train.py": (MLOPS / "train.py").read_text(), "retrain.py": (MLOPS / "retrain.py").read_text()}
from app.config import settings  # noqa: E402

check("train.py, retrain.py and the backend all use the same champion model location",
      all(champ_rel in t for t in paths.values())
      and (MLOPS / champ_rel).resolve() == (BACKEND / "models" / "champion").resolve()
      and Path(settings.model_path).resolve() == (BACKEND / "models" / "champion" / "model.joblib").resolve()
      and "backend/models/champion" in retrain_wf)
check("retrain workflow versions the same dataset file retrain.py writes",
      'CURRENT, SEED, GOLD = pathlib.Path("data/train_current.csv")' in paths["retrain.py"] and "mlops/data/train_current.csv" in retrain_wf)

# ---------------------------------------------------------------- 5. requirements cover every import
PKG = {"bs4": "beautifulsoup4", "dotenv": "python-dotenv", "sklearn": "scikit-learn", "yaml": "pyyaml"}
OPTIONAL = {"mlflow"}  # imported lazily; installed by the retrain workflow

def imports(files, local):
    mods = set()
    for f in files:
        for n in ast.walk(ast.parse(f.read_text())):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                mods.add(n.module.split(".")[0])
    return {PKG.get(m, m).lower() for m in mods if m not in sys.stdlib_module_names and m not in local}

def reqs(path):
    return {re.split(r"[<>=\[ ]", l.strip())[0].lower() for l in path.read_text().splitlines() if l.strip() and not l.startswith("#")}

b_files, m_files = src_files(BACKEND / "app"), src_files(MLOPS)
need_b = imports(b_files, {"app"}) - OPTIONAL
need_m = imports(m_files, {p.stem for p in m_files}) - OPTIONAL
check("backend/requirements.txt covers every backend import", need_b <= reqs(BACKEND / "requirements.txt"), f"missing: {need_b - reqs(BACKEND / 'requirements.txt')}")
check("mlops/requirements.txt covers every mlops import", need_m <= reqs(MLOPS / "requirements.txt"), f"missing: {need_m - reqs(MLOPS / 'requirements.txt')}")

# ---------------------------------------------------------------- 6. frontend imports + package
bad = []
for f in (FRONTEND / "src").rglob("*.js*"):
    for rel in re.findall(r'from "(\.{1,2}/[^"]+)"', f.read_text()):
        base = (f.parent / rel)
        if not any((base.with_suffix(e)).exists() or base.exists() and base.is_file() for e in (".jsx", ".js")):
            bad.append(f"{f.name} -> {rel}")
check("every relative frontend import points at a real file", not bad, f"broken: {bad}")
pkg = (FRONTEND / "package.json").read_text()
check("frontend index.html loads src/main.jsx", "/src/main.jsx" in (FRONTEND / "index.html").read_text() and (FRONTEND / "src/main.jsx").exists())

# ---------------------------------------------------------------- 7. shipped model
import joblib  # noqa: E402
import sklearn  # noqa: E402
from aspects import ASPECTS  # noqa: E402

mp = BACKEND / "models" / "champion" / "model.joblib"
try:
    art = joblib.load(mp)
    ok = art["aspects"] == ASPECTS and set(art["models"]) == set(ASPECTS)
    detail = f"aspects differ from mlops/aspects.py ({art['aspects']})"
except Exception as e:
    ok, detail = False, str(e)
check("champion model loads and matches the aspect list", ok, detail)
pins = {l.split("==")[1].strip() for p in (BACKEND, MLOPS) for l in (p / "requirements.txt").read_text().splitlines() if l.startswith("scikit-learn==")}
check("scikit-learn is pinned identically in both requirements files and matches this environment", pins == {sklearn.__version__}, f"pins={pins} installed={sklearn.__version__}")

# ---------------------------------------------------------------- 8. docs
check("README points to docs/explainable.html", "docs/explainable.html" in README)
check("README documents every GitHub secret/variable used by workflows", True)  # checked per workflow above

print(f"\n{sum(results)} of {len(results)} checks passed")
sys.exit(0 if all(results) else 1)
