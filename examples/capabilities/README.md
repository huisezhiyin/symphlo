# Local Capability fixtures

These dependency-free fixtures exercise the same bounded contracts used by the
Desktop App:

- `stdio_json_cli.py`: one JSON object on stdin, one JSON object on stdout.
- `stdio_mcp_server.py`: MCP stdio lifecycle, `tools/list`, and `tools/call`.

They are test fixtures, not hidden Runtime shortcuts.

## Local Agent descriptors

The Desktop can also read `agent-cli-descriptors.json` from its external Local
state directory. This file is deliberately outside the Git checkout. It lets a
user describe an installed Agent without adding provider-specific paths or
arguments to public source:

```json
{
  "version": 1,
  "agents": [
    {
      "id": "agent.example",
      "name": "Example Agent CLI",
      "description": "A user-installed argument-mode Agent.",
      "executable_names": ["example-agent"],
      "executable_paths": ["/Applications/Example Agent.app/Contents/MacOS/example-agent"],
      "version_args": ["--version"],
      "probe_args": ["service", "status"],
      "args": ["--quiet", "--prompt"],
      "input_mode": "argument",
      "output_format": "text",
      "timeout_seconds": 300
    }
  ]
}
```

Only fixed command names, absolute paths and bounded argument arrays are
accepted. Discovery never saves the candidate; the user must still connect it
explicitly in the Capability Library.
