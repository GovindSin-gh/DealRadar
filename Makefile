# Shortcuts. Run `make help`.
.PHONY: help setup test verify backend frontend retrain-demo

help:           ## list commands
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/ -/'
setup:          ## install backend, mlops and frontend dependencies
	pip install -r backend/requirements.txt -r mlops/requirements.txt pyyaml
	cd frontend && npm install
test:           ## run backend and ML tests
	cd backend && pytest -q
	cd mlops && pytest -q
verify:         ## check that every file agrees with the others
	python scripts/verify_project.py
backend:        ## start the API on http://localhost:8000
	cd backend && uvicorn app.main:app --reload
frontend:       ## start the website on http://localhost:5173
	cd frontend && npm run dev
retrain-demo:   ## train on the synthetic demo data (pipeline check only)
	cd mlops && python make_demo_data.py && python train.py --note demo-synthetic
