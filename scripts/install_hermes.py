#!/usr/bin/env python3
"""Install Claude SEO into a Hermes Agent profile.

Copies every skill into ``$HERMES_HOME/skills/software-development/``,
rewrites Claude-plugin launcher tokens to the Hermes wrapper, strips
``model: opus|sonnet|haiku`` pins so subagents inherit the current Hermes
session model, and (unless ``--skip-setup``) creates the isolated Python
runtime under ``$HERMES_HOME/runtime/claude-seo``.

This does not require Claude Code, Anthropic credentials, or a specific
LLM. Whatever model Hermes is running is the model that runs the skills.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

CATEGORY = "software-development"
CANONICAL_LAUNCHER = '"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo"'
MODEL_LINE = re.compile(
    r"^(model:\s*(?:opus|sonnet|haiku|inherit)[ \t]*)(\r?\n)",
    re.MULTILINE | re.IGNORECASE,
)
MARKER_NAME = "hermes-install.json"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_hermes_home() -> Path:
    raw = os.environ.get("HERMES_HOME")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".hermes").resolve()


def neutralize_model_pins(text: str) -> str:
    """Drop Claude Code model pins so the host session model is used."""
    return MODEL_LINE.sub("", text)


def rewrite_launcher(text: str, quoted_launcher: str) -> str:
    return text.replace(CANONICAL_LAUNCHER, quoted_launcher)


def quoted_hermes_launcher(hermes_home: Path) -> str:
    default = Path.home() / ".hermes"
    try:
        is_default = hermes_home.resolve() == default.resolve()
    except OSError:
        is_default = False
    if is_default:
        return (
            '"${HERMES_HOME:-$HOME/.hermes}/skills/'
            f"{CATEGORY}/seo/scripts/hermes-seo\""
        )
    return f'"{hermes_home / "skills" / CATEGORY / "seo" / "scripts" / "hermes-seo"}"'


def _copy_tree(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "ms-playwright"),
        dirs_exist_ok=False,
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _chmod_exec(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _rewrite_tree(root: Path, quoted_launcher: str, neutralize: bool) -> int:
    changed = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".json", ".sh", ".ps1", ".txt"}:
            continue
        original = path.read_text(encoding="utf-8")
        updated = rewrite_launcher(original, quoted_launcher)
        if neutralize:
            updated = neutralize_model_pins(updated)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def plugin_version(root: Path) -> str:
    for manifest in (root / ".claude-plugin" / "plugin.json", root / "runtime-plugin.json"):
        try:
            value = json.loads(manifest.read_text(encoding="utf-8")).get("version")
            if isinstance(value, str):
                return value
        except (OSError, ValueError):
            pass
    return "unknown"


def skill_names(root: Path) -> list[str]:
    skills = root / "skills"
    names = sorted(p.name for p in skills.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    return names


def install(hermes_home: Path, *, skip_setup: bool, skip_browser: bool) -> Path:
    root = repo_root()
    skills_src = root / "skills"
    if not (skills_src / "seo" / "SKILL.md").is_file():
        raise SystemExit(f"not a claude-seo checkout: missing {skills_src / 'seo' / 'SKILL.md'}")
    if not (root / "scripts" / "claude-seo").is_file():
        raise SystemExit("missing scripts/claude-seo launcher")

    dest_skills = hermes_home / "skills" / CATEGORY
    dest_seo = dest_skills / "seo"
    runtime_dir = hermes_home / "runtime" / "claude-seo"
    dest_skills.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    names = skill_names(root)
    print(f"Installing {len(names)} skills into {dest_skills} ...")
    for name in names:
        _copy_tree(skills_src / name, dest_skills / name)

    scripts_dest = dest_seo / "scripts"
    _copy_tree(root / "scripts", scripts_dest)
    _chmod_exec(scripts_dest / "claude-seo")
    hermes_wrapper = scripts_dest / "hermes-seo"
    if hermes_wrapper.is_file():
        _chmod_exec(hermes_wrapper)

    for extra in ("data", "schema", "pdf"):
        src = root / extra
        if src.is_dir():
            _copy_tree(src, dest_seo / extra)

    req = root / "requirements.txt"
    if req.is_file():
        shutil.copy2(req, dest_seo / "requirements.txt")
    plugin = root / ".claude-plugin" / "plugin.json"
    if plugin.is_file():
        shutil.copy2(plugin, dest_seo / "runtime-plugin.json")

    agents_src = root / "agents"
    agents_dest = dest_seo / "agents"
    if agents_src.is_dir():
        _copy_tree(agents_src, agents_dest)

    hermes_doc = root / "HERMES.md"
    if hermes_doc.is_file():
        dest_ref = dest_seo / "references"
        dest_ref.mkdir(parents=True, exist_ok=True)
        shutil.copy2(hermes_doc, dest_ref / "hermes.md")

    quoted = quoted_hermes_launcher(hermes_home)
    rewritten = _rewrite_tree(dest_skills, quoted, neutralize=True)
    print(f"Rewrote launcher/model pins in {rewritten} installed files.")

    marker = {
        "version": plugin_version(root),
        "category": CATEGORY,
        "skills": names,
        "launcher": quoted,
        "source": str(root),
        "fork": "Alextechgamer/claude-seo",
    }
    _write_text(runtime_dir / MARKER_NAME, json.dumps(marker, indent=2, sort_keys=True) + "\n")

    if skip_setup:
        print("Skipping runtime setup (--skip-setup).")
        return dest_seo

    launcher = dest_seo / "scripts" / "hermes-seo"
    if not launcher.is_file():
        launcher = dest_seo / "scripts" / "claude-seo"
    cmd = [str(launcher), "setup"]
    if skip_browser:
        cmd.append("--skip-browser")
    env = os.environ.copy()
    env["CLAUDE_SEO_DATA_DIR"] = str(runtime_dir)
    env["HERMES_HOME"] = str(hermes_home)
    print(f"Creating isolated runtime in {runtime_dir} ...")
    result = subprocess.run(cmd, env=env, check=False)
    if result.returncode not in (0, 10):
        raise SystemExit(f"runtime setup failed with exit {result.returncode}")
    if result.returncode == 10:
        print("Core runtime ready; Chromium setup is incomplete (non-fatal).")
    return dest_seo


def uninstall(hermes_home: Path) -> None:
    runtime_dir = hermes_home / "runtime" / "claude-seo"
    marker_path = runtime_dir / MARKER_NAME
    names: list[str] = []
    if marker_path.is_file():
        try:
            payload = json.loads(marker_path.read_text(encoding="utf-8"))
            names = list(payload.get("skills") or [])
        except (OSError, ValueError):
            names = []
    dest_skills = hermes_home / "skills" / CATEGORY
    if not names and dest_skills.is_dir():
        names = [p.name for p in dest_skills.iterdir() if p.is_dir() and p.name.startswith("seo")]
    removed = []
    for name in names:
        target = dest_skills / name
        if not target.is_dir():
            continue
        skill = target / "SKILL.md"
        if skill.is_file():
            text = skill.read_text(encoding="utf-8")
            if "hermes-seo" not in text and "AgriciDaniel" not in text and name != "seo":
                print(f"Skipping {target} (does not look like a Claude SEO install).")
                continue
        shutil.rmtree(target)
        removed.append(name)
    if runtime_dir.is_dir():
        shutil.rmtree(runtime_dir)
    print(f"Removed skills: {', '.join(removed) if removed else '(none)'}")
    print(f"Removed runtime dir: {runtime_dir}")


def neutralize_repo_agents() -> int:
    """Strip model pins in this checkout's agents/ (hermes branch maintenance)."""
    agents = repo_root() / "agents"
    changed = 0
    for path in sorted(agents.glob("*.md")):
        original = path.read_text(encoding="utf-8")
        updated = neutralize_model_pins(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install Claude SEO for Hermes Agent")
    parser.add_argument(
        "--hermes-home",
        type=Path,
        default=None,
        help="Hermes profile home (default: $HERMES_HOME or ~/.hermes)",
    )
    parser.add_argument("--skip-setup", action="store_true", help="copy skills only, do not create the venv")
    parser.add_argument("--skip-browser", action="store_true", help="skip Playwright Chromium during setup")
    parser.add_argument("--uninstall", action="store_true", help="remove a previous Hermes install")
    parser.add_argument(
        "--neutralize-agents",
        action="store_true",
        help="strip model: opus/sonnet/haiku from this checkout's agents/ and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.neutralize_agents:
        n = neutralize_repo_agents()
        print(f"Neutralized model pins in {n} agent files.")
        return 0
    hermes_home = args.hermes_home.expanduser().resolve() if args.hermes_home else default_hermes_home()
    if args.uninstall:
        uninstall(hermes_home)
        return 0
    dest = install(hermes_home, skip_setup=args.skip_setup, skip_browser=args.skip_browser)
    print("")
    print("Claude SEO is installed for Hermes.")
    print(f"  Skills:  {dest.parent}")
    print(f"  Runtime: {hermes_home / 'runtime' / 'claude-seo'}")
    print("  Model:   whatever Hermes is running (no opus/sonnet pin)")
    print("")
    print("Start a new Hermes chat, then:  seo audit https://example.com")
    print("Or from this checkout:          ./scripts/hermes-seo doctor --json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
