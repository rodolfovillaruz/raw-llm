SRC = .

.PHONY: all format format-check lint typecheck test check

all: check

check: format-check lint typecheck test

format:
	isort --profile black $(SRC)
	black --line-length 79 $(SRC)

format-check:
	isort --profile black --check-only $(SRC)
	black --line-length 79 --check $(SRC)

lint:
	flake8 $(SRC)
	pylint $(SRC)

typecheck:
	mypy $(SRC)

test:
	pytest $(SRC)