"""Hermes install adapter for Claude SEO."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_hermes.py"
CANONICAL = '"${CLAUDE_PLUGIN_ROOT}/scripts/claude-seo"'


def test_repo_agents_have_no_claude_model_pins() -> None:
    pinned = []
    for path in (ROOT / "agents").glob("*.md"):
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip().lower()
            if stripped.startswith("model:") and any(
                token in stripped for token in ("opus", "sonnet", "haiku")
            ):
                pinned.append(f"{path.name}: {line.strip()}")
    assert pinned == [], "agent model pins leak Claude-only routing: " + "; ".join(pinned)


def test_hermes_wrapper_is_executable_sibling() -> None:
    wrapper = ROOT / "scripts" / "hermes-seo"
    assert wrapper.is_file()
    text = wrapper.read_text(encoding="utf-8")
    assert "CLAUDE_SEO_DATA_DIR" in text
    assert 'exec "${launcher_dir}/claude-seo"' in text
    if os.name == "posix":
        assert wrapper.stat().st_mode & stat.S_IXUSR


def test_install_hermes_copies_and_rewrites(tmp_path: Path) -> None:
    dest = tmp_path / "hermes-home"
    result = subprocess.run(
        [sys.executable, str(INSTALLER), "--hermes-home", str(dest), "--skip-setup"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr

    seo = dest / "skills" / "software-development" / "seo"
    assert (seo / "SKILL.md").is_file()
    assert (seo / "scripts" / "hermes-seo").is_file()
    assert (seo / "scripts" / "runtime.py").is_file()
    assert (seo / "references" / "hermes.md").is_file()
    assert (dest / "runtime" / "claude-seo" / "hermes-install.json").is_file()

    skill_text = (seo / "SKILL.md").read_text(encoding="utf-8")
    assert CANONICAL not in skill_text
    assert "hermes-seo" in skill_text

    audit = dest / "skills" / "software-development" / "seo-audit" / "SKILL.md"
    assert audit.is_file()
    assert CANONICAL not in audit.read_text(encoding="utf-8")

    for agent in (seo / "agents").glob("*.md"):
        body = agent.read_text(encoding="utf-8")
        assert "model: opus" not in body
        assert "model: sonnet" not in body

    marker = json.loads((dest / "runtime" / "claude-seo" / "hermes-install.json").read_text())
    assert "seo" in marker["skills"]
    assert "seo-audit" in marker["skills"]
    assert marker["fork"] == "Alextechgamer/claude-seo"

    # Source tree must keep the Claude plugin token so upstream tests pass.
    source_skill = (ROOT / "skills" / "seo" / "SKILL.md").read_text(encoding="utf-8")
    assert CANONICAL in source_skill


def test_uninstall_hermes_removes_copied_skills(tmp_path: Path) -> None:
    dest = tmp_path / "hermes-home"
    subprocess.run(
        [sys.executable, str(INSTALLER), "--hermes-home", str(dest), "--skip-setup"],
        cwd=str(ROOT),
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        [sys.executable, str(INSTALLER), "--hermes-home", str(dest), "--uninstall"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (dest / "skills" / "software-development" / "seo").exists()
    assert not (dest / "runtime" / "claude-seo").exists()


@pytest.mark.skipif(os.name != "posix", reason="hermes-seo is a bash wrapper")
def test_hermes_wrapper_doctor_help() -> None:
    env = {**os.environ, "PYTHON_COLORS": "0", "NO_COLOR": "1"}
    env.pop("FORCE_COLOR", None)
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "hermes-seo"), "doctor", "--help"],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert "usage: claude-seo doctor" in result.stdout
