PHONY: lint

lint:
	black . --check

mypy:
	mypy .
