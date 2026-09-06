.PHONY: test lint check build smoke clean

test:
	python -m pytest -q

lint:
	ruff check .

check: test lint
	python -m compileall -q genreplay tests

build:
	python -m pip wheel . --no-deps --no-build-isolation -w dist

smoke:
	python -m genreplay --version
	python -m genreplay networks

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
