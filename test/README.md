# FP 测试套件

本目录包含 FP (Foundation Protocol) 项目的所有单元测试。

## 目录结构

```
test/
├── conftest.py              # pytest 配置和共享 fixtures
├── fp/
│   ├── core/                # 核心模块测试
│   │   ├── test_base.py     # 基础类型测试 (FPAddress, EntityKind 等)
│   │   └── test_wellknown.py # Well-known 协议测试
│   ├── utils/               # 工具函数测试
│   │   └── test_common.py   # 通用工具测试
│   ├── test_message.py      # 消息模块测试
│   ├── test_mail.py         # 邮件模块测试
│   ├── test_entity.py       # Entity 模块测试
│   └── test_host.py         # Host 模块测试
└── README.md
```

## 运行测试

### 运行所有测试

```bash
uv run pytest test/ -v
```

### 运行特定模块的测试

```bash
# 运行核心模块测试
uv run pytest test/fp/core/ -v

# 运行消息模块测试
uv run pytest test/fp/test_message.py -v

# 运行 Host 模块测试
uv run pytest test/fp/test_host.py -v
```

### 带覆盖率报告

```bash
uv run pytest test/ --cov=src/fp --cov-report=html
```

### 运行单个测试

```bash
uv run pytest test/fp/core/test_base.py::TestFPAddress::test_create_host_address -v
```

## 测试覆盖

当前测试覆盖的模块：

- ✅ `fp.core.base` - FPAddress, EntityKind 等基础类型
- ✅ `fp.core.wellknown` - EntityCard, HostWellKnown
- ✅ `fp.message` - Message, MessageKind
- ✅ `fp.mail` - Mail 封装和加密
- ✅ `fp.entity` - Entity 管理
- ✅ `fp.host` - Host 管理
- ✅ `fp.utils.common` - 工具函数

## 依赖

测试依赖已在 `pyproject.toml` 中定义：

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.1.0",
]
```

安装开发依赖：

```bash
uv pip install -e ".[dev]"
```

## 注意事项

- 测试使用临时目录，不会影响真实数据
- 密钥对会在测试期间生成到 `~/.fp/keys/` 目录
- 异步测试使用 `pytest-asyncio` 支持
