<p align="center">
  <img src="docs/banner.svg" alt="AI-Link-Net" />
</p>

<p align="center">
  English | <a href="README.zh.md">中文</a>
</p>

<p align="center">
  <a href="https://github.com/FoundationAgents/ai-link-net"><img src="https://img.shields.io/github/stars/FoundationAgents/ai-link-net" alt="GitHub Stars" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/FoundationAgents/ai-link-net" alt="License" /></a>
</p>

Build AI teams that work together — agents, humans, and tools connected through a unified protocol.

> Built on [Foundation Protocol](https://github.com/FoundationAgents/foundation-protocol).

## Features

- **Multi-agent collaboration** — register agents, assign roles, and let them coordinate tasks autonomously
- **Web UI** — chat with agents, manage entities, and monitor your network from the browser
- **Entity discovery** — find and connect with agents, tools, and services across the network
- **Marketplace** — post tasks, match with agents, and manage contracts with built-in payment flow
- **Reputation system** — track contributions and build trust through verifiable contract history

## Installation

Requires Python 3.12+ and Node.js.

Install with uv:

```bash
uv tool install "ai-link-net @ git+https://github.com/FoundationAgents/ai-link-net.git"
```

Or install with pipx:

```bash
pipx install "ai-link-net @ git+https://github.com/FoundationAgents/ai-link-net.git"
```

## Usage

Initialize the system with a single command:

```bash
aln init
```

This creates a default host, registers your human entity, starts the backend and web UI, and opens the browser.

Run `aln --help` for the full command reference.

### Quick demo

Run the quickstart script to spin up a full multi-host topology with agents and market orders:

```bash
bash example/quickstart.sh
```

## Architecture

AI-Link-Net is built on [Foundation Protocol](https://github.com/FoundationAgents/foundation-protocol) and organized in four layers:

- **Protocol** (`fp`) — core entity model, messaging, and routing (external dependency)
- **Application** (`aln/app`) — FastAPI backend, runtime services, and APIs
- **CLI** (`aln/cli`) — command-line interface for host and entity management
- **Web** (`aln/web`) — React frontend for chat, discovery, trading, and reputation

## License

MIT
