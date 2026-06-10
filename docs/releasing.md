# 发布指南

AI-Link-Net 与 Foundation Protocol 是两个独立的 PyPI 项目，版本号和发布周期
相互独立。如果 AI-Link-Net 依赖新的协议能力，需要先发布 Foundation Protocol。

## 版本兼容

在 `0.x` 快速开发阶段，AI-Link-Net 使用有上下界的协议依赖：

```toml
foundation-protocol>=0.1,<0.2
```

补丁版本可以直接兼容。Foundation Protocol 升级次版本时，需要明确更新并测试
AI-Link-Net 的兼容范围。

## 当前 TestPyPI 实验配置

当前 Fork 实验使用 TestPyPI。Foundation Protocol 已从 TestPyPI 安装，ALN 的
release workflow 也发布到 TestPyPI。为 ALN Fork 添加 Trusted Publisher：

| TestPyPI 项目 | GitHub 仓库 | Workflow | Environment |
|---|---|---|---|
| `ai-link-net` | `Kevin5600/ai-link-net` | `release.yml` | `testpypi` |

在 GitHub 仓库中创建名为 `testpypi` 的 Environment。Workflow 通过 GitHub
OIDC 获取一次性发布凭据，不需要保存 TestPyPI API Token。

如果 TestPyPI 项目尚不存在，可以先配置 Pending Publisher，让第一次成功发布
自动创建项目。

合并回上游或正式发布到 PyPI 前，需要：

1. 删除 `pyproject.toml` 中的 `[[tool.uv.index]]` 和 `[tool.uv.sources]`。
2. 重新运行 `uv lock`，确认 `uv.lock` 中不再包含 TestPyPI URL。
3. 将 release workflow 的 Environment、项目 URL 和 `repository-url` 切回 PyPI。
4. 删除 wheel 冒烟安装前单独从 TestPyPI 安装 Foundation Protocol 的步骤。

## 发布 Foundation Protocol

1. 修改 `foundation-protocol/pyproject.toml` 中的 `project.version`。
2. 运行 Foundation Protocol 测试。
3. 将版本提交合并到 `main`。
4. 给该提交创建并推送 Tag：

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

Workflow 会验证 Tag、运行测试、构建发布包、发布到配置的包索引，最后创建
GitHub Release。当前 Fork 实验的目标索引是 TestPyPI。

## 发布 AI-Link-Net

1. 确认需要的 Foundation Protocol 版本已经可以从当前目标仓库安装。
2. 必要时更新 `foundation-protocol` 的兼容版本范围。
3. 修改 `pyproject.toml` 中的 `project.version`。
4. 更新 Python 锁文件并安装 Web 依赖：

   ```bash
   uv lock
   cd aln/web
   npm ci
   cd ../..
   ```

5. 执行 Python 和 Web 验证：

   ```bash
   uv run pytest
   cd aln/web
   npm test
   npm run build
   cd ../..
   uv build
   ```

6. 将版本变更合并到 `main`。
7. 给该提交创建并推送 Tag：

   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```

Workflow 会拒绝以下发布：

- Tag 版本和 `pyproject.toml` 不一致；
- Tag 对应提交不属于 `main`；
- Python 或 Web 测试失败；
- Web 静态资源没有进入 wheel；
- wheel 中仍包含 Git URL 依赖；
- 构建产物元数据无效。

## 用户更新

正式安装版本最多每 24 小时检查一次 PyPI。检查失败不会影响普通命令。
TestPyPI 实验不验证自动更新；更新检测和 `aln update` 仍以正式 PyPI 为准。

```bash
# 只检查
aln update --check

# 升级并恢复升级前正在运行的服务
aln update
```

`aln update` 要求使用 uv 安装。它会启动独立的 `.cmd` 或 `.sh` 更新脚本，等待
当前 `aln` 进程退出后再替换工具环境，避免 Windows 文件占用问题。日志位于：

```text
~/.fp/updates/update.log
```
