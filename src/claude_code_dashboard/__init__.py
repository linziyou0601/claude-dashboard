"""Claude Dashboard — Claude Code 終端儀表板套件。

整合 Token 用量監控（透過 claude-monitor）與 Agent 狀態監控（像素精靈動畫），
提供即時的終端介面，方便同時掌握多個 Claude Code 工作階段的狀態。
"""

from importlib.metadata import version as _version

__version__: str = _version("claude-code-dashboard")
