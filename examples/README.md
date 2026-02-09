# Codex SDK 示例（Claude 对标集合）

该目录为 `claude-agent-sdk-python/examples` 中每个 Python 示例提供了 Codex 侧的对应实现。

## 运行方式

在仓库根目录执行：

```bash
python examples/quick_start.py
python examples/streaming_mode.py all
```

本地环境可选稳定性开关：

- `CODEX_SDK_EXAMPLE_FORCE_MEDIUM_REASONING=1`
  - 在辅助函数中附加 `model_reasoning_effort="medium"`。
- `CODEX_SDK_EXAMPLE_QUIET_STDERR=1`
  - 在安装 stderr hook 的示例中，抑制转发的 Codex stderr 行输出。

## 统一调用风格

`CodexSDKClient` 示例默认采用会话式写法（对齐 Claude 风格）：

1. `await client.query(...)`
2. `async for event in client.receive_response(): ...`

one-shot 场景可使用 `client.run(...)`。

## Claude -> Codex 对照表

| Claude 示例 | Codex 对应示例 | 说明 |
| --- | --- | --- |
| `quick_start.py` | `quick_start.py` | 1:1 快速开始流程。 |
| `streaming_mode.py` | `streaming_mode.py` | 基于 `CodexSDKClient` 的多模式流式演示。 |
| `streaming_mode_ipython.py` | `streaming_mode_ipython.py` | 面向 Notebook 的辅助用法（`await ask(...)`）。 |
| `streaming_mode_trio.py` | `streaming_mode_trio.py` | 使用 AnyIO Trio 后端（`pip install trio`）。 |
| `hooks.py` | `hooks.py` | 粗粒度事件 Hook（`*`、`item`、`tool`、`turn` 等）。 |
| `include_partial_messages.py` | `include_partial_messages.py` | 流式打印 partial item 事件。 |
| `tool_permission_callback.py` | `tool_permission_callback.py` | App-server 审批回调（`command`、`file_change`）。 |
| `mcp_calculator.py` | `mcp_calculator.py` | 使用动态工具（Codex 对应“进程内可调用工具”场景）。 |
| `plugin_example.py` | `plugin_example.py` | 通过动态工具 + 指令文件模拟插件式行为。 |
| `tools_option.py` | `tools_option.py` | 通过 `config_overrides` 与 `search` 调整工具行为。 |
| `system_prompt.py` | `system_prompt.py` | 演示 `developer_instructions` + `model_instructions_file`。 |
| `setting_sources.py` | `setting_sources.py` | 展示 Python 侧显式配置分层组合。 |
| `agents.py` | `agents.py` | 角色化本地 Agent 的封装模式。 |
| `filesystem_agents.py` | `filesystem_agents.py` | 从 `examples/agents/` 加载 Agent Markdown。 |
| `max_budget_usd.py` | `max_budget_usd.py` | 本地事件预算守卫模式（当前无原生 USD 上限）。 |
| `stderr_callback_example.py` | `stderr_callback_example.py` | 捕获 CLI stderr 输出行。 |

## 现有 Codex 专属补充示例

- `dynamic_tools.py`
- `mcp_helpers.py`
- `resume_session.py`

## 当前协议缺口（重要）

- 当前 SDK 尚未提供原生 `max_budget_usd`。
- Codex CLI 协议暂无 Claude 风格插件包直接加载 API。
- Codex CLI 协议暂无命名 Agent 注册 API。
- Hook 回调属于事件流可观测性能力，不是完整的工具前/后置变更 Hook。
