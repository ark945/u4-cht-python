"""[軌 B] 純 Python 遊戲重寫（gated by Phase B0 pygbag PoC）。

Phase B0 內容：
- `poc_main.py` — 最小可行 pygame U4：20×20 tileset map + 鍵盤移動 + YM2151 WAV
- 目標：pygbag 打包 → 部署臨時 HF Space → 實測 fps/latency

Pass 條件（見 PLAN §4 Phase B0）：
- Desktop Chrome ≥ 55 fps
- Mobile Safari ≥ 30 fps
- Keyboard latency < 100ms
- Audio 可播無明顯延遲
- WASM bundle ≤ 15 MB

Fail 應變：本軌永久暫停，`game/` 轉為 Gradio 展示館基底。
"""
