# Changelog

## [1.0.3] - 2026-03-01

### Bug Fixes

- Fixed **Burn Rate** displaying an inflated instantaneous value instead of a smoothed rate
  - **Root cause:** used `tokensPerMinute` from the API (total block tokens ÷ block duration), which spikes to unrealistically high values at the start of a new billing block
  - **Fix:** now uses `calculate_hourly_burn_rate()` (tokens over the past hour), matching the rate shown in the ccm UI; falls back to the block average only when no hourly data is available

- Fixed **Token Exhaustion** time showing the billing reset time instead of the actual depletion estimate
  - **Root cause:** `projection.remainingMinutes` from the API represents time until the billing block ends, not time until tokens/cost run out
  - **Fix:** exhaustion time is now derived from `(cost_limit − current_cost) / cost_per_minute`, the same formula used internally by ccm; the field is hidden when depletion would not occur before the next reset

## [1.0.2] - 2026-03-01

### Improvements

- **Agent state detection is now significantly more accurate**
  - Use `turn_duration` system events as a reliable "turn ended" signal for the **Waiting Input** state, replacing the previous timeout-only heuristic
  - Detect `bash_progress` / `mcp_progress` / `agent_progress` events to prevent long-running tools from being misclassified as **Waiting Permission**
  - Added `Agent`, `Task`, and `AskUserQuestion` to the exempt-tools list so sub-agent calls and user prompts are no longer misidentified as permission requests
  - Increased the fallback input-wait threshold from 5 s to 10 s to reduce false **Waiting Input** transitions during streaming responses

## [1.0.1] - 2026-03-01

### Bug Fixes

- Fixed `--version` displaying an incorrect version number (`0.1.0`)
  - **Root cause:** version string was hardcoded in `__init__.py` and not kept in sync with `pyproject.toml`
  - **Fix:** version is now read dynamically via `importlib.metadata`; `pyproject.toml` is the single source of truth

## [1.0.0] - 2026-02-28

### Features

**Dual-Panel TUI Dashboard**
- Displays token usage and agent status side by side in a single terminal view
- Screen refreshes at 2 Hz; data is polled at a configurable interval

**Token Usage Panel**
- Real-time progress bars for **Cost**, **Tokens**, and **Messages** relative to plan limits
- **Model distribution** stacked bar (Opus / Sonnet / Haiku)
- **Burn Rate**, **Cost Rate**, **Reset Countdown**, and **Exhaustion Time** estimates
- Warning indicator when usage exceeds plan limits
- Two switchable themes: `default` (custom progress bars + responsive two-column layout) and `ccm` (original claude-monitor UI)
- Supports `pro`, `max5`, `max20`, and `custom` plan tiers

**Agent Status Panel**
- Automatically scans all active Claude Code sessions under `~/.claude/projects/`
- Five agent states with distinct visual indicators:
  - ✍ **Working** — executing tasks with tools
  - 🧠 **Thinking** — generating a response or reasoning
  - ⏳ **Permission** — waiting for user tool approval
  - 💬 **Input** — waiting for user input
  - 💤 **Idle** — no recent activity
- Tool activity labels: read, edit, write, execute, search, sub-agent, web fetch, todo update
- Multi-session support with automatic numbering within the same project (#1, #2, …)

**Pixel Sprite Animation**
- 14×12 pixel grid rendered via Unicode Braille characters (2×4 dot matrix per character)
- 7-color palette; 2-frame animation per state, alternating at 0.5-second intervals
- No image protocol required (Sixel / Kitty / iTerm2) — plain Unicode text output
- Disable with `--no-sprites` for screen readers or low-resolution terminals

**Internationalization (i18n)**
- 5 languages: English, Traditional Chinese, Simplified Chinese, Japanese, Korean
- Auto-detects system locale via `LC_ALL` / `LANG` / `locale.getlocale()`
- Override with `--lang`

**Cross-Terminal Compatibility**
- Pure Unicode text output — works in VS Code integrated terminal, iTerm2, and Terminal.app
- Supports macOS, Linux, and Windows

---

### Installation

Requires Python 3.9+. The [claude-monitor](https://pypi.org/project/claude-monitor/) dependency is installed automatically.

```bash
# Recommended: install as a global CLI tool with uv
uv tool install claude-code-dashboard

# Or with pip
pip install claude-code-dashboard
```

### Usage

```bash
# Quick start (both commands are equivalent)
claude-dash --plan max5
ccd --plan max5

# Agent panel only
ccd --view agents

# Token panel only
ccd --view tokens
```

### CLI Options

| Option | Default | Description |
|---|---|---|
| `--plan` | `max5` | Plan tier: `pro` / `max5` / `max20` / `custom` |
| `--timezone` | `Asia/Taipei` | IANA timezone name |
| `--view` | `all` | Panel to show: `all` / `tokens` / `agents` |
| `--refresh` | `10` | Data refresh interval in seconds |
| `--idle-timeout` | `10` | Hide agents idle for more than N minutes |
| `--max-agents` | `0` | Max agent cards to display (0 = unlimited) |
| `--show-all` | `false` | Show all sessions active within the last 30 minutes |
| `--no-sprites` | `false` | Disable pixel sprites; use plain text mode |
| `--token-theme` | `default` | Token panel theme: `default` / `ccm` |
| `--time-format` | `24h` | Time format: `24h` / `12h` |
| `--lang` | `auto` | UI language: `auto` / `en` / `zh_TW` / `zh_CN` / `ja` / `ko` |
| `--version` | — | Print version number |

### Acknowledgements

This project builds on the following open-source work:

- **[claude-monitor (ccm)](https://github.com/Maciek-roboblog/Claude-Code-Usage-Monitor)** — the token usage panel calls ccm's API directly (MIT License)
- **[Pixel Agents](https://github.com/pablodelucca/pixel-agents)** — inspiration for agent state detection logic and pixel sprite concept (MIT License)

[1.0.3]: https://github.com/linziyou0601/claude-code-dashboard/releases/tag/v1.0.3
[1.0.2]: https://github.com/linziyou0601/claude-code-dashboard/releases/tag/v1.0.2
[1.0.1]: https://github.com/linziyou0601/claude-code-dashboard/releases/tag/v1.0.1
[1.0.0]: https://github.com/linziyou0601/claude-code-dashboard/releases/tag/v1.0.0
