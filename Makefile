.PHONY: lint mypy isort test

lint:
	black . --check

mypy:
	mypy .

isort:
	isort . --check-only --diff

test:
	pytest -v -s
