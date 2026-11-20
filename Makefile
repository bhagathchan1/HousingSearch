.PHONY: install dev run test seed demo-data docker clean

install:            ## create venv and install runtime deps
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

dev:                ## install dev deps (tests)
	python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt

run:                ## start the web app on :8000
	.venv/bin/python -m housingsearch serve --reload

test:               ## run the test suite
	.venv/bin/python -m pytest -q

demo-data:          ## regenerate the synthetic demo dataset
	.venv/bin/python scripts/generate_demo_data.py

seed:               ## reload demo data into the database
	.venv/bin/python -m housingsearch seed --reset

docker:             ## build and run with Docker
	docker compose up --build

clean:
	rm -rf .venv data/*.db .pytest_cache
