.PHONY: run discover install deps

run:
	.venv/bin/python3 main.py

discover:
	.venv/bin/python3 main.py --discover

deps:
	brew install portaudio ffmpeg

install:
	python3 -m venv .venv && .venv/bin/pip install -e .
