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

typecheck:
	mypy $(SRC)

test:
	pytest $(SRC)

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/

build: clean
	python -m build

publish: build
	twine upload dist/*

publish-test: build
	twine upload --repository testpypi dist/*