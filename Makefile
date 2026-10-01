# Short aliases for the common DevBots workflows. Everything runs through uv, which manages the
# workspace virtualenv (shared + bots/*) and the pinned dev tools (ruff, pytest).
#
# Override the dashboard port with PORT, e.g.  make serve PORT=3000

UV ?= uv
UVX ?= uvx
PORT ?= 8080
CLEAN_PATHS = .pytest_cache .ruff_cache .coverage htmlcov

.DEFAULT_GOAL := help
.PHONY: help install lint fix test check-updates check-security audit doctor clean serve generate chat

help:
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Setup"
	@echo "  install          Install all workspace dependencies (uv sync)"
	@echo "  doctor           Check required tools and local configuration"
	@echo ""
	@echo "Quality"
	@echo "  lint             Run ruff lint checks"
	@echo "  fix              Auto-fix ruff lint issues"
	@echo "  test             Run the pytest suite across the workspace"
	@echo ""
	@echo "Dependencies"
	@echo "  check-updates    List outdated direct dependencies"
	@echo "  check-security   Scan locked dependencies for known vulnerabilities (pip-audit)"
	@echo "  audit            Alias of check-security"
	@echo ""
	@echo "Run"
	@echo "  serve            Generate dashboard data and serve it on http://localhost:$(PORT)/"
	@echo "  generate         Regenerate dashboard JSON data only"
	@echo "  chat             Start the interactive orchestrator chat"
	@echo ""
	@echo "Cleanup"
	@echo "  clean            Remove caches and coverage output (never touches data/)"
	@echo ""

install:
	$(UV) sync

lint:
	$(UV) run ruff check .

fix:
	$(UV) run ruff check --fix .

test:
	$(UV) run pytest

check-updates:
	-$(UV) tree --outdated --depth 1

check-security:
	$(UV) export --format requirements-txt --no-hashes --no-emit-workspace --quiet \
		| $(UVX) pip-audit --requirement /dev/stdin --no-deps --disable-pip

audit: check-security

doctor:
	@echo "Checking DevBots environment..."
	@missing=0; \
	for tool in $(UV) git; do \
		if command -v $$tool >/dev/null 2>&1; then \
			echo "  OK   $$tool -> $$(command -v $$tool)"; \
		else \
			echo "  MISS $$tool (not on PATH)"; missing=1; \
		fi; \
	done; \
	if $(UV) run python -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then \
		echo "  OK   python $$($(UV) run python -c 'import platform; print(platform.python_version())')"; \
	else \
		echo "  MISS python >= 3.10 (via uv)"; missing=1; \
	fi; \
	if [ -f .env ]; then \
		echo "  OK   .env present"; \
		provider=$$(sed -n 's/^DEVBOTS_PROVIDER=\([A-Za-z]*\).*/\1/p' .env | tail -1 | tr '[:upper:]' '[:lower:]'); \
		provider=$${provider:-anthropic}; \
		case $$provider in \
			openai) key=OPENAI_API_KEY ;; \
			gemini) key=GEMINI_API_KEY ;; \
			*) key=ANTHROPIC_API_KEY ;; \
		esac; \
		if grep -Eq "^$$key=[^[:space:]#]+" .env; then \
			echo "  OK   $$key set (provider: $$provider)"; \
		else \
			echo "  MISS $$key empty or missing in .env (provider: $$provider)"; missing=1; \
		fi; \
	else \
		echo "  MISS .env (copy .env.example to .env)"; missing=1; \
	fi; \
	exit $$missing

clean:
	find . -path ./.venv -prune -o -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf $(CLEAN_PATHS)

serve:
	$(UV) run dashboard --port $(PORT)

generate:
	$(UV) run dashboard generate

chat:
	$(UV) run orchestrator chat
