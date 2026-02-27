# NovaOS v0.1 Makefile
# Canonical commands for agents and humans

.PHONY: help install test lint format run check clean

help:
	@echo "NovaOS v0.1 - Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run ruff linter"
	@echo "  make format     - Format code with ruff"
	@echo "  make typecheck  - Run mypy type checker"
	@echo "  make run        - Start the orchestrator"
	@echo "  make check      - Run all checks (lint + typecheck + test)"
	@echo "  make clean      - Clean worktrees and temp files"

install:
	pip install -r requirements.txt

test:
	pytest tests/ -v

lint:
	ruff check novaos/

format:
	ruff format novaos/

typecheck:
	mypy novaos/ --ignore-missing-imports

run:
	python -m novaos.core.orchestrator

check: lint typecheck test

clean:
	rm -rf /tmp/novaos-worktrees/*
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

# Development helpers
dev-setup:
	cp env.example .env
	@echo "Edit .env with your credentials, then run: make install"

schema-deploy:
	@echo "Run schema.sql in your Supabase SQL Editor"
	@echo "https://supabase.com/dashboard/project/_/sql/new"
