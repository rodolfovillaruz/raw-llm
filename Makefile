SRC = .

.PHONY: all format typecheck test check

all: check

check: typecheck test

format:
	ruff check
	ruff format

typecheck:
	ty check $(SRC)

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