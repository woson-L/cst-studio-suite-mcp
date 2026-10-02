# CST-MCP —— 通过 MCP 驱动 CST Studio Suite 2026

[English](README.md) | [简体中文](README.zh-CN.md)

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)
[![MCP](https://img.shields.io/badge/MCP-stdio-6E4AFF.svg)](https://modelcontextprotocol.io)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](#运行环境)
[![Tools: 84](https://img.shields.io/badge/tools-84-brightgreen.svg)](docs/use/tool-catalogue.md)
[![CI](https://github.com/woson-L/cst-studio-suite-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/woson-L/cst-studio-suite-mcp/actions/workflows/ci.yml)

一个 MCP 服务端，通过 CST 自带的自动化 API（`cst.interface`、`cst.results`）驱动
**CST Studio Suite 2026**：建模、材料、端口、边界、网格、求解器选择、频率范围、场监视器、
求解、结果读取与证据导出。

**84 个工具 · 14 个类别 · stdio 传输 · 不访问网络。**

初次使用？**[安装](docs/start/install.md)** → **[快速上手](docs/use/quickstart.md)**
→ **[用 demo 工程验证安装](docs/start/verify-with-demo.md)**。

---

## 出处

本服务是 [`Cai-aa/CAE-Agent-Hub`](https://github.com/Cai-aa/CAE-Agent-Hub)（`MCP/CST/`）中
CST MCP 的**重构**。该项目为 MIT 许可，其版权声明保留在 [`LICENSE`](LICENSE) 中。

| | 上游 | 本项目 |
| --- | --- | --- |
| 工具数 | 51 个，在单个 623 行的 `mcp_server.py` 中 | **84 个 / 14 类**，位于 `cst_mcp/` 包内 |
| 内置 runtime CLI | 824 个文件 | 无 —— 由内置命令注册表提供 |
| 离线检查、CI | 该组件无 | 每次推送 9 个门禁，Python 3.10 与 3.12 |
| 文档、技能 | 1 份 README；技能放在 hub 根目录 | 17 份文档，2 个随包技能 |

此处在上游之上新增：拦截会让 CST 卡死的 history 块的护栏、由最小特征尺寸反推网格、
覆盖工程时不再残留 `Result/` 目录、以及端口返回判定而非裸数字。
**完整对比见 [与上游的差异](docs/reference/differences-from-upstream.md)。**

---

## 为什么需要它

只具备通用 CST 知识的模型，生成的自动化脚本往往**看着正确、却在很具体的地方悄悄失败**。
下表中每个坑都在 CST 2026.2 上实测过，原始报错记录在
[`tests/evidence/known_failures.md`](tests/evidence/known_failures.md)。

| 坑 | 具体表现 |
| --- | --- |
| **端口模式消失（截止频率过高）** | 1.6 mm 微带截面上的波导端口，截止频率 **51.9 GHz**、2.4 GHz 处波阻抗 **6.2 kΩ**。于是 S 参数被参考到 7623 Ω 而不是 50 Ω，S11 变成一条 **−0.6 dB** 的平线 —— 很容易误认为是天线。而求解器报的是成功。 |
| **在结构宏里 `Rebuild`** | CST 会拒绝，且实测中 Design Environment 被**永久卡死** —— 之后每次调用都挂起。 |
| **材料库材料 + 改参数** | 从材料库加载的材料经保存/重开后不再存在，下一次 rebuild 会在用到它的实体上失败。对这类工程做参数扫描，**每一个**算例都会失败。 |
| **靠删 `.cst` 来覆盖工程** | 一个 CST 工程是 `.cst` 文件**加上**同名伴随目录（含 `Model/`、`Result/`）。只删文件会留下目录，CST 回 `The project directory … already exists and is non-empty`。交互界面下，这就是那个"是否删除旧结果"的确认框。 |
| **端口建在局部坐标系** | 端点坐标会被当作全局 `xyz` 读取，于是 `uvw` 端口悄悄落在别的位置。 |

服务端把这些实测结论固化成护栏、默认值和拒绝信息，让错误**在工具调用处大声失败**，
而不是悄悄污染结果。

## 能做什么

| 类别 | 工具数 | 覆盖 |
| --- | --- | --- |
| `session` | 14 | 健康检查、探测、连接、工程新建/打开/保存/关闭、消息窗口、裸 VBA、history 块、释放 CST |
| `parameters` | 4 | 设计参数的读取、创建、修改、删除 |
| `geometry` | 14 | 长方体、圆柱、球、锥、环、椭圆柱、键合线、布尔、变换、拉伸、组件 |
| `material` | 3 | 创建材料、指派材料、从材料库加载 |
| `port` | 3 | 离散端口、波导端口、列出端口 |
| `solver` | 11 | 求解器选择、频率范围、频域/时域/本征模配置、边界、对称、背景、求解 |
| `mesh` | 2 | 网格类型与密度，含 `smallest_feature_mm` |
| `monitor` | 2 | 添加与列出场监视器 |
| `results` | 2 | 结果树、读取一维结果项 |
| `verify` | 5 | S11、参考阻抗、端口信息（带判定）、能量预算、模型审计 |
| `export` | 3 | Touchstone、ASCII、汇总 JSON |
| `sweep` | 2 | 参数扫描：先预览算例数，再执行 |
| `runtime` | 16 | 内置命令桥与类型化包装器生成 |
| `meta` | 3 | 列出工具、完整清单、动态分发 |

完整的工具面（含参数与示例）在 [`docs/mcp_tools.json`](docs/mcp_tools.json) ——
机器可读，其他 agent 可以直接读取。

## 运行环境

| | |
| --- | --- |
| **CST Studio Suite 2026** | 商业软件，**不随本仓库分发** —— 需自行获取并授权。已在 2026.2 版本上验证。 |
| **操作系统** | Windows。CST 的自动化 API 仅支持 Windows。 |
| **Python** | 3.10 或更高，且能 `import mcp`。CST 自带的 Python 可用。 |
| **网络** | 不需要。配置从本地 `.env` 文件读取。 |

## 快速上手

```bash
# 1. 找到本机的 CST 并自动写好 .env
python check_install.py --fix

# 2. 校验：Python、依赖包、.env、工具注册表，以及一次真实的 MCP 握手
python check_install.py

# 3. 让你的 MCP 客户端指向它
#    command: python
#    args:    ["<path to>\\mcp_server.py"]
#    cwd:     <path to this folder>

# 4. 第一次调用
#    cst_health_check_tool  {}
```

`check_install.py` 退出码：就绪 `0`、有警告 `1`、有问题 `2`。完整流程（含无网络机器怎么做）
见[安装](docs/start/install.md)。

## 验证安装

`check_install.py` 只能证明服务端**能被加载**。要证明它真的**能驱动 CST**——打开工程、
建模、建端口、设频段、求解——把下面这段提示词交给你的 AI。它会安装 MCP 与两个 Skill，
然后用仓库自带的 [`test_demo/`](test_demo) 工程执行一次验证任务。

把两个占位符填好后，整段复制。

```text
请将此 cst-studio-suite-mcp 安装到本地 harness（填写你的 harness，如 dsh、codex、WorkBuddy 等），
MCP 路径为：<请填写 MCP 所在目录>，并安装 skill 文件夹下的两个 Skill：
`cst-studio-suite-mcp` 和 `cst2026-simulation-execution`。

安装完成后，请通过该 MCP 及这两个 Skill 进行验证。验证任务如下：

1. 打开工程文件：`<MCP 所在目录>\test_demo\test_demo.cst`。
2. 创建一个正方体 box，边长为 50 mm，材料设置为 iron。
3. 在 box 下方 2 mm 处创建一个薄平面 sheet，厚度为 5 mm，长宽均为 50 mm，材料设置为 PEC。
4. 在该平面中心设置一个激励端口，类型为离散端口，连接 box 与 sheet。
5. 频率范围设置为 0–100 MHz。
6. 求解 S 参数。

安装与验证完成后，请记录所用文件、操作步骤及验证结果。
```

同一段提示词的英文版在 [README.md](README.md)。

**什么算通过**、以及两个必须知道的坑 —— 参考阻抗必须读到 50 Ω；50 mm 立方体在 0–100 MHz
远低于任何谐振，所以 S11 接近 0 dB 才是正确答案 —— 见
**[用 demo 工程验证安装](docs/start/verify-with-demo.md)**。

## 一次会话长什么样

一次针对真实 CST 的完整运行：建模、配置求解器、求解、读结果、导出证据 ——
**30 次工具调用，0 次失败**。精简如下：

```
cst_connect_tool                {"launch_if_needed": true}
cst_new_project_tool            {"project_type": "mws", "path": "…\\123.cst"}
cst_define_parameters_tool      {"parameters": {"L": 50, "gap": 2, "tsheet": 5}}
cst_create_brick_tool           {"component": "parts", "name": "box", "xrange": ["-L/2","L/2"], …}
cst_add_discrete_port_tool      {"port_number": 1, "point1": [0,0,"-gap"], "point2": [0,0,"0"], "impedance": 50.0}
cst_set_solver_tool             {"solver": "HF Frequency Domain"}
cst_set_frequency_range_tool    {"fmin": 0, "fmax": 100, "unit": "MHz"}
cst_set_mesh_tool               {"mesh_type": "Tetrahedral", "steps_per_wavelength": 8}
cst_save_project_tool           {"path": "…\\123.cst", "overwrite": true}
cst_run_solver_tool             {}
cst_read_s11_tool               {"target_frequency": 100}
cst_read_reference_impedance_tool {}
cst_export_touchstone_tool      {"filename": "…\\evidence\\123_s11", "impedance": 50.0}
```

逐次调用记录见
[`tests/evidence/mcp_calls_123_report.md`](tests/evidence/mcp_calls_123_report.md)。

## 文档

全部文档在 [`docs/`](docs/)，索引见 **[docs/README.md](docs/README.md)**。

| 我想 | 读 |
| --- | --- |
| 在本机安装 | [安装](docs/start/install.md) |
| **端到端证明它能用** | **[用 demo 工程验证](docs/start/verify-with-demo.md)** |
| 把安装交给另一个 AI | [交给另一个 agent 安装](docs/start/install-via-agent.md) |
| 在已有安装上升级 | [升级](docs/start/upgrade.md) |
| 开始使用 | [快速上手](docs/use/quickstart.md) |
| 看一次会话长什么样 | [使用示例](docs/use/usage.md) |
| 浏览工具 | [工具目录](docs/use/tool-catalogue.md) |
| 了解让结果可信的规则 | [规则](docs/use/rules.md) |
| 知道 CST 2026.2 不开放什么 | [CST 2026.2 限制](docs/use/cst-2026-limits.md) |
| 知道服务端自身的限制 | [已知限制](docs/use/known-limits.md) |
| 新增一个工具或工具族 | [扩展](docs/extend/overview.md) |
| 了解仓库结构 | [目录结构](docs/dev/layout.md) |
| 跑验证 | [验证](docs/dev/verification.md) |

文档采用渐进式披露：每份都刻意写短，并链接到相邻文档。只读你当前需要的那一份即可。

## 验证

离线检查不需要安装 CST，且会在 CI 中运行：

```bash
python check_install.py --quick
python tests/smoke_registry.py
python tests/check_mcp_compliance.py
python tests/check_self_description.py
python tests/check_skill_tool_refs.py
python tests/check_skill_layout.py
python tests/check_docs_consistency.py
python tests/test_audit_regressions.py
python tests/test_port_info_verdict.py
python tests/test_save_overwrite.py
```

在线 runner 需要已授权的 CST 与约 2 GB 空闲内存；它们由人工执行，结果记录在
[验证](docs/dev/verification.md)。

## 仓库结构

```
├── mcp_server.py         MCP 入口、注册表引导、清单生成
├── check_install.py      安装验收检查
├── cst_mcp/              服务端实现，一个工具类别一个模块
├── skills/               两个随包 agent skill
├── docs/                 文档，分组索引见 docs/README.md
├── tests/                离线门禁、在线 runner、已整理的证据
└── .env.example          配置模板（`.env` 永不入库）
```

带逐文件说明的完整目录树：[目录结构](docs/dev/layout.md)。

## 参与贡献

请先读 [`AGENTS.md`](AGENTS.md) —— 它规定了文档同步要求，并由上面那些检查强制执行。
然后见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

两条底线规则，因为本项目驱动的是商业仿真软件：

1. **改动包含其文档。** 如果你的改动让某份文档变得不准确，就在同一个 PR 里改掉它。
2. **不要记录未经证实的行为。** 去读实现，或在 CST 上实测。没验证过的说法是删掉，不是合并。

## 安全

服务端在本机运行，通过 stdio 讲 MCP，不发起任何网络请求。漏洞请私下报告 —— 见
[`SECURITY.md`](SECURITY.md)。

## 许可证

[MIT](LICENSE) © 2026 Thompson Labs。

本项目**不分发 CST Studio Suite**，它是商业软件，需自行获取并授权。本项目只调用 CST 自带的
自动化 API。
