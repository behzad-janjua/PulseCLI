.PHONY: run discover custom collect train install deps

run:
	.venv/bin/python3 main.py

discover:
	.venv/bin/python3 main.py --discover

custom:
	.venv/bin/python3 main.py --custom

collect:
	.venv/bin/python3 scripts/collect.py

add:
	.venv/bin/python3 scripts/collect.py --add $(GESTURE)

train:
	.venv/bin/python3 scripts/train.py

deps:
	brew install portaudio ffmpeg

install:
	python3 -m venv .venv && .venv/bin/pip install -e .
