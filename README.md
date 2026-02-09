# Codex Agent SDK for Python（脚手架）

这是一个面向 Codex CLI 的 Python SDK 脚手架。整体设计尽量对齐 Claude Agent SDK，方便你以较低成本构建上层 Agent 能力。

## 核心能力

- 封装 `codex exec --json`，把 JSONL 事件解析为 Python 对象。
- 提供顶层 `query()`（轻量 one-shot）与 `CodexSDKClient`（会话式）两种入口。
- 支持动态工具（`@tool`）与 app-server 回调（审批、用户输入）。
- 支持可观测性 Hook（记录/过滤/中止流）。
- 保留传输抽象，便于扩展后端。

## 安装（可编辑模式）

```bash
pip install -e "./codex-agent-sdk-python"
```

## 快速开始（顶层 `query`）

```python
import anyio
from codex_agent_sdk import query

async def main():
    async for event in query(prompt="总结这个仓库"):
        print(event)

anyio.run(main)
```

## `CodexSDKClient` 用法

### 1. 会话式（对齐 Claude 风格）

```python
import anyio
from codex_agent_sdk import CodexAgentOptions, CodexSDKClient

async def main():
    options = CodexAgentOptions(model="gpt-5-codex", sandbox="workspace-write")

    async with CodexSDKClient(options) as client:
        await client.query("列出顶层文件")
        async for event in client.receive_response():
            print(event)

        await client.query("现在打开 README.md")
        async for event in client.receive_response():
            print(event)

anyio.run(main)
```

### 2. One-shot（`run`）

```python
import anyio
from codex_agent_sdk import CodexSDKClient

async def main():
    client = CodexSDKClient()
    async for event in client.run("解释这个项目的目录结构"):
        print(event)

anyio.run(main)
```

### 3. 模型覆盖优先级

优先级从高到低：

- 调用级参数：`query(..., model=...)` / `run(..., model=...)`
- 会话级：`await client.set_model(...)` 或 `connect(model=...)`
- 默认级：`CodexAgentOptions.model`

## 兼容说明（弃用路径）

旧调用 `receive_response(prompt=...)` 仍可用，但会发出 `DeprecationWarning`。建议迁移到：

- 会话式：`connect()` -> `query(...)` -> `receive_response()`
- one-shot：`run(...)`

详细迁移示例见 `MIGRATION.md`。

## 动态工具（类 Claude SDK 接口）

Codex app-server 支持动态工具调用。SDK 提供 `@tool` 装饰器，传入 `dynamic_tools` 后会走 app-server 路径。

```python
import anyio
from codex_agent_sdk import CodexAgentOptions, CodexSDKClient, tool

@tool("greet", "Greet a user", {"name": {"type": "string"}})
async def greet(args):
    return {"content": [{"type": "text", "text": f"Hello {args['name']}!"}]}

async def main():
    options = CodexAgentOptions(
        dynamic_tools=[greet],
        use_app_server=True,
        ask_for_approval="never",
        sandbox="workspace-write",
    )

    async with CodexSDKClient(options) as client:
        await client.query("请用 greet 工具向 Alice 打招呼")
        async for event in client.receive_response():
            print(event)

anyio.run(main)
```

`@tool(..., input_schema=...)` 支持两种写法：

- 完整对象 Schema：`{"type": "object", "properties": {...}}`
- 简写属性映射：`{"name": {"type": "string"}}`

## 审批与用户输入回调（App-Server）

```python
from codex_agent_sdk import CodexAgentOptions

def approve_command(payload):
    return "allow"  # 或 "deny" / "defer"

def approve_file_change(payload):
    return "allow"

def provide_user_input(payload):
    return "yes"

options = CodexAgentOptions(
    approval_callbacks={
        "command": approve_command,      # 或 "command_execution"
        "file_change": approve_file_change,  # 或 "fileChange"
    },
    request_user_input_callback=provide_user_input,
)
```

回调约定：

- 审批回调返回：`"allow"` / `"deny"` / `"defer"`
- 支持别名（如 `"accept"`、`"approved"`、`"reject"`）
- 返回 `"defer"`（或 `None`）会回落到 `ask_for_approval` 策略
- 用户输入回调返回：`str` 或 `dict`
- 返回类型非法会抛出明确 SDK 错误

审批回落矩阵：

| `ask_for_approval` | 回落决策 |
| --- | --- |
| `never` | allow |
| `on-request` | deny |
| `on-failure` | deny |
| `untrusted` | deny |

## Event Hook（可观测性）

Hook 当前定位是可观测性：可记录事件、提前中止流；不支持修改 Codex 工具执行输入输出。

```python
from codex_agent_sdk import CodexAgentOptions, HookAbort

async def log_events(event):
    print("EVENT:", event)

def stop_on_error(event):
    if getattr(event, "kind", None) == "error":
        raise HookAbort("Stop on error")

options = CodexAgentOptions(
    event_hooks={
        "*": [log_events],
        "error": [stop_on_error],
        "tool": [log_events],
        "turn": [log_events],
    }
)
```

## 事件模型（粗粒度）

解析后事件会有 `kind`：

- `thread`：会话生命周期
- `turn`：轮次生命周期与完成
- `item`：消息或增量片段
- `tool`：工具/命令/文件变更
- `log`：stdout/stderr/日志
- `error`：错误
- `raw`：未分类

可直接查看原始负载：

```python
async for event in query(prompt="hello"):
    print(event.kind, getattr(event, "event_type", None))
    print(getattr(event, "raw", None) or getattr(event, "event", None))
```

## 自定义事件解析

```python
from codex_agent_sdk import CodexAgentOptions

def my_parser(event: dict):
    return event

def is_final(event):
    return False

options = CodexAgentOptions(
    event_parser=my_parser,
    final_event_predicate=is_final,
)
```

## MCP Helpers（App-Server）

```python
import anyio
from codex_agent_sdk import CodexSDKClient

async def main():
    client = CodexSDKClient()
    print(await client.mcp_status_list())
    print(await client.mcp_reload())

anyio.run(main)
```

或使用顶层 helper：

```python
from codex_agent_sdk import mcp_status_list, mcp_reload

async def main():
    print(await mcp_status_list())
    print(await mcp_reload())
```

## 限制与注意事项

- 当前脚手架依赖 Codex JSONL 输出（`codex exec --json`）。
- 消息解析是启发式策略，建议结合你的真实样本继续细化。
- 动态工具目前走 app-server，并要求字符串 prompt。
- `Hook` 是事件级能力，不是完整的工具前/后置变更钩子。
- 目前不提供 Python 侧 in-process MCP server（仅提供 Codex CLI 层面的 MCP 管理 helper）。

## 高级选项

- `CodexAgentOptions.app_server_request_timeout_seconds`
  - 默认 `30.0`
  - `None` 或 `<= 0` 表示禁用超时
- 环境变量继承策略
  - `inherit_env=True`：继承父进程环境（默认）
  - `env_allowlist=[...]`：仅保留白名单变量
  - `env_denylist=[...]`：剔除黑名单变量
  - `env={...}`：显式注入/覆盖变量

## 安全与隐私

- SDK 通过子进程调用 `codex`，默认会继承当前 shell 环境。
- 如需最小化环境暴露，建议：
  - `inherit_env=False`
  - 配置 `env_allowlist` / `env_denylist`
  - 只通过 `env={...}` 注入必需变量
- app-server 模式下，审批回调是主要策略钩子；回调返回 `"defer"` 会按 `ask_for_approval` 回落。
