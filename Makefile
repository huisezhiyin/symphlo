UV ?= uv
PNPM ?= pnpm
SYSTEM_PYTHON_312 := $(shell command -v python3.12 2>/dev/null)
PYTHON_VERSION ?= $(if $(SYSTEM_PYTHON_312),$(SYSTEM_PYTHON_312),3.12)
PYTHON_RUN := $(UV) run --isolated --python $(PYTHON_VERSION) python
GRANULARITY ?= balanced
TOPIC ?= Why durable work needs an observable outer Agent loop
AGENT_COMMAND ?=
AGENT ?=
AGENT_MODEL ?=
AGENT_TIMEOUT ?= 120
RUNS ?= 2
LIVE_RUNS ?= 1
CODEX_MODEL ?= gpt-5.4
PUBLIC_DIR ?=

export PYTHONDONTWRITEBYTECODE := 1
export PYTHONPATH := src

.DEFAULT_GOAL := help

.PHONY: help doctor app desktop desktop-build desktop-check desktop-package desktop-smoke web-install web-build web-lint web-typecheck web-test web-check demo demo-open demo-codex demo-opencode public-tree source-check test check

help:
	@printf '%s\n' \
		'Symphlo Local Alpha' \
		'' \
		'  make doctor         Check offline readiness and optional Agent CLIs' \
		'  make app            Launch the complete Local App at 127.0.0.1:8765' \
		'  make desktop        Launch the independent Symphlo Desktop App' \
		'  make desktop-check  Typecheck, test and build the Desktop shell' \
		'  make desktop-package Build an unsigned macOS Symphlo.app' \
		'  make web-check      Lint, typecheck, test and build the React App' \
		'  make demo           Run the zero-credential balanced demo twice' \
		'  make demo-open      Run the offline demo and open its Evidence App' \
		'  make demo-codex     Run one live Codex-backed Flow' \
		'  make demo-opencode  Run one live OpenCode-backed Flow' \
		'  make public-tree PUBLIC_DIR=/empty/path  Export only public files' \
		'  make check          Run source-boundary and test checks' \
		'' \
		'Options: GRANULARITY=compact|balanced|fine, TOPIC="...", STATE_DIR=/empty/path'

doctor:
	$(PYTHON_RUN) -m symphlo doctor --workspace "$(CURDIR)"

app: web-build
	$(PYTHON_RUN) -m symphlo app --workspace "$(CURDIR)" $(if $(STATE_ROOT),--state-root "$(STATE_ROOT)",) $(if $(PORT),--port "$(PORT)",) $(if $(APP_NO_OPEN),--no-open,)

desktop: web-build web-install
	SYMPHLO_PROJECT_ROOT="$(CURDIR)" SYMPHLO_UV="$(shell command -v $(UV))" $(PNPM) desktop:dev

desktop-build: web-build web-install
	$(PNPM) desktop:build

desktop-check: web-build web-install
	$(PNPM) desktop:lint
	$(PNPM) desktop:typecheck
	$(PNPM) desktop:test

desktop-package: desktop-check
	$(PNPM) desktop:package

desktop-smoke: desktop-check
	SYMPHLO_PROJECT_ROOT="$(CURDIR)" SYMPHLO_UV="$(shell command -v $(UV))" $(PNPM) desktop:smoke

web-install:
	$(PNPM) install --frozen-lockfile

web-build: web-install
	$(PNPM) web:build

web-lint: web-install
	$(PNPM) web:lint

web-typecheck: web-install
	$(PNPM) web:typecheck

web-test: web-install
	$(PNPM) web:test

web-check: web-lint web-typecheck web-test web-build

demo:
	$(PYTHON_RUN) -m symphlo demo --workspace "$(CURDIR)" --granularity "$(GRANULARITY)" --topic "$(TOPIC)" --runs "$(RUNS)" $(if $(AGENT_COMMAND),--agent-command "$(AGENT_COMMAND)",) $(if $(AGENT),--agent "$(AGENT)",) $(if $(AGENT_MODEL),--agent-model "$(AGENT_MODEL)",) --agent-timeout "$(AGENT_TIMEOUT)" $(if $(STATE_DIR),--state-dir "$(STATE_DIR)",)

demo-open:
	$(PYTHON_RUN) -m symphlo demo --workspace "$(CURDIR)" --granularity "$(GRANULARITY)" --topic "$(TOPIC)" --runs "$(RUNS)" $(if $(AGENT_COMMAND),--agent-command "$(AGENT_COMMAND)",) $(if $(AGENT),--agent "$(AGENT)",) $(if $(AGENT_MODEL),--agent-model "$(AGENT_MODEL)",) --agent-timeout "$(AGENT_TIMEOUT)" --open $(if $(STATE_DIR),--state-dir "$(STATE_DIR)",)

demo-codex:
	$(MAKE) demo AGENT=codex AGENT_MODEL="$(CODEX_MODEL)" AGENT_TIMEOUT=300 RUNS="$(LIVE_RUNS)"

demo-opencode:
	$(MAKE) demo AGENT=opencode AGENT_TIMEOUT=300 RUNS="$(LIVE_RUNS)"

public-tree:
	@test -n "$(PUBLIC_DIR)" || (printf '%s\n' 'error: PUBLIC_DIR is required' >&2; exit 2)
	$(PYTHON_RUN) scripts/check_public_source.py --export "$(PUBLIC_DIR)"

source-check:
	$(PYTHON_RUN) scripts/check_public_source.py

test:
	$(PYTHON_RUN) -m unittest discover -s tests -v

check: source-check test web-check desktop-check
