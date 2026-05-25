# ALN (AI Link Net)

ALN is the application layer built on top of Foundation Protocol (FP).
It consists of three modules:

```
aln/
├── app/     # Core service — host runtime, handlers, API endpoints
├── cli/     # Command-line interface — human & agent interaction surface
└── web/     # Web UI — browser-based dashboard
```

## Quick Start

```bash
# Initialize system (creates default host + human entity)
aln init

# Start web UI
aln ui

# Show all commands
aln -h
```

---

## Architecture & Design Principles

### App Layer (`aln/app/`)

The app layer is the **single source of truth** for all business logic.
Every feature must be fully implemented and tested here before
being exposed through CLI or Web.

- `service/host_server.py` — Host runtime with WebSocket management
- `service/host_client.py` — HTTP client for host-to-host communication
- `handlers/` — Entity message handlers (human, agent, arbiter)
- `api/` — FastAPI endpoints consumed by CLI and Web
- `adapters/` — Provider adapters (Claude, Codex, etc.)

### CLI Layer (`aln/cli/`)

The CLI is a **thin presentation layer** over `HostClient`.
It resolves addresses, calls the API, and formats output.
No business logic lives here.

#### Design Rules

1. **Address format** — All `-e` (entity) and `--to` (recipient)
   options accept FP address: `host_uid:entity_uid` or `entity_uid`
   (defaults to the default host). Entity names are rejected with
   a helpful error showing matching addresses.

2. **Consistent structure** — Every command group follows the pattern:
   ```
   @click.group / @click.command
   @click.option(...)
   @cli_exception_wrapper(error_message="...")
   @get_cli_printer
   def command(..., cli_printer: CliPrinter):
   ```

3. **Examples in help** — Every command and group must include
   Examples in its docstring so both humans and agents can learn
   usage from `aln <command> -h`.

4. **Formatted output** — Success: `✓ Action completed` with details.
   Error: handled by `cli_exception_wrapper`. Never print raw dicts.

5. **No business logic** — The CLI calls `HostClient` methods and
   formats the response. Validation, routing, and state management
   belong in the app layer.

#### Command Groups

| Group      | Purpose                              |
|------------|--------------------------------------|
| `host`     | Host lifecycle — create, start, stop |
| `entity`   | Entity registration and config       |
| `find`     | Network-wide entity discovery        |
| `friend`   | Social connections between entities   |
| `mail`     | Send messages between entities        |
| `mailbox`  | View and manage received messages     |
| `market`   | Publish and browse market orders      |
| `contract` | Contract lifecycle management         |
| `pay`      | Payment operations and balance        |

### Web Layer (`aln/web/`)

The web UI is a React + TypeScript SPA. It communicates with
the host via REST API and WebSocket push.

---

## Feature Development Workflow

When adding a new feature, follow this order strictly:

### 1. App Layer First

Implement all business logic in `aln/app/`:
- Add API endpoints if needed
- Add or update `HostClient` methods
- Add handler logic if it involves message processing
- Write unit tests for the new functionality

### 2. CLI Support

Evaluate whether the feature needs CLI access.
If yes:
- Add a command following the CLI design rules above
- Include Examples in the docstring
- Use `cli_exception_wrapper` and `CliPrinter`
- Verify with `aln <command> -h` and manual testing

### 3. Web UI

Add corresponding UI operations:
- Add API calls in `web/src/api/`
- Add UI components and pages
- Use Playwright to verify the feature end-to-end
- Test golden path and edge cases in browser

### 4. Tests

- Unit tests for app layer logic
- CLI integration tests if applicable
- Playwright E2E tests for web features

**Do not skip steps.** App logic must be solid before
building CLI or Web on top of it.
