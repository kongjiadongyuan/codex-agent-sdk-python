# Migration Guide（中文）

本文档用于从旧版 `CodexSDKClient` 调用方式迁移到当前推荐接口。

## 背景

旧版常见写法：

```python
async for event in client.receive_response(prompt="..."):
    ...
```

该写法仍可运行，但会触发 `DeprecationWarning`。

## 推荐写法（会话式）

```python
async with CodexSDKClient(options) as client:
    await client.query("...")
    async for event in client.receive_response():
        ...
```

### 优势

- 与 Claude SDK 的调用节奏一致。
- `query`（发送）和 `receive_response`（接收）职责分离，行为更明确。
- 便于后续扩展中断、切模、会话控制。

## One-shot 场景

如果你不需要显式会话控制，推荐直接：

```python
async for event in client.run("..."):
    ...
```

## 模型优先级

从高到低：

1. `query(..., model=...)` / `run(..., model=...)`
2. `await client.set_model(...)` 或 `connect(model=...)`
3. `CodexAgentOptions.model`

## 兼容行为说明

- `receive_response(prompt=...)`：保留，触发弃用告警。
- `query(...)`：现在是会话式发送动作，需先 `connect()`，不再直接返回事件流。

## 常见迁移模式

### 模式 1：单轮调用

旧：

```python
async for e in client.receive_response("hello"):
    ...
```

新：

```python
async for e in client.run("hello"):
    ...
```

### 模式 2：多轮会话

旧：

```python
async for e in client.receive_response("q1"):
    ...
async for e in client.receive_response("q2"):
    ...
```

新：

```python
async with client:
    await client.query("q1")
    async for e in client.receive_response():
        ...

    await client.query("q2")
    async for e in client.receive_response():
        ...
```
