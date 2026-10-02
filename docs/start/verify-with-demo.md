# Verify the installation with a demo project

> **Documentation index** › [Getting started](../README.md) › Verify with the demo

`check_install.py` proves the server *loads*. This page proves it can actually **drive
CST**: open a project, build geometry, place a port, set the band and solve.

The repository ships a small, self-contained CST project for exactly this:
[`test_demo/test_demo.cst`](../../test_demo/test_demo.cst) — 22 KB, no companion
directory, no machine-specific content.

---

## What you need first

| | |
| --- | --- |
| CST Studio Suite 2026 | Installed and licensed on this machine |
| The MCP server | Registered with your harness — see [Installation](install.md) |
| The two skills | `cst-studio-suite-mcp` and `cst2026-simulation-execution`, from [`skills/`](../../skills) — see [Install via another agent](install-via-agent.md) for the copy step |
| A working `.env` | `python check_install.py --fix` writes it |

## Hand this prompt to your agent

Replace the two placeholders — your harness name, and the folder you installed the MCP
into — then paste the whole thing.

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

The same prompt in English:

```text
Install this cst-studio-suite-mcp into my local harness (<your harness: dsh, codex,
WorkBuddy, ...>). The MCP path is: <the folder you installed it in>. Also install the two
skills in the skills folder: `cst-studio-suite-mcp` and `cst2026-simulation-execution`.

Then verify the installation through that MCP and those two skills. The verification task:

1. Open the project at `<MCP folder>\test_demo\test_demo.cst`.
2. Create a cube named box, 50 mm per side, material iron.
3. Create a thin sheet 2 mm below the box, 5 mm thick, 50 mm x 50 mm, material PEC.
4. Place an excitation port at the centre of that sheet: a discrete port connecting the
   box and the sheet.
5. Set the frequency range to 0-100 MHz.
6. Solve for S-parameters.

When the install and the verification are done, report the files used, the steps taken and
the result.
```

## What a pass looks like

| Check | Expected |
| --- | --- |
| Project opened | The agent can name the project it opened; `cst_project_info_tool` shows it as active |
| Geometry | `cst_model_audit_tool` reports **two** solids: the 50 mm cube in `iron`, the sheet in PEC |
| Port | `cst_list_ports_tool` reports exactly one **Discrete** port at 50 Ω |
| Band | `cst_frequency_overview_tool` shows `0 - 100` |
| Solve | `cst_run_solver_tool` returns, and the CST message window carries no `ERROR` |
| Result | `cst_read_s11_tool` returns a number from `1D Results\S-Parameters\S1,1` |

Two things worth knowing about this particular model, so a plausible-looking result is not
mistaken for a good one:

* **The reference impedance must read 50 Ω.** `cst_read_reference_impedance_tool` is the
  check — a port referenced to something else silently rescales every S-parameter.
* **The model is deliberately not an antenna.** A 50 mm cube at 0–100 MHz is far below any
  resonance, so S11 will be close to 0 dB. That is the correct outcome; this task verifies
  that the *toolchain* works, not that a design performs. The recorded run of this exact
  model measured **−0.144 dB at 100 MHz** — treat that as the reference value, not as a
  disappointing result.

If your numbers differ from a previous run, compare the frequency range and the reference
impedance first — those two account for most surprises.

## Where this fits

The same chain, with every individual call and payload recorded, is in
[`tests/evidence/mcp_calls_123_report.md`](../../tests/evidence/mcp_calls_123_report.md)
(30 calls, 0 failures). This page is the short, human-facing version of it.

---

## Related documents

* [Installation](install.md) — the full install walkthrough
* [Install via another agent](install-via-agent.md) — hand the install, and this verification, to an AI
* [Quick start](../use/quickstart.md) — the first tool call, without a demo project
* [Rules that keep results trustworthy](../use/rules.md) — why the reference impedance is checked
* [Verification](../dev/verification.md) — the checks the project runs on itself
