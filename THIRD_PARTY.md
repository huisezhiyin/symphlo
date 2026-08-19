# Third-Party Inventory

Symphlo's Local Runtime and Python tests use only the Python standard library.
The Local App uses reviewed public JavaScript dependencies resolved by
`pnpm-lock.yaml`. No Agent executable, model SDK, provider credential or
generated third-party source is bundled in this repository.

## Local App Dependencies

| Component | Reviewed version | License | Use |
| --- | --- | --- | --- |
| React / React DOM | `19.2.7` | MIT | product UI rendering |
| XYFlow / React Flow | `12.11.2` | MIT | App-owned observable Flow Canvas |
| Vite | `8.1.4` | MIT | Web development and production build |
| TypeScript | `5.9.3` | Apache-2.0 | strict developer type checking |

## Desktop Development Dependencies

| Component | Reviewed version | License | Use |
| --- | --- | --- | --- |
| Electron | `43.1.0` | MIT | sandboxed native Desktop window and process lifecycle |
| Electron Packager | `20.0.2` | MIT | unsigned macOS Local Alpha packaging |
| TypeScript | `5.9.3` | Apache-2.0 | strict Desktop source checking |

The full direct and transitive development graph is pinned in `pnpm-lock.yaml`.
No Agent CLI, private adapter or vendored third-party UI source is included.

## Transitive License Review

The locked JavaScript graph was enumerated with
`pnpm licenses list --json --long` on 2026-07-24:

| SPDX identifier | Package entries | Review note |
| --- | ---: | --- |
| MIT | 64 | permissive |
| ISC | 14 | permissive |
| BlueOak-1.0.0 | 5 | permissive |
| Apache-2.0 | 4 | permissive with notice/patent terms |
| BSD-2-Clause | 4 | permissive |
| BSD-3-Clause | 2 | permissive |
| MPL-2.0 | 2 | file-scoped copyleft; build-time `lightningcss` package and macOS binary |

No package reported an unknown, unlicensed, GPL, AGPL, LGPL, SSPL or BUSL
identifier. The MPL-2.0 entries are unmodified build tooling resolved into
`node_modules`; their source is not copied into this repository. This inventory
is engineering evidence, not legal advice, and must be refreshed when the
lockfile changes.

The release-candidate audit command is:

```bash
pnpm --registry=https://registry.npmjs.org/ audit --json
```

It reported zero known vulnerabilities on 2026-07-24. Audit results are
time-sensitive and do not prove that the dependency graph is vulnerability
free.

## CI-Only Actions

| Component | Reviewed version | License | Use |
| --- | --- | --- | --- |
| [actions/checkout](https://github.com/actions/checkout) | `v7.0.1` / `3d3c42e5aac5ba805825da76410c181273ba90b1` | MIT | read-only source checkout in GitHub Actions |
| [astral-sh/setup-uv](https://github.com/astral-sh/setup-uv) | `v9.0.0` / `c771a70e6277c0a99b617c7a806ffedaca235ff9` | MIT | install pinned uv and select Python 3.12 in GitHub Actions |
| [actions/setup-node](https://github.com/actions/setup-node) | `v6.4.0` / `48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e` | MIT | select Node.js 24 in GitHub Actions |

Both Actions are referenced by immutable commit SHA. They are CI dependencies,
not distributed runtime components.

## Optional User-Installed Executors

| Executor | Upstream license | Symphlo boundary |
| --- | --- | --- |
| [Codex CLI](https://github.com/openai/codex) | Apache-2.0 | discovered and invoked only when the user selects the optional Codex preset |
| [OpenCode](https://github.com/anomalyco/opencode) | MIT | discovered and invoked only when the user selects the optional OpenCode preset |

Symphlo does not download, package, authenticate or redistribute these
executables. Their installation, provider configuration, sessions and
credentials remain user-owned external state.

Product and project names belong to their respective owners. Listing an
optional interoperability target does not imply endorsement or affiliation.
