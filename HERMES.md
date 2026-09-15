# Hermes Agent: run Claude SEO on any model

This fork (`Alextechgamer/claude-seo`, `hermes` branch) is Agrici Daniel's
[claude-seo](https://github.com/AgriciDaniel/claude-seo) plus a Hermes-native
install path. The Python tools, scoring, and Google-grounded recommendations
are unchanged. What changes is the **host**:

- **No Claude Code plugin, no Anthropic requirement.**
- **No `model: opus` / `model: sonnet` pins.** Subagents inherit whatever
  model the current Hermes session is using (Grok, Claude, GPT, Gemini,
  local GGUF, anything Hermes can call).
- Skills live in `$HERMES_HOME/skills/software-development/` so Hermes
  auto-discovers them the same way it discovers every other skill.

Upstream remains the source of SEO methodology. This branch is the Hermes
adapter. Sync with `git fetch upstream && git merge upstream/main` on `main`,
then rebase/merge into `hermes`.

## Install

From a clone of this fork:

```bash
git clone --branch hermes https://github.com/Alextechgamer/claude-seo.git
cd claude-seo
bash install-hermes.sh
```

`install-hermes.sh` copies all 25 skills, rewrites launcher tokens, strips
model pins, and runs `./scripts/hermes-seo setup` (isolated venv + Chromium
under `$HERMES_HOME/runtime/claude-seo`). Use `--skip-browser` if you only
need raw HTTP fetches.

Uninstall:

```bash
bash uninstall-hermes.sh
```

Start a **new** Hermes chat after install. The current session's skill
loader will not see newly copied skills.

### In-repo use (no profile copy)

If this checkout is the workspace, Hermes already injects this file. Run
tools through the wrapper so the venv stays out of git:

```bash
./scripts/hermes-seo setup
./scripts/hermes-seo doctor --json
./scripts/hermes-seo run fetch_page.py https://example.com --json
```

Never call the bundled scripts with a bare Python interpreter.

## Any model

Claude Code agent files in `agents/*.md` originally declared `model: opus`
or `model: sonnet`. That is a Claude Code routing hint, not an SEO
requirement. On this branch:

1. Those pins are removed from `agents/*.md`.
2. `install-hermes.sh` strips them again from the installed copies, so a
   later upstream merge cannot re-pin Opus into Hermes.
3. When spawning specialists, **do not** pass a `model` argument to
   `delegate_task`. Children inherit the parent session model.

Judgment-heavy work (content/E-E-A-T, GEO, clustering, drift, SXO) still
benefits from a stronger model — pick that in Hermes (`hermes model`), not
in these files.

## Tool mapping

Skills still mention Claude Code tool names. On Hermes, use the equivalent:

| Claude Code | Hermes |
|---|---|
| Read | `read_file` |
| Write | `write_file` |
| Edit | `patch` |
| Bash | `terminal` |
| Glob / Grep | `search_files` |
| WebFetch | `web_extract` |
| WebSearch | `web_search` |
| Task (subagent) | `delegate_task` |

Page fetches must go through the bundled runtime (`url_safety.py` SSRF
guard), not a raw `requests.get` and not `web_extract` for the target URL
when the skill says to use `render_page.py` / `fetch_page.py`.

## Commands

Same surface as upstream. In Hermes chat, natural language is enough
("audit https://example.com", "schema for this page"). Slash form still
routes through the `seo` orchestrator:

| Say this | Skill |
|---|---|
| `/seo audit <url>` or "full SEO audit" | `seo-audit` |
| `/seo page <url>` | `seo-page` |
| `/seo technical <url>` | `seo-technical` |
| `/seo content <url>` | `seo-content` |
| `/seo schema <url>` | `seo-schema` |
| `/seo sitemap <url>` | `seo-sitemap` |
| `/seo geo <url>` | `seo-geo` |
| `/seo ecommerce <url>` | `seo-ecommerce` |
| `/seo setup` | `./scripts/hermes-seo setup` |
| `/seo doctor` | `./scripts/hermes-seo doctor --json` |

After install, run setup/doctor via `terminal` against the wrapper under
`$HERMES_HOME/skills/software-development/seo/scripts/hermes-seo`.

## Parallel specialists

For `/seo audit`, spawn leaf `delegate_task` children (one per specialist)
and pass the matching `agents/<name>.md` (installed at
`seo/agents/<name>.md`) as context. Do not nest further — Hermes profiles
often have `max_spawn_depth=1`. If delegation is unavailable, run the
matching `seo-*` skill inline.

Always-on audit specialists: technical, content, schema, sitemap,
performance, visual, geo, sxo. Conditional: local, maps, google,
backlinks, cluster, drift, ecommerce.

## Runtime layout

```
$HERMES_HOME/
  skills/software-development/seo/          # orchestrator + scripts + agents
  skills/software-development/seo-audit/    # ...
  runtime/claude-seo/                       # venv, Playwright, install marker
    .venv/
    hermes-install.json
```

`CLAUDE_SEO_DATA_DIR` is set by `scripts/hermes-seo`. Override it only when
you want the venv somewhere else.

API credentials stay in `~/.config/claude-seo/` (same as upstream). Hermes
does not need those files for a basic fetch/audit.

## Verification

1. `./scripts/hermes-seo doctor --json` → `"ready": true`
2. `./scripts/hermes-seo run fetch_page.py https://example.com --json` exits 0
3. A new Hermes chat lists `seo`, `seo-audit`, `seo-page`, ... as enabled
4. Asking "seo audit https://example.com" loads `seo` / `seo-audit` and
   calls the wrapper, not a guessed `pip install`

## Pitfalls

- **Current chat cannot see new skills.** Install, then `/new`.
- **Do not run `install.sh`.** That path writes `~/.claude/skills/` for
  Claude Code. Hermes uses `install-hermes.sh`.
- **Do not put `model: opus` back** when merging upstream. Re-run
  `python3 scripts/install_hermes.py --neutralize-agents`.
- **Do not write an un-prefixed launcher invocation in docs** (upstream
  layout test). Use `./scripts/hermes-seo` or `./scripts/claude-seo`.
- Playwright Chromium is optional. Setup exit code 10 means core Python
  is fine and SPA rendering is not. Raw `fetch_page.py` still works.

## Credits

Claude SEO is MIT-licensed work by [AgriciDaniel](https://github.com/AgriciDaniel)
and contributors listed in `CONTRIBUTORS.md`. Hermes adapter: Alextechgamer.
