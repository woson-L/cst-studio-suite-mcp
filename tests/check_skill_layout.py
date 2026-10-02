"""Gate: the skills in this package must follow the repository skill layout.

Reference layout (matching `Skill/CST/` in Cai-aa/CAE-Agent-Hub):

    <skill-name>/
    ├─ SKILL.md              YAML front-matter with `name` and `description`
    ├─ metadata.json         name, dir_name, category, status, source, description
    ├─ agents/openai.yaml    display_name, short_description, default_prompt
    └─ references/*.md       detail files, each named by SKILL.md

A skill copied without its references/ still loads but points at missing files, so
this gate checks that every reference named in SKILL.md actually exists.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

RE_FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
RE_REF_LINK = re.compile(r"`references/([A-Za-z0-9._-]+\.md)`")

#: A plain (unquoted) YAML scalar cannot contain ": " — the YAML parser reads it as
#: the start of a nested mapping and rejects the whole document. DSH then drops the
#: skill SILENTLY (a logger warning only), so the skill vanishes from the catalog.
#: Real incident: a description containing "through MCP tools: classify the request"
#: made cst-studio-suite-mcp invisible to the harness.
#: This is a lint, not a full YAML parser: the package must stay dependency-free,
#: and the offline gates run on a bare interpreter.
RE_PLAIN_SCALAR_COLON = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s+(\S.*)$")

problems: list[str] = []
checked = 0


def main() -> int:
    global checked
    if not SKILLS.is_dir():
        print(f"FAIL: no skills directory at {SKILLS}")
        return 2

    for skill in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        checked += 1
        rel = skill.relative_to(ROOT)
        print(f"\n=== {rel} ===")

        # --- SKILL.md -----------------------------------------------------
        skill_md = skill / "SKILL.md"
        if not skill_md.is_file():
            problems.append(f"{rel}: SKILL.md missing")
            continue
        raw_bytes = skill_md.read_bytes()
        if raw_bytes[:3] == b"\xef\xbb\xbf":
            # A BOM makes the first line "\ufeff---", so an exact front-matter
            # delimiter test fails and the harness cannot see the skill at all.
            problems.append(
                f"{rel}: SKILL.md starts with a UTF-8 BOM; writing it with "
                f"Out-File/Set-Content -Encoding UTF8 adds one on Windows. "
                f"Save as UTF-8 without BOM."
            )
        text = raw_bytes.decode("utf-8-sig")
        fm = RE_FRONT_MATTER.match(text)
        if not fm:
            problems.append(f"{rel}: SKILL.md has no YAML front-matter block")
        else:
            block = fm.group(1)
            for field in ("name", "description"):
                if not re.search(rf"^{field}\s*:\s*\S", block, re.MULTILINE):
                    problems.append(f"{rel}: SKILL.md front-matter has no {field}")
            m = re.search(r"^name\s*:\s*(\S+)", block, re.MULTILINE)
            if m and m.group(1) != skill.name:
                problems.append(
                    f"{rel}: front-matter name {m.group(1)!r} != directory {skill.name!r}"
                )
            # Unquoted scalars must not contain ': ' — that makes the YAML invalid and
            # the harness drops the skill without an error the operator would notice.
            for line in block.splitlines():
                if line.startswith((" ", "\t", "#", "-")):
                    continue
                mm = RE_PLAIN_SCALAR_COLON.match(line.strip())
                if not mm:
                    continue
                value = mm.group(2)
                if value[:1] in ("'", '"', "|", ">"):
                    continue          # quoted or a block scalar: safe
                if ": " in value:
                    problems.append(
                        f"{rel}: front-matter key {mm.group(1)!r} has an unquoted ': ' "
                        f"in its value, which is invalid YAML and makes DSH drop the "
                        f"whole skill silently. Quote the value or use '>-'."
                    )
        print(f"  SKILL.md {len(text.splitlines())} lines")

        # --- metadata.json ------------------------------------------------
        meta_path = skill / "metadata.json"
        if not meta_path.is_file():
            problems.append(f"{rel}: metadata.json missing")
        else:
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                meta = None
                problems.append(f"{rel}: metadata.json is not valid JSON: {exc}")
            if meta is not None:
                for field in ("name", "dir_name", "category", "status",
                              "source", "license", "description"):
                    if field not in meta:
                        problems.append(f"{rel}: metadata.json has no {field!r}")
                if meta.get("name") != skill.name:
                    problems.append(f"{rel}: metadata.json name {meta.get('name')!r} != {skill.name!r}")
                if meta.get("dir_name") != skill.name:
                    problems.append(f"{rel}: metadata.json dir_name {meta.get('dir_name')!r} != {skill.name!r}")
                print(f"  metadata.json ok (category={meta.get('category')!r})")

        # --- agents/openai.yaml -------------------------------------------
        yml = skill / "agents" / "openai.yaml"
        if not yml.is_file():
            problems.append(f"{rel}: agents/openai.yaml missing")
        else:
            ytext = yml.read_text(encoding="utf-8")
            for key in ("display_name", "short_description", "default_prompt"):
                if not re.search(rf"^{key}\s*:\s*\S", ytext, re.MULTILINE):
                    problems.append(f"{rel}: agents/openai.yaml has no {key}")
            print("  agents/openai.yaml ok")

        # --- references ---------------------------------------------------
        refs_dir = skill / "references"
        named = set(RE_REF_LINK.findall(text))
        present = set()
        if refs_dir.is_dir():
            # only files directly in references/, as the links are `references/x.md`
            present = {p.name for p in refs_dir.glob("*.md")}
        if named - present:
            problems.append(
                f"{rel}: SKILL.md points at missing reference file(s): "
                f"{sorted(named - present)}"
            )
        if present - named:
            problems.append(
                f"{rel}: reference file(s) never mentioned by SKILL.md (dead weight, "
                f"the agent will not know to read them): {sorted(present - named)}"
            )
        if named and not (named - present):
            print(f"  references ok: {len(named)} file(s), all named by SKILL.md")

        # A router SKILL.md should stay short; long content belongs in references/.
        n_lines = len(text.splitlines())
        if n_lines > 160:
            problems.append(
                f"{rel}: SKILL.md is {n_lines} lines. Keep it a router and move detail "
                f"into references/ (the repository reference skill is ~89 lines)."
            )

    print(f"\nskills checked: {checked}")
    if problems:
        print(f"\nPROBLEMS ({len(problems)}):")
        for p in problems:
            print("  [FAIL]", p)
    else:
        print("  [ ok ] every skill matches the repository layout")
    print(f"\nproblems found: {len(problems)}")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
