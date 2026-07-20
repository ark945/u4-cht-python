# u4-cht-python

> 姊妹專案 [`u4-cht`](../u4-cht) 的 **Python 分支**。
> 最終目標：**讓 U4 繁中版在瀏覽器裡玩到**（HF Spaces 部署）。
> 走「雙軌混合」路線 — 短期 xu4 WASM 快速上線、長期 Python 重寫作為研究用備援。

## 目標

**HF Space 上一個網址，點進去就能玩繁中版 Ultima IV**，`F2` 切美術、三套 CJK 字型、YM2151 招魂配樂全在瀏覽器裡跑。

## 雙軌路線

### 軌 A：xu4 → WASM（短期主線）

- **遊戲本體** = 上游 `u4-cht` 的 C++/xu4/Allegro 5，用 **emscripten** 編成 WASM
- 保留全部上游成果：2775 行中文化 patches、跨平台美術、字型切換、YM2151 音樂
- `u4-cht-python` 在此軌的角色 = **資產管線 + emscripten build 驅動 + HF Space 部署 CLI**
- 部署為 **HF Static Space**（純靜態檔案，載入即玩）

### 軌 B：純 Python 重寫（長期研究）

- 用 **pygame** 重寫遊戲，透過 **pygbag** 打包成 WASM
- **強制門檻**：先做 pygbag PoC（map render + input + audio）在瀏覽器實測 fps；PoC 不過就不繼續 Phase B1+
- 通過後才擴展至完整遊戲循環；未通過則本軌永久暫停，只留 Gradio 展示館作為 Python 側交付

兩軌**共用**：`dumps/*.json` 翻譯、`assets/*.bin` 字型 atlas、`u4-cht-python` 的抽字/打包工具。

## 現況

**Phase 0（骨架 + 規劃）✅ 完成**

- `pyproject.toml` / `src/u4cht/` package / `tests/` / CLI (`u4cht info`)
- `pytest` 3 綠燈；`u4cht --version` 可用

所有規劃、決策、Phase 細節請見 [docs/ai_planning/PLAN.md](docs/ai_planning/PLAN.md)。

## 快速開始

```powershell
python -m pip install -e ".[dev]"
pytest
u4cht info
```

## 目錄結構

```
u4-cht-python/
├── docs/ai_planning/    # 規劃文件（依 .ai_rules.md §文件路徑規範）
│   └── PLAN.md          # 雙軌計畫、Phase 拆解、open decisions
├── src/u4cht/           # Python package
│   ├── extract/         # 抽字工具（tlk / strings / hardcoded / vendor）
│   ├── build/           # 資產打包（cjk_font / cjk_txf / lookup）
│   ├── platforms/       # 多平台 tileset 解碼（fmtowns / amiga / msx2 / x68000 / sms）
│   ├── web/             # [軌 A] emscripten build + HF Space 打包
│   ├── game/            # [軌 B] 純 Python 遊戲重寫（gated by pygbag PoC）
│   └── cli.py           # 統一 CLI
├── tests/
└── pyproject.toml
```

## 授權 / 資產

- 程式碼：沿用上游 `u4-cht` 授權（GPL-2.0-or-later）
- 遊戲原始資料（`AVATAR.EXE` / `.TLK` / `.ULT`）：Origin/EA freeware，**不隨本專案散布**
- 部署到 HF Space 時，遊戲資料透過使用者自備或 freeware URL 下載
