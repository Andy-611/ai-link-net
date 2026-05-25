# Refactor: fp/aln 分层重构 — 冲突解决指南

> Branch: `refactor/fp-aln-split`
>
> 目标: fp 成为零 aln 依赖的协议库，aln 承载应用层实现

---

## 变更概览

| Commit | 内容 |
|--------|------|
| `d740fcd` | EntityStatus 枚举从 aln 移入 fp/core/base.py |
| `08df787` | CheckPoint 增加 order 字段 + Entity.add_checkpoint() |
| `218c93a` | Handler 统一为 CheckPoint pipeline（核心变更） |
| `f1ca810` | fp/adapters/ 和 handler 实现迁移到 aln |
| `5943393` | Host.register_entity() 精简，应用策略移到 HostServer |

---

## 1. 删除的文件

| 文件 | 说明 |
|------|------|
| `fp/adapters/__init__.py` | 整个目录迁移到 aln/app/adapters/ |
| `fp/adapters/cli_adapter.py` | → `aln/app/adapters/cli_adapter.py` |
| `fp/adapters/mcp_client.py` | → `aln/app/adapters/mcp_client.py` |
| `fp/adapters/prompts.py` | → `aln/app/adapters/prompts.py` |
| `fp/adapters/providers.yaml` | → `aln/app/adapters/providers.yaml` |
| `fp/trade/arbiter_handler.py` | 重命名为 `fp/trade/arbiter_checkpoint.py` |

**如果你的分支修改了以上文件**：将改动迁移到新路径对应的文件。

---

## 2. 新增的文件

| 文件 | 来源 | 内容 |
|------|------|------|
| `aln/app/adapters/__init__.py` | 新建 | 重导出 CLIAdapter, MCPClient 等 |
| `aln/app/adapters/cli_adapter.py` | 从 fp 迁入 | 无改动，仅路径变化 |
| `aln/app/adapters/mcp_client.py` | 从 fp 迁入 | 无改动 |
| `aln/app/adapters/prompts.py` | 从 fp 迁入 | 无改动 |
| `aln/app/adapters/providers.yaml` | 从 fp 迁入 | 无改动 |
| `aln/app/handlers/__init__.py` | 从 fp/handler.py 提取 | create_entity_handler, create_cli_adapter |
| `aln/app/handlers/agent_handler.py` | 从 fp/handler.py 提取 | AgentHandler + build_agent_system_prompt |
| `aln/app/handlers/human_handler.py` | 从 fp/handler.py 提取 | HumanHandler |
| `aln/app/handlers/mcp_handler.py` | 从 fp/handler.py 提取 | MCPHandler（提取了 _handle_list_tools / _send_response 内部方法） |

---

## 3. 核心架构变更

### 3.1 Handler → CheckPoint 统一

**旧模式**: Entity 有 `handler: BaseHandler` 字段，消息最终由 handler.handle() 处理。

**新模式**: Entity 只有 `checkpoints: list[CheckPoint]`，消息通过 pipeline 依次执行，
执行逻辑是 order=900 的 checkpoint。Entity 不再有 handler 字段。

```
pipeline 执行顺序（按 order 排序）：
  200  FriendCheckPoint         — 验证发送者是好友
  210  FriendRequestCheckPoint  — 处理好友请求
  800  CarbonCopyCheckpoint     — 抄送给 owner
  900  执行层 checkpoint         — 替代旧 handler
```

**执行层 checkpoint 的三种形式：**

| 类型 | 场景 | order |
|------|------|-------|
| `ArbiterCheckPoint` | Arbiter entity，协议层 | 900 |
| `CallbackCheckPoint` | callable handler（测试/示例用） | 900 |
| `HandlerBridgeCheckPoint` | 包装 BaseHandler 子类（过渡用） | 900 |

**冲突解决要点：**

- 如果你的代码访问 `entity.handler`：改为 `entity.get_checkpoint(XxxCheckPoint)`
- 如果你创建了新的 Handler 子类：用 HandlerBridgeCheckPoint 包装，或直接继承 CheckPoint
- 如果你注册 entity 时传入 callable：自动包装为 CallbackCheckPoint，无需改动

### 3.2 ArbiterHandler → ArbiterCheckPoint

文件: `fp/trade/arbiter_handler.py` → `fp/trade/arbiter_checkpoint.py`

```python
# 旧
class ArbiterHandler(BaseHandler):
    async def handle(self, message: Message) -> None:
        ...  # self.entity 引用

# 新
class ArbiterCheckPoint(CheckPoint):
    async def execute(self, message: Message, entity: Entity, mail: Mail) -> CheckPointResult:
        ...  # entity 作为参数传入
```

**所有方法签名变更**: `self.entity` → 参数 `entity`

访问 Arbiter 状态:
```python
# 旧
arbiter.handler  # → ArbiterHandler
arbiter.handler.contracts
arbiter.handler.ledger

# 新
arbiter.get_checkpoint(ArbiterCheckPoint)  # → ArbiterCheckPoint | None
arbiter.get_checkpoint(ArbiterCheckPoint).contracts
arbiter.get_checkpoint(ArbiterCheckPoint).ledger
```

### 3.3 Entity.get_checkpoint() 新方法

```python
_T = TypeVar("_T")

def get_checkpoint(self, checkpoint_type: type[_T]) -> _T | None:
    for cp in self.checkpoints:
        if isinstance(cp, checkpoint_type):
            return cp
    return None
```

### 3.4 Entity.add_checkpoint() 新方法

插入 checkpoint 并按 order 排序:
```python
def add_checkpoint(self, checkpoint: CheckPoint) -> None:
    self.checkpoints.append(checkpoint)
    self.checkpoints.sort(key=lambda cp: cp.order)
```

---

## 4. fp/handler.py 精简

**保留内容（协议层接口）：**
- `BaseHandler(ABC)` — 抽象基类
- `CallbackHandler(BaseHandler)` — callback 包装
- `MessageCallback` 类型别名

**移除内容（迁移到 aln/app/handlers/）：**
- `AgentHandler` → `aln/app/handlers/agent_handler.py`
- `HumanHandler` → `aln/app/handlers/human_handler.py`
- `MCPHandler` → `aln/app/handlers/mcp_handler.py`
- `QueuedInvoke` → `aln/app/handlers/agent_handler.py`
- `build_agent_system_prompt` → `aln/app/handlers/agent_handler.py`
- `create_entity_handler` → `aln/app/handlers/__init__.py`
- `create_cli_adapter` → `aln/app/handlers/__init__.py`

**冲突解决要点：**

```python
# 旧 import
from fp.handler import AgentHandler, MCPHandler, HumanHandler
from fp.handler import create_entity_handler
from fp import AgentHandler, MCPHandler, HumanHandler, CLIAdapter

# 新 import
from aln.app.handlers import AgentHandler, MCPHandler, HumanHandler
from aln.app.handlers import create_entity_handler, create_cli_adapter
from aln.app.adapters import CLIAdapter
```

---

## 5. fp/__init__.py 导出变更

**移除的导出：**
```
AgentHandler, HumanHandler, MCPHandler, Handler,
CLIAdapter, create_cli_adapter, create_entity_handler
```

**保留的导出：**
```
BaseHandler, CallbackHandler, HandlerConfig,
CallbackCheckPoint, HandlerBridgeCheckPoint,
ArbiterCheckPoint, ... (所有 CheckPoint 类型)
```

---

## 6. Host.register_entity() 签名变更

**新增参数**: `arbiter: FPAddress | None = None`

**移除的内部逻辑（移到 HostServer）：**
- auto_owner: 自动为 agent 设置第一个 human 为 owner
- auto_arbiter: 自动查找已有 arbiter 并分配
- workdir 创建: agent 的默认 workspace 目录

**保留在 Host 的逻辑：**
- 密钥生成、地址创建、Entity 构建
- 执行层 checkpoint 设置（arbiter/callback/bridge）
- 默认 checkpoints 设置
- save()

**冲突解决要点：**

如果你的代码调用 `host.register_entity()`：
- 如果 host 是 HostServer 实例 → 无需改动，HostServer.register_entity 会接管应用策略
- 如果 host 是 Host 实例（测试场景）→ 需要手动传 `owner=` / `arbiter=`，或者不依赖自动分配

---

## 7. HostServer 新增 override 方法

```python
class HostServer(Host):
    def _resolve_entity_handler(self, ...) -> BaseHandler | None:
        # Host 返回 None → HostServer 调用 create_entity_handler

    def register_entity(self, name, kind, *, provider=None,
                        system_prompt=None, handler_config=None, **kwargs):
        # 应用策略: auto_owner, auto_arbiter, workdir, arbiter 传播
        entity = super().register_entity(...)
        ...

    def _apply_load_policies(self) -> None:
        # load() 后执行: auto_friend, auto_owner, auto_arbiter 传播
```

**Host._resolve_entity_handler** 现在 handler=None 时返回 None。
只有 HostServer override 才会创建具体 handler。

**Host._apply_load_policies** 是空方法，由 Host.load() 末尾调用。
HostServer 覆盖此方法执行加载后的应用策略。

---

## 8. Trade API (aln/app/api/v1/trade.py) 变更

```python
# 旧
from fp.trade.arbiter_handler import ArbiterHandler
handler = arbiter.handler  # type: ArbiterHandler

# 新
from fp.trade.arbiter_checkpoint import ArbiterCheckPoint
arbiter_cp = arbiter.get_checkpoint(ArbiterCheckPoint)
```

所有局部变量 `handler` → `arbiter_cp`。

---

## 9. 常见冲突场景速查

### 我在 fp/adapters/ 下加了新文件
→ 移到 `aln/app/adapters/` 下，更新 import 路径。

### 我修改了 fp/handler.py 的 AgentHandler
→ 改动应用到 `aln/app/handlers/agent_handler.py`。

### 我新建了一个 Handler 子类
→ 放到 `aln/app/handlers/` 下。在 HostServer 的 `_resolve_entity_handler` 或
`create_entity_handler` 中注册。如果是 fp 协议层需要的，用 CheckPoint 基类实现。

### 我修改了 entity.handler 的调用
→ 改为 `entity.get_checkpoint(目标CheckPoint类型)`。

### 我修改了 Host.register_entity() 的逻辑
→ 判断是协议层还是应用层逻辑。协议层改 `fp/host.py`，应用策略改
`aln/app/service/host_server.py` 的 `register_entity` override。

### 我引用了 `from fp import AgentHandler`
→ 改为 `from aln.app.handlers import AgentHandler`。

### 我修改了 arbiter_handler.py
→ 文件已重命名为 `arbiter_checkpoint.py`，类名 `ArbiterHandler` → `ArbiterCheckPoint`，
方法 `handle(message)` → `execute(message, entity, mail) -> CheckPointResult`。

### 我在 Host.load() 末尾添加了加载后逻辑
→ 覆盖 `_apply_load_policies()` 方法，或在 HostServer 的 override 中添加。

---

## 10. 依赖方向（终态）

```
aln  ──depends──>  fp
fp   ──0 deps──>   aln
```

fp 内部不存在任何 `from aln` 或 `import aln` 的引用。
如果合并后出现 fp → aln 的反向依赖，说明合并有误，需修正。
