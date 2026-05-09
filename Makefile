.PHONY: run discover install

run:
	.venv/bin/python3 main.py

discover:
	.venv/bin/python3 main.py --discover

install:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
