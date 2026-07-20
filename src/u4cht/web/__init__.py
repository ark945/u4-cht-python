"""[軌 A] xu4 → WASM 建置與 HF Space 部署（尚未實作）。

計畫子模組：

- `emscripten` — xu4 + Allegro 5 + Boron 用 emcc build 成 WASM
  對應 Phase A1；產出 `xu4.wasm` + `xu4.js` + HTML shell
- `hf_space`   — 從 build 產物打包成 HF Static Space 目錄結構 + push
  對應 Phase A2；提供 `u4cht deploy-hf` CLI

啟用條件：Phase A1 spike 通過（`docs/ai_planning/PLAN.md` §4 軌 A）。
"""
