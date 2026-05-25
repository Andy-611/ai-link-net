# Test Report: Cross-Host Mail Routing

## Test Environment
- **OS**: macOS 15.7.4
- **Python**: 3.13
- **Test Date**: 2025-03-31
- **Branch**: `zzj/feat/aln-app-enhancement`
- **FP_HOME**: `/tmp/fp_test_a`, `/tmp/fp_test_b` (custom paths for testing)

## Quick Start for Reviewers

### Prerequisites

**FP_HOME Environment Variable (Optional but Recommended)**

The `FP_HOME` environment variable controls where FP stores keys and config:
- **Default**: `~/.fp/` (if not set)
- **Custom**: Any writable directory (useful for testing or macOS permission issues)

```bash
# Option 1: Use default ~/.fp/ (most users)
# No environment variable needed

# Option 2: Use custom directory (recommended for testing)
export FP_HOME=/tmp/fp_test
```

> **Note for macOS users**: If you encounter `Operation not permitted` errors with `~/.fp/`, use `FP_HOME` to specify a custom directory.

### Start Hosts

```bash
# 1. Start Host A (Terminal 1)
export FP_HOME=/tmp/fp_test_a  # Optional: omit to use default ~/.fp/
export HOST_NAME=host_a
export HOST_PORT=8000
uv run uvicorn aln.app.main:app --port 8000 --reload

# 2. Start Host B (Terminal 2)
export FP_HOME=/tmp/fp_test_b  # Optional: omit to use default ~/.fp/
export HOST_NAME=host_b
export HOST_PORT=8001
uv run uvicorn aln.app.main:app --port 8001 --reload

# 3. Register Alice on Host A
curl -s -X POST http://localhost:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "kind": "agent", "is_public": true}'

# 4. Register Bob on Host B
curl -s -X POST http://localhost:8001/api/v1/entities \
  -H "Content-Type: application/json" \
  -d '{"name": "Bob", "kind": "agent", "is_public": true}'

# 5. Set Host A as parent of Host B
curl -s -X POST http://localhost:8001/api/v1/parent \
  -H "Content-Type: application/json" \
  -d '{"parent_url": "http://localhost:8000"}'
# Note: Returns 200 with parent wellknown (Issue #10 fixed)

# 6. Send mail from Alice to Bob
curl -s -X POST http://localhost:8000/api/v1/mail \
  -H "Content-Type: application/json" \
  -d '{
    "sender": {"address": "HOST_A_UID:ALICE_UID"},
    "recipient": [{"address": "HOST_B_UID:BOB_UID"}],
    "message": {"kind": "invoke", "message_id": "test-001", "payload": {"text": "Hello"}, "metadata": {}},
    "signature": ""
  }'
```

## Detailed Test Results

### Step 1: Start Two Hosts ✅

**Command**:
```bash
# Host A
export FP_HOME=/tmp/fp_test_a
export HOST_NAME=host_a
export HOST_PORT=8000
uv run uvicorn aln.app.main:app --port 8000 --reload

# Host B
export FP_HOME=/tmp/fp_test_b
export HOST_NAME=host_b
export HOST_PORT=8001
uv run uvicorn aln.app.main:app --port 8001 --reload
```

**Result**:
- Host A: uid=`6fb2e1c4`, port=8000 ✅
- Host B: uid=`0eb82239`, port=8001 ✅

**Note**: Avoid port 7000 (macOS AirPlay conflict)

### Step 2: Register Entities ✅

**Alice on Host A**:
```bash
curl -s -X POST http://localhost:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice", "kind": "agent", "is_public": true}'
```

**Response**:
```json
{
  "success": true,
  "message": "Entity registered successfully",
  "data": {
    "name": "Alice",
    "address": {"address": "6fb2e1c4:912ee3d6"},
    "kind": "agent",
    "entity_uid": "912ee3d6",
    "host_uid": "6fb2e1c4"
  }
}
```

**Bob on Host B**:
```bash
curl -s -X POST http://localhost:8001/api/v1/entities \
  -H "Content-Type: application/json" \
  -d '{"name": "Bob", "kind": "agent", "is_public": true}'
```

**Response**:
```json
{
  "success": true,
  "message": "Entity registered successfully",
  "data": {
    "name": "Bob",
    "address": {"address": "0eb82239:734316a0"},
    "kind": "agent",
    "entity_uid": "734316a0",
    "host_uid": "0eb82239"
  }
}
```

**Status**: ✅ Both entities registered successfully

### Step 3: Set Parent-Child Relationship ✅

**Command**:
```bash
curl -s -X POST http://localhost:8001/api/v1/parent \
  -H "Content-Type: application/json" \
  -d '{"parent_url": "http://localhost:8000"}'
```

**Response**:
```json
{
  "success": true,
  "message": "Parent set successfully",
  "data": {"name": "host_a", "uid": "...", "url": "http://0.0.0.0:8000", ...}
}
```

**Server Logs (Host A)**:
```
INFO: Adding new child 0eb82239
INFO: WebSocket handshake from child: 0eb82239
INFO: Child host 0eb82239 connected
```

**Server Logs (Host B)**:
```
INFO: Connected to parent at ws://127.0.0.1:8000/ws
```

**Status**: ✅ Returns 200 with parent wellknown (Issue #10 fixed)
- WebSocket connection: ✅ Established
- Child registration: ✅ Success
- HTTP response: ✅ 200 OK

### Step 4: Send Mail ✅ (Forwarding)

**Command**:
```bash
curl -s -X POST http://localhost:8000/api/v1/mail \
  -H "Content-Type: application/json" \
  -d '{
    "sender": {"address": "6fb2e1c4:912ee3d6"},
    "recipient": [{"address": "0eb82239:734316a0"}],
    "message": {"kind": "invoke", "message_id": "test-001", "payload": {"text": "Hello Bob!"}, "metadata": {}},
    "signature": ""
  }'
```

**Response**:
```json
{
  "success": true,
  "message": "Mail routed successfully",
  "data": {
    "message_id": "test-001",
    "status": "delivered"
  }
}
```

**Server Logs (Host A)**:
```
DEBUG: Forwarded mail to child 0eb82239
```

**Server Logs (Host B)**:
```
WARNING: Received mail from non-friend 912ee3d6, rejecting
```

**Status**: ⚠️ Forwarding success, delivery blocked
- HTTP mail submission: ✅ Success
- Mail routing decision: ✅ Correct (identified as child host)
- WebSocket forwarding: ✅ Success
- Local delivery: ❌ Blocked by check_mail()

## Summary

| Step | Component | Status | Notes |
|------|-----------|--------|-------|
| 1 | Host startup | ✅ | Works with FP_HOME env |
| 2 | Entity registration | ✅ | name/kind/is_public fields |
| 3 | Parent-child setup | ✅ | WS established, HTTP 200 (Issue #10 fixed) |
| 4 | Mail forwarding | ✅ | Cross-host WS routing works |
| 4 | Mail delivery | ❌ | check_mail() rejects unsigned mail |

## Core Functionality Status

**Working**:
- ✅ Multi-host WebSocket communication
- ✅ Mail routing between hosts
- ✅ Entity registration
- ✅ Parent-child relationship establishment

**Not Working**:
- ❌ Final mail delivery (signature/friend check)
- ❌ CLI commands (mostly stubs)

## Known Issues

1. **Issue #4**: `check_mail` rejects mail without signature/friend relationship
2. **macOS Port 7000**: AirPlay conflict, use 8000+ instead
3. **macOS Gatekeeper**: May restrict `~/.fp/` directory access; use `FP_HOME` environment variable to specify custom path
