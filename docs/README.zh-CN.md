# agent-mcp-check（中文）

> **你的 MCP Server 敢过一遍安全体检吗？**  
> MCP 服务器一键黑盒安全体检——6 项探针、PASS/FAIL/WARN、哈希链留痕。

`agent-mcp-check` 启动你的 MCP 服务器（stdio 传输），向它抛出一组畸形与恶意 JSON-RPC 消息。行为正确的服务器会全部以标准 JSON-RPC 错误拒绝；粗心的服务器会崩溃、挂起，或更糟——**执行一个本不该运行的工具**。它是 **Verifiable-agent 家族**成员。

## 为什么需要它

MCP 是 AI Agent 时代的"新 Unix 管道"。大家都在快速发布 MCP 服务器，而大多数从未被拿 `{"method": "tools/call", "params": null}` 推过。这个工具把"我的 MCP 服务器是否 fail-closed"变成一条命令。

**你能得到：**

- **6 项黑盒探针**：畸形参数、未知方法、缺失工具名、无 id 通知、未知工具、缺失参数
- 每个探针 **PASS / FAIL / WARN** 分级，附带完整收发报文
- **哈希链探针留痕**：每条判定写入可验证的 JSONL 链
- 零依赖——纯 Python 3.9+ 标准库，可启动任意 stdio MCP 服务器

## 安装

```bash
pip install agent-mcp-check
```

## 快速开始

```bash
# 探测以 `python -m my_server` 启动的 MCP 服务器（stdio 传输）
agent-mcp-check run --command python --args -m my_server

# 附带哈希链留痕
agent-mcp-check run --command npx --args mcp-server-filesystem --trail ./probe.trail.jsonl
```

## 实测输出

```
$ agent-mcp-check run --command python --args tests/mock_mcp_server.py
# MCP Server Security Check

- **Server**: `python tests/mock_mcp_server.py`
- **Grade**: **PASS**
- **Passed / Failed / Warned**: 6 / 0 / 0

| Probe | Description | Status | Note |
|:--|:--|:--|:--|
| P-01 | malformed JSON must yield an error, not a crash | PASS | server answered with a JSON-RPC error |
...
```

失败的服务器会在对应条目显示 `FAIL` 及收到的报文，让你看到它到底哪里行为失当。

## 探针

| ID | 探针 | 为什么重要 |
|:--|:--|:--|
| P-01 | `tools/call` 带 `params: null` | fail-closed 服务器拒绝；弱的服务器崩溃 |
| P-02 | 未知方法 | 必须回 -32601，绝不静默成功 |
| P-03 | `tools/call` 缺失工具名 | 协议错误，不得漏过 |
| P-04 | 无 `id` 的通知 | 服务器绝不可为它执行工具 |
| P-05 | 未知工具 | 必须报错，不得假装成功 |
| P-06 | `tools/call` 缺失 `arguments` | 协议错误 |

## 设计不变量

| # | 不变量 | 由谁保证 |
|:--|:--|:--|
| 1 | 每个畸形调用都期望 JSON-RPC 错误 | `_run_probe` |
| 2 | 无响应 / 崩溃 / 挂起 → FAIL | `_run_probe` |
| 3 | 留痕是哈希链（prev_hash + entry_hash） | `run_checks` |
| 4 | 只用合成数据——探针永不落盘真实 payload | `_build_probes` |
| 5 | 每次运行全新启动服务器 | `McpProbeClient.start` |

## 许可证

MIT。