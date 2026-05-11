.PHONY: run discover custom collect train install deps test

PULSE = .venv/bin/pulse

run:
	$(PULSE) run

discover:
	$(PULSE) discover

custom:
	$(PULSE) custom

collect:
	$(PULSE) collect

add:
	$(PULSE) collect --add $(GESTURE)

train:
	$(PULSE) train

deps:
	brew install portaudio ffmpeg

test:
	.venv/bin/python3 -m pytest tests/ -v

install:
	python3 -m venv .venv && .venv/bin/pip install -e .
