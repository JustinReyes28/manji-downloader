"""Makefile equivalents for Windows users; see README for uv commands."""

.PHONY: sync test lint format typecheck build run

sync:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy src

build:
	uv build

run:
	uv run manji
