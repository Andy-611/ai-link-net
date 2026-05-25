---
name: aln
description: ALN CLI 与 FP 核心开发说明，重点覆盖 aln mail 的正确使用方式
---

# FP (Foundation Protocol) Development Skill

A minimal, implementable protocol for coordinating heterogeneous participants (humans, agents, services) with secure peer-to-peer communication.

## Core Architecture

FP consists of three main layers:

### 1. Protocol Layer (`src/fp/`)

**Host & Entity**
- `Host`: Container managing entities, routing mail between child/parent hosts
- `Entity`: Individual participant with identity, friends list, and message handlers
- `FPAddress`: Addressing format `HostUid:EntityUid` (host address uses `HostUid:0`)

**Communication**
- `Message`: Application-layer content with kind, payload, and metadata
- `Mail`: Secure envelope with encryption (recipient's public key) and signature (sender's private key)
- `Session`: Conversation context grouping multiple participants

**Key Concepts**
- Entity types: `host`, `human`, `agent`, `tool`, `resource`, `service`
- Message kinds: `hello`, `session_create`, `invoke`, `heartbeat`, `friend_request`, etc.
- Auto-friend: Host-level setting for automatic friendship between entities on same host

### 2. Application Layer (`src/app/`)

Runtime implementation with HTTP API server:
- `HostServer`: Persistent host with FastAPI endpoints, config persistence
- `HostClient`: HTTP client for CLI to communicate with running host servers
- `HostConfig`: Local configuration management (stores in `~/.fp/config.json`)

### 3. CLI Layer (`src/cli/`)

Command-line interface for FP operations:
- `aln host`: Host lifecycle (init, start, stop, reset, list)
- `aln entity`: Entity management (register, search, friends, set, delete)
- `aln mail`: Mail operations (send)
- `aln status`: System status overview
- `aln ui`: Interactive UI

## Common Workflows

### Initialize and Start Host

```bash
# Create host profile and start server
aln host init [HOST_NAME] --port 7000

# Start existing host
aln host start --host default

# List configured hosts
aln host list

# Stop host
aln host stop --host default
```

### Entity Management

```bash
# Register new entity
aln entity register -k agent -n Alice --host default

# Search public entities
aln entity search --name Alice

# List entity friends
aln friend list <entity_uid>

# Update entity config
aln entity set <entity_uid> --visible true --enabled true

# Delete entity
aln entity delete <entity_uid>
```

### `aln mail` 用法（以当前代码为准）

`aln mail` 用于让一个实体主动发送文本消息。  
CLI 会把参数解析后调用 `POST /api/v1/messages/send`。

```bash
aln mail -e <sender> --to <recipient> -m '<json>'
```

参数说明：
- `-e, --entity`：发送方，支持 `entity` 或 `host:entity`（都可用 name 或 uid）
- `--to`：接收方，支持 `entity` 或 `host:entity`（都可用 name 或 uid）
- `-m, --message`：JSON 对象，必须包含 `text` 或 `payload.text`

解析规则（关键）：
- 未写 host 时默认按 `default` host 解析（例如 `Alice` 等价于 `default:Alice`）
- 名字匹配到多个实体会报错，需改用完整地址（如 `host_uid:entity_uid`）
- `-m` 必须是 JSON 对象，字符串/数组会被拒绝
- 当前 CLI 只提取文本并发送，`kind` 等其他字段不会原样透传

推荐示例：

```bash
# 同 host（name 解析）
aln mail -e Alice --to Bob -m '{"text":"hello"}'

# 跨 host（显式地址）
aln mail -e default:Alice --to test1:Bob -m '{"text":"hi"}'

# 使用 payload.text（兼容写法）
aln mail -e host1:a1b2c3d4 --to host2:e5f6a7b8 -m '{"payload":{"text":"ping"}}'
```

发送前建议：
- 先用 `aln find <name>` 确认双方实体可被发现
- 确保发送方所属 host 已启动且可访问

常见错误：
- `Invalid JSON message`：`-m` 不是合法 JSON
- `Message must be a JSON object`：`-m` 是字符串/数组而非对象
- `Message must contain "text" field or payload.text`：缺少文本字段
- `Entity not found` / `Multiple entities matched`：实体解析失败或歧义

### Programmatic Usage

**Basic Example**

```python
import asyncio
from fp import Host, Message, MessageKind, EntityKind

async def main():
    # Create hosts
    cloud = Host(name="CloudHost")
    local_a = Host(name="LocalHostA")
    local_b = Host(name="LocalHostB")

    # Set up topology (parent-child)
    local_a.set_parent_host(cloud)
    local_b.set_parent_host(cloud)

    # Register entities
    alice = local_a.register_entity(
        name="Alice",
        kind=EntityKind.AGENT,
        is_public=True
    )
    bob = local_b.register_entity(
        name="Bob",
        kind=EntityKind.AGENT,
        is_public=True
    )

    # Add friends (required for communication)
    alice.add_friend(bob.entity_card)
    bob.add_friend(alice.entity_card)

    # Send message
    await alice.send_message(
        to="Bob",  # Can use name, EntityUid, or FPAddress
        message=Message(
            kind=MessageKind.INVOKE,
            payload={
                "jsonrpc": "2.0",
                "method": "chat.hello",
                "params": {"text": "Hello Bob!"}
            }
        )
    )

asyncio.run(main())
```

**Message Handling**

```python
async def custom_handler(message: Message):
    """Custom message handler for entity"""
    print(f"Received: {message.kind}")
    print(f"Payload: {message.payload}")

    # Access common fields
    text = message.text  # From payload["text"]
    session_id = message.session_id  # From metadata or payload

# Register entity with handler
entity = host.register_entity(
    name="Agent",
    kind=EntityKind.AGENT,
    handler=custom_handler
)
```

**Working with Sessions**

```python
from fp import Session

# Create session
session = Session(
    session_id="session-123",
    participants=[alice.address, bob.address],
    metadata={"topic": "collaboration"}
)

# Track in entity
alice.sessions[session.session_id] = session
```

## Key Design Patterns

### Mail Routing

Mail routes through host hierarchy automatically:
1. Host checks recipient's `host_uid`
2. If recipient is on same host → deliver to entity
3. If recipient is on child host → forward to child
4. Otherwise → forward to parent host

### Security Model

- Each entity has Ed25519 key pair (public key + private key file)
- Outgoing mail: encrypt with recipient's public key, sign with sender's private key
- Incoming mail: verify sender's signature, decrypt with recipient's public key
- Only friends can communicate (friends list required)

### Entity Discovery

```python
# Get all discoverable public entities
public_entities = host.get_discoverable_entities()

# Includes:
# - This host's public entities
# - Parent host's public entities (if connected)
# - All child hosts' public entities
```

### Entity Friend Management

```python
# Add friend (required before messaging)
alice.add_friend(bob.entity_card)

# Remove friend
alice.remove_friend(bob_uid)

# Get friend by name
card = alice._get_friend_by_name("Bob")
```

## Important Notes

### Protocol Layer Boundaries

**#NOTE comments in code define critical constraints:**
- FP folder (`src/fp/`) provides no persistence - only deserialization logic
- Persistence logic belongs in application layer (e.g., `HostServer.save()`)
- Host's core function is routing Mail (see `Host.route_mail()`)
- Do not modify or add #NOTE comments

### Address Types

```python
from fp import FPAddress

# Host address (entity_uid is "0")
host_addr = FPAddress(address="abc123:0")
host_addr.is_host_address  # True

# Entity address
entity_addr = FPAddress(address="abc123:def456")
entity_addr.is_entity_address  # True
entity_addr.host_uid  # "abc123"
entity_addr.entity_uid  # "def456"
```

### Message ACK Pattern

```python
# Create ACK response
request_msg = Message(
    kind=MessageKind.HELLO,
    payload={"greeting": "hi"}
)

ack_msg = request_msg.to_ack(
    success=True,
    payload={"status": "ok"},
    metadata={"note": "received"}
)

# ACK automatically sets:
# - kind: MessageKind.HELLO_ACK
# - metadata.ack_of_message_id: original message ID
# - metadata.success: True/False
```

## Configuration Files

### Local Config (`~/.fp/config.json`)

```json
{
  "default_host": "default",
  "hosts": {
    "default": {
      "name": "default",
      "bind_host": "0.0.0.0",
      "port": 7000,
      "url": "http://0.0.0.0:7000",
      "entities": {},
      "pids": {}
    }
  }
}
```

### Host Runtime State

Managed by `HostServer` in application layer:
- Entities with keys, mailboxes, sessions
- Parent/child host topology
- Process ID for running server

## Testing

```bash
# Run example
uv run python example/case1.py

# Start dev server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

When host server is running, FastAPI exposes:

**Host Operations**
- `GET /.well-known/fp` - Host discovery info
- `POST /api/v1/host/set-parent` - Set parent host
- `PUT /api/v1/host` - Update host config

**Entity Operations**
- `POST /api/v1/entities` - Register entity
- `GET /api/v1/entities/search` - Search public entities
- `GET /api/v1/entities/{uid}/friends` - List entity friends
- `PUT /api/v1/entities/{uid}` - Update entity
- `DELETE /api/v1/entities/{uid}` - Delete entity

**Mail Operations**
- `POST /api/v1/messages/send` - Send message (used by `aln mail`)
- `POST /api/v1/mail` - Send mail (legacy/raw mail route)

## Code Style Guidelines

### Docstrings
- Core methods: Multi-line detailed docstrings
- Non-core methods: Single-line docstring only

### Error Handling
- CLI commands use `@cli_exception_wrapper` decorator
- Avoid verbose try-catch blocks

### Imports
- Use `from __future__ import annotations` for forward references
- Avoid quoted type hints like `-> "MailBase"`

### Type Hints
- Use modern Python type aliases: `type EntityUid = str`
- Generic types with TypeVar for protocol abstraction

## Limitations

Current scope is minimal and local-first:
- No network discovery beyond direct HTTP
- No distributed consensus
- Single-process host server
- Ed25519 crypto only
- Target: Keep `src/fp/` under 2000 lines

## Troubleshooting

**Host won't start**
- Check if port is already in use
- Use `--port` flag to specify different port
- Check logs in host process

**Entity can't send message**
- Verify both entities have added each other as friends
- Check recipient address format (`HostUid:EntityUid`)
- Ensure host topology allows routing (parent-child links)

**Permission errors**
- Check `~/.fp/keys/` directory permissions
- Verify private key files are readable

## Next Steps

After understanding FP basics:
1. Read `src/fp/core/base.py` for protocol abstractions
2. Study `example/case1.py` for working example
3. Explore `src/app/main.py` for API implementation
4. Check `docs/roadmap.md` for planned features
