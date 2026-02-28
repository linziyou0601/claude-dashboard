"""模組入口點 — 支援 ``python -m claude_dashboard`` 方式啟動。

當使用者透過 ``python -m claude_dashboard`` 或 ``uv run python -m claude_dashboard``
執行時，Python 會自動載入此檔案並呼叫 :func:`cli.main`。
"""

from claude_dashboard.cli import main

main()
