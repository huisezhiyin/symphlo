# Public Source Manifest

## Purpose

This manifest defines the exact source projection for Symphlo's public Git
history. It is a fail-closed allowlist contract.

Use an empty destination:

```bash
make public-tree PUBLIC_DIR=/tmp/symphlo-public
```

The exporter fails closed when the destination is non-empty, validates the
source projection, copies only allowlisted paths and validates the result again.

## Required Public Root Files

| Path | Purpose |
| --- | --- |
| `AGENTS.md` | contributor and Agent operating boundary |
| `Makefile` | clone-to-run entrypoints |
| `LICENSE` | canonical Apache License 2.0 text |
| `NOTICE` | Symphlo copyright notice |
| `package.json` | pinned public Web workspace entrypoints |
| `pnpm-lock.yaml` | reproducible public Web dependency graph |
| `pnpm-workspace.yaml` | public package workspace boundary |
| `pyproject.toml` | public Python 3.12 project metadata |
| `setup.py` | fail-closed wheel hook for reviewed Local App build output |
| `PROJECT_SPEC.md` | durable product and architecture contract |
| `PUBLIC_SOURCE_MANIFEST.md` | source projection contract |
| `README.md` | public project entry |
| `THIRD_PARTY.md` | reviewed dependency and interoperability inventory |
| `CONTRIBUTING.md` | public contribution and validation boundary |
| `SECURITY.md` | vulnerability-reporting and execution-security boundary |

## Required Public Directories

| Path | Purpose |
| --- | --- |
| `.github/workflows/` | pinned, least-privilege offline CI |
| `apps/desktop/` | isolated Electron lifecycle, launcher tests and macOS packaging |
| `apps/web/` | App-owned React/Vite Local Console source |
| `docs/demo/` | canonical demo guide |
| `docs/vision/` | public viewpoint articles |
| `examples/agents/` | public process-protocol fixture |
| `examples/capabilities/` | public CLI and MCP stdio contract fixtures |
| `examples/flows/` | portable examples and notes |
| `scripts/` | public source-boundary and export checks |
| `src/symphlo/` | independently authored Local Alpha source |
| `tests/` | public contract, runtime and usability tests |

## Local-Only Workspace Records

The following implementation records may remain useful in the local workspace,
but the exporter never copies them into public Git history:

- `PROJECT_KNOWLEDGE.md`
- `IMPLEMENTATION_BOOTSTRAP.md`
- `OPEN_SOURCE_REVIEW.md`
- `docs/features/`

## Always Excluded

- credentials, tokens, cookies and provider configuration;
- source-control metadata from any other repository;
- dependency caches, virtual environments, bytecode and test output;
- local databases, Run state, Context, Artifacts, traces and logs;
- handoffs, chat exports, screenshots and private review packs;
- Pilot or participant material;
- internal adapters, endpoints, identities or fixtures;
- copied, derived or generated source of uncertain provenance.
- repository-local package-manager configuration or a non-public package
  registry reference.

## Import Rule

Each future public source unit requires:

1. an approved task boundary;
2. independent implementation, explicitly authorized App-owned source or a reviewed public dependency;
3. focused tests and provenance evidence;
4. source-manifest, secret and private-reference checks;
5. exported-tree validation before it enters Git history.

## Publication Record

The first public projection was approved on 2026-07-24 under Apache-2.0 with
copyright identity `GreyChen`. Future additions must continue to satisfy the
import rule and may not weaken the source boundary.
