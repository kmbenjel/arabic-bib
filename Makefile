.PHONY: dev test lint demo bench media
dev:
	uv venv && uv pip install -e '.[dev]'
test:
	.venv/bin/pytest
lint:
	.venv/bin/ruff check src tests bench docs/media
demo:
	.venv/bin/arabic-bib demo
bench:   # heavy (CAMeL Tools pulls in PyTorch): run on a roomy machine
	bash bench/compare.sh
media:   # needs google-chrome and Pillow for the card
	python docs/media/make_media.py --card
