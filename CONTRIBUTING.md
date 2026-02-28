# Contributing

感謝你有興趣貢獻 Claude Dashboard！

<br>

## 開發流程

### 分支規範

| 分支 | 用途 |
|---|---|
| `main` | 穩定版本，所有發版從此分支進行 |
| `feature/*` | 新功能開發（例如 `feature/dark-mode`） |
| `fix/*` | Bug 修復（例如 `fix/card-truncation`） |

### 提交 Pull Request

1. 從 `main` 建立功能分支
2. 完成開發後發起 PR 到 `main`
3. PR 標題簡潔描述變更內容（例如「Add dark mode support」）
4. PR 描述中說明：
   - **做了什麼**：變更摘要
   - **為什麼**：動機或對應的 Issue
   - **如何測試**：驗證方式

> **發版權限**：僅專案維護者可以打 tag 與觸發 PyPI 發佈。

<br>

## 開發環境

```bash
cd claude-code-dashboard
uv sync                         # 建立 .venv 並安裝相依套件
uv run claude-dash --plan max5  # 直接執行
```

<br>

## 新增 Agent 狀態

1. 在 `constants.py` 新增 `STATE_XXX` 常數與 `STATE_DISPLAY` 項目
2. 在 `messages.py` 為所有語系新增對應的 `state_xxx` 欄位
3. 在 `constants.py` 的 `get_state_display()` 中新增對應項目
4. 在 `sprites.py` 新增對應的像素網格（2 幀）與 `SPRITE_FRAMES` 項目
5. 在 `agent_parser.py` 的 `parse_agent_state()` 中新增判斷邏輯

<br>

## 新增工具顯示格式

1. 在 `constants.py` 的 `TOOL_DISPLAY` 字典中新增項目
2. 在 `messages.py` 為所有語系新增對應的 `tool_xxx` 欄位
3. 在 `constants.py` 的 `get_tool_display()` 中新增對應項目
4. 在 `agent_parser.py` 的 `_format_tool_status()` 中新增對應的參數萃取邏輯

<br>

## 新增語系

1. 在 `messages.py` 新增 `Messages` 實例（如 `TH = Messages(...)`）
2. 在 `messages.py` 的 `_REGISTRY` 字典中註冊新語系代碼
3. 如有 locale 別名（如 `th_TH` → `th`），在 `_ALIASES` 中新增
4. 在 `cli.py` 的 `--lang` choices 中新增語系代碼
5. 更新 `README.md` 的語系說明

<br>

## GitHub 設定（維護者）

### GitHub Secrets

Repository → Settings → **Secrets and variables** → Actions。

| Secret 名稱 | 用途 |
|---|---|
| `TEST_PYPI_API_TOKEN` | [TestPyPI](https://test.pypi.org/manage/account/#api-tokens) 的 API Token |
| `PYPI_API_TOKEN` | [PyPI](https://pypi.org/manage/account/#api-tokens) 的 API Token |

### Repository 保護規則

Repository → Settings → **Rules** → Rulesets → New ruleset。

**1. Branch 保護 (`main`)**

- **Target**:
  - Branches matching `main`
- **Bypass list**:
  - Maintain
  - Repository admin (Always allow)
- **Rules**:
  - **Require a pull request before merging**
  - **Block force pushes**
  - **Restrict deletions**

**2. Tag 保護 (`v*`)**

- **Target**:
  - Tags → Tag targeting criteria 填 `v*`
- **Bypass list**:
  - Maintain
  - Repository admin (Always allow)
- **Rules**:
  - **Restrict creations**
  - **Restrict deletions**
  - **Block force pushes**

> `workflow_dispatch`（手動觸發 Actions）預設僅 write 權限以上的人可操作，無需額外設定。

<br>

## 發佈到 PyPI

### 發版流程

所有發版操作在 `main` 分支上進行。

### 測試發佈（TestPyPI）

先透過手動觸發 GitHub Actions 發到 TestPyPI 驗證。**TestPyPI 必須使用 `rc` 後綴版號**，避免佔用正式版號（CI 會檢查）：

1. 修改 `pyproject.toml` 中的 `version` 為 rc 版號（例如 `1.1.0rc1`）
2. Commit & Push 到 `main`
   ```bash
   git commit -m "chore: bump version to 1.1.0rc1 for testing"
   git push origin main
   ```
3. 到 GitHub Actions 頁面 → "Publish to PyPI" → **Run workflow**
4. 驗證安裝
   ```bash
   pip install -i https://test.pypi.org/simple/ claude-code-dashboard==1.1.0rc1
   ```
5. 若需修正後重測，遞增 rc 號：`rc1` → `rc2` → `rc3`...

### 正式發佈（PyPI + GitHub Release）

確認 TestPyPI 沒問題後，移除 rc 後綴並打 tag 觸發正式發佈。**正式版號不可含 `rc` 後綴**（CI 會檢查）：

1. 修改 `pyproject.toml` 中的 `version` 為正式版號（例如 `1.1.0`）
2. Commit & Push 到 `main`
   ```bash
   git commit -m "release: v1.1.0"
   git push origin main
   ```
3. 打 tag 觸發 CI
   ```bash
   git tag v1.1.0
   git push origin v1.1.0
   ```
4. GitHub Actions 偵測到 `v*` tag 後自動：
   - 驗證 tag 版號與 `pyproject.toml` 一致
   - 驗證版號不含預發佈後綴
   - 發佈到 PyPI
   - 建立 GitHub Release（自動產生 release notes）

### 版本號規則（Semantic Versioning）

| 變更類型 | 版本號 | 範例 |
|---|---|---|
| Bug 修復、微調 | Patch `x.y.Z` | `1.0.0` → `1.0.1` |
| 新功能、不影響既有 API | Minor `x.Y.0` | `1.0.1` → `1.1.0` |
| 重大變更、不相容修改 | Major `X.0.0` | `1.9.0` → `2.0.0` |
| TestPyPI 測試版 | RC `x.y.zrcN` | `1.1.0rc1` → `1.1.0rc2` → `1.1.0` |

> **注意**：PyPI / TestPyPI 不允許重新上傳相同版本號。測試用 `rc` 後綴，正式發佈移除後綴。
