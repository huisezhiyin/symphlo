# Security Policy

## Release Status

Symphlo is a pre-release Local Alpha. It has no stable or long-term-supported
version yet. Security fixes are made against the current public development
line after publication; no response-time or remediation SLA is promised.

## Report a Vulnerability

Do not open a public issue for a suspected vulnerability, exposed credential or
privacy-sensitive report. Use
[GitHub private vulnerability reporting](https://github.com/huisezhiyin/symphlo/security/advisories/new)
and include:

- the affected version or commit;
- the smallest reproducible case;
- expected and observed behavior;
- realistic impact and prerequisites;
- any suggested mitigation.

Do not include real credentials, private user data or destructive proof.
Maintainers will acknowledge and assess reports as capacity allows.

## Security Boundary

The default Golden Demo is credential-free and uses a fictional deterministic
process fixture. Optional Agent CLIs and manually registered capabilities are
user-installed execution supply:

- Symphlo does not download or authenticate them;
- process executors inherit the launching environment;
- commands run with the current user's operating-system permissions;
- Local HTTP APIs bind to IPv4 loopback and are not a remote security boundary;
- cancellation prevents later acceptance but cannot undo an external effect
  that already happened.

Only bind executables, MCP servers and HTTP endpoints you trust. Keep provider
credentials outside Flow definitions, commands, repository files and bug
reports.

## Supported Scope

Reports about the public source, Local Runtime, Web App, Desktop shell and
published dependency graph are in scope. Provider services, user-installed
Agent executables and private adapters are owned by their respective projects
unless the issue is caused by Symphlo's integration boundary.
