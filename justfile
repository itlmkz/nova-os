# NovaOS v0.1 Justfile
# https://github.com/casey/just

# Install dependencies
install:
    pip install -r requirements.txt

# Run tests
test:
    pytest tests/ -v

# Run linter
lint:
    ruff check novaos/

# Format code
format:
    ruff format novaos/

# Type check
typecheck:
    mypy novaos/ --ignore-missing-imports

# Run orchestrator
run:
    python -m novaos.core.orchestrator

# Run all checks
check: lint typecheck test

# Clean worktrees and cache
clean:
    rm -rf /tmp/novaos-worktrees/*
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name '*.pyc' -delete

# Setup dev environment
dev-setup:
    cp env.example .env
    echo "Edit .env with your credentials"
