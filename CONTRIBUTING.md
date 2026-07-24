# Contributing to Symphlo

Symphlo is a narrow Local Alpha for making selected Agent-task boundaries
durable, observable and repeatable. Contributions should preserve that product
shape rather than turn the project into a general low-code platform or an
Agent-specific UI shell.

## Before You Start

- Read [`PROJECT_SPEC.md`](PROJECT_SPEC.md) for the product and architecture
  contract.
- Read [`AGENTS.md`](AGENTS.md) for clean-room, source and validation rules.
- For a material change, open an issue or proposal that states the public
  contract, evidence, risks and explicit non-goals before implementation.
- Keep provider-specific behavior behind the Capability or Adapter boundary.

Do not submit private source, generated vendor code, internal endpoints,
company identities, credentials, user data, local Run state or source with
uncertain provenance. By submitting a contribution, you must have the right to
provide it for inclusion under the repository's published terms.

## Development Setup

The reviewed baseline is Python 3.12, Node.js 24 and pnpm 11.6.0:

```bash
make help
make doctor
make check
```

Use `make desktop` for the macOS native acceptance path or `make app` for the
loopback Web development profile. The zero-credential Golden Demo must remain
available without an Agent account or provider key.

## Change Rules

- Write or update the public contract and focused tests before changing
  Runtime behavior.
- Preserve domain isolation: core contracts must not depend on Web, database
  or concrete adapter implementations.
- Treat Flow definitions, Run state, accepted Context, events and Artifacts as
  durable truth; private Agent conversations are execution evidence only.
- Fail closed for unsupported DSL, capabilities, effects and protocol
  versions.
- Do not weaken tests, schemas or source checks to make a change pass.
- Keep pull requests focused on one reviewable behavior.

## Validation

Run at least:

```bash
make check
make demo
```

Changes to Desktop lifecycle or Run rendering should also run:

```bash
make desktop-smoke
```

Changes to the public projection should be tested from an empty export:

```bash
make public-tree PUBLIC_DIR=/tmp/symphlo-public
```

The exporter is fail-closed. Local governance records, dependency caches,
credentials, generated state and private integrations must never enter the
public tree.

## Security Reports

Follow [`SECURITY.md`](SECURITY.md). Do not disclose suspected vulnerabilities
or secrets in a public issue.
