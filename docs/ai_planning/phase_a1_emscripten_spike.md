# Phase A1 — xu4 emscripten Spike

> 立案日：2026-07-20 ・ 維護：L.CY (anr2) + Copilot
> 上游 PLAN 對照：[PLAN.md §Phase A1](./PLAN.md#軌-aphase-a1xu4-emscripten-build-spike--決定性)
> 狀態：**未啟動**

---

## 0. TL;DR

| 項目 | 決定 |
|---|---|
| 目的 | 用最少的力氣證明：xu4 能不能編成 WASM 在瀏覽器裡動 |
| 目標畫面 | **瀏覽器裡看到 xu4 標題畫面 + 主選單能鍵盤操作**（僅此，不打字幕、不掛翻譯） |
| Backend 選擇 | **SDL2**（不用 Allegro 5）— xu4 已有 `screen_sdl.cpp` + `event_sdl.cpp`；emscripten `-sUSE_SDL=2` 是官方 port |
| 音訊 | **全部 stub 掉** — Faun/OpenAL emscripten 太複雜，A1 只看畫面 |
| Boron VM | 純 C，用 `emcc` 直接編（風險低） |
| 資料 | 用 IDBFS + `--preload-file` 打包 `ultima4.zip` 內容 + `vendors.b` |
| 產出物 | `dist/xu4-web/` 目錄（`xu4.html` + `xu4.js` + `xu4.wasm` + `xu4.data`）+ 實測筆記 |
| Kill switch | 見 §5 — 任一硬阻塞條件觸發即終止 A1，走 §6 應變 |

---

## 1. 為什麼是 SDL 不是 Allegro

上游 PLAN 原本假設編 Allegro 5，但真讀了 xu4 src 之後：

```
data/xu4/src/screen_sdl.cpp       ← SDL2 renderer
data/xu4/src/event_sdl.cpp        ← SDL2 event pump
data/xu4/src/screen_allegro.cpp   ← Allegro 5 renderer（不用）
data/xu4/src/screen_glfw.cpp      ← GLFW（桌面 only）
data/xu4/src/screen_glv.cpp       ← GLV
```

xu4 是「多 backend」引擎，configure 時選。SDL2 已經在 tree 裡，就選它。

| 面向 | Allegro 5 emscripten | SDL2 emscripten |
|---|---|---|
| 官方支援 | 5.1+，需自行 emcmake build | **一等公民**，`-sUSE_SDL=2` 一鍵引入 |
| 社群案例 | 稀少 | 海量（幾乎每個 emscripten 遊戲教學都用它） |
| Faun / OpenAL 綁定 | Allegro 內建 audio | SDL_mixer / SDL2 audio 都有 emscripten port |
| xu4 上游中文化 patch 依賴 | patch 有動 renderer 嗎？→ **A1 前需確認** | 同左 |

**待驗證項 A1-V1**：`../u4-cht/patches/engine/cht-engine.patch` 內有沒有 backend-specific 的修改。若只改 `screen.cpp` / `text.cpp` 這種抽象層，SDL 路線可承接 patch；若改到 `screen_allegro.cpp` 深處，就要移植成 SDL 版。

---

## 2. Scope（僅此，多做算多）

### In scope（A1 定義的成功）

1. `emcc` 能編過 `libboron.a`
2. `emcc` 能編過 xu4 sources 用 SDL backend
3. 產出 `.wasm` + `.js` + `.data` 三檔套組
4. `python -m http.server` serve 起來，Chrome 打開能看到：
   - xu4 標題畫面（"Ultima IV — Quest of the Avatar"）
   - 按方向鍵 + Enter 進主選單
   - 不 crash（跑 30 秒不 corrupt）
5. **不需要**：中文字、實際遊戲進行、音訊、mobile、touch input、正確的 fps

### Out of scope

- 音訊（Faun / OpenAL）— 全 stub `-DFAUN_STUB` 或改 `sound.cpp` 空函式
- 網路 / IDBFS 儲存 — Phase A2 事
- 翻譯 JSON 掛入 — Phase A2 事
- HF Space 部署 — Phase A2 事
- Touch input / mobile — Phase A3 事
- YM2151 / X68000 音樂 — Phase A3 事

---

## 3. 前置補洞（先解決 fetch-data 的漏斗）

目前 `bootstrap/fetch_data.py` 的 tarball filter 只留 `.cpp/.c/.h/.hpp/.b/.txt/.md`，把 **`configure` / `Makefile` / `src/Makefile`** 全濾掉了。A1 build 時需要它們。

**任務 A1-P0（1 hop）**：
- `fetch_data.py:_extract_xu4_tarball` 的 `KEEP_SUFFIXES` 加上：
  - 顯式白名單檔名：`configure`, `Makefile`, `mkdefs.mk`, `xcode-project.mk`
  - 副檔名 `.mk`, `.pri`, `.qbs`, `.pro`
- 更新測試 `test_bootstrap_fetch_data.py:_make_synthetic_xu4_tarball` 加一個 `configure` 檔驗證有進來
- **不改** golden 邏輯

---

## 4. 分步驟里程碑（每步都有 pass/fail gate）

### M1 — 環境驗證（半天內）

**動作**
```bash
# 安裝 emsdk（如果 host 沒有）
git clone https://github.com/emscripten-core/emsdk.git ~/emsdk
cd ~/emsdk && ./emsdk install latest && ./emsdk activate latest
source ./emsdk_env.sh  # or emsdk_env.bat on Windows

# 驗證
emcc --version
```

**Pass**：`emcc` 印版本 ≥ 3.1.50
**Fail**：改用 docker image `emscripten/emsdk:latest`（避免 host 環境問題）

**產出**：`docs/ai_planning/A1-notes.md`（新檔，記實測環境）

---

### M2 — Boron VM 獨立 build

xu4 依賴 Boron；先確認 Boron 能編。

**動作**
```bash
cd data/xu4/src/../support  # 假設 boron 在 src 或 support
# 或若 boron 是外部：git clone https://github.com/wickedsmoke/boron.git
emcc -c boron/*.c -o boron.o -O2 -sSTRICT
emar rcs libboron.a boron.o
```

**Pass**：`libboron.a` 產出
**Fail 場景**：
- boron 用 POSIX-only API（`mmap`, `fork`）→ 檢查 `#ifdef __EMSCRIPTEN__` 需求，寫 patch
- 依賴 GNU-only inline asm → 較嚴重，可能要 fork boron

**產出**：`build/web/libboron.a`；如需 patch，寫入 `patches/boron-emscripten.patch`

---

### M3 — Faun 音訊 stub

**動作**：
- 新增 `patches/xu4-audio-stub.patch`：把 `sound_faun.cpp` 全部函式 body 換成空 `{ /* stub */ }`（保留簽名，不改 header）
- 或加 `-DXU4_NO_AUDIO` 在 build flags，需 xu4 `sound.h` 支援；若不支援，加一個 `#ifdef` 分支

**Pass**：`sound_faun.o` 用 emcc 編過
**Fail**：Faun 內部有其他 sources 也被 include → 加更寬的 stub

---

### M4 — xu4 主 build（SDL backend + emscripten）

**動作**
```bash
cd data/xu4
# xu4 用手寫 configure；不吃 --host，但吃 CC 環境變數
emconfigure ./configure --sdl --no-audio
emmake make -C src \
    CXXFLAGS="-O2 -sUSE_SDL=2 -DEMSCRIPTEN" \
    LDFLAGS="-sUSE_SDL=2 -sALLOW_MEMORY_GROWTH=1 -sFETCH=1 \
             --preload-file ../../../data/tlk@/tlk \
             --preload-file ../../../data/dos@/dos \
             --preload-file ../../../data/xu4/module@/module \
             -o xu4.html"
```

**Pass**：產出 `xu4.wasm` + `xu4.js` + `xu4.html` + `xu4.data`（四檔缺一不可）
**Fail 場景（按預期出現機率排序）**：

| # | 症狀 | 應變 |
|---|---|---|
| F1 | `error: undefined symbol: al_*`（Allegro 沒剃乾淨） | 檢查 `configure --sdl` 有沒有真的把 Allegro 排除；找 xu4 Makefile 的 SRC_ALLEGRO 變數確認 |
| F2 | Boron 呼叫的 `mmap` / `dlopen` 找不到 | 加 `-sERROR_ON_UNDEFINED_SYMBOLS=0` 先過，之後補 stub |
| F3 | SDL 版 xu4 缺 `screen_sdl.cpp` include | 檢查 sdl backend 是不是完整（歷史上有 fork 移除過 SDL） |
| F4 | `configure` script 用 bash-only 語法在 Windows 掛 | 走 M1 fail 應變的 docker |

**產出**：`dist/xu4-web/xu4.*`

---

### M5 — 瀏覽器實跑（最終 gate）

**動作**
```bash
cd dist/xu4-web
python -m http.server 8000
# 開 http://localhost:8000/xu4.html
```

**Pass 條件（全 3 條，缺一不可）**：
1. Chrome DevTools console 沒有 red error
2. 畫面出現 xu4 標題（可能是 EGA 醜圖，OK）
3. 鍵盤方向鍵能移動、Enter 能進主選單

**Fail 應變**：見 §5

**產出**：截圖 → `docs/ai_planning/A1-screenshots/*.png`；筆記寫入 `A1-notes.md`

---

## 5. Kill Switch（硬阻塞就退）

若下列**任一**條件觸發，A1 立即停止，改走 §6：

| 觸發條件 | 意義 |
|---|---|
| M2 Boron 需要改超過 200 行才能編 | Boron VM 與 emscripten 不相容度過高 |
| M4 xu4 SDL backend 不完整（缺檔或 stub 太多） | xu4 SDL 支援已 rot，走 Allegro 更遠 |
| M5 標題畫面出得來但每動一下就 crash | 記憶體模型 / threading 深層問題，非 spike 能解 |
| **累積實作時間 > 5 個 focus session** | 就是走不通，別再撞了 |

---

## 6. Fail 應變（決策樹）

```
M2 fail  ────→  改用 xu4 fork 已剝 Boron 的版本？搜 github "xu4 no-boron"
              └── 沒有 → 跳到 F-B
M3 fail  ────→  Faun 剃不掉 → 找 xu4 更早版本（audio 是後加的）
              └── 沒有 → 跳到 F-B
M4 fail  ────→  SDL backend rot → 評估 Allegro 5 emscripten 路線（複雜度 3x）
              └── 不做 → 跳到 F-B
M5 fail  ────→  crash 反覆 → 跳到 F-B

F-B: 砍軌 A，全力走軌 B（pygbag PoC）。
     u4-cht-python 產品定位改為「翻譯工具鏈 + Gradio 展示館」。
```

---

## 7. 驗收清單（Definition of Done for A1）

- [ ] `patches/xu4-audio-stub.patch` 或等效 `-DXU4_NO_AUDIO` 已 wire 進 build
- [ ] `patches/boron-emscripten.patch`（如需要）
- [ ] `src/u4cht/web/emscripten.py`（build driver，orchestrate M2–M4）
- [ ] `u4cht build-web` CLI subcommand
- [ ] `dist/xu4-web/xu4.{html,js,wasm,data}` 全出檔
- [ ] `docs/ai_planning/A1-notes.md` 實測記錄 + 至少 1 張標題畫面截圖
- [ ] `pytest` 全綠（不含 A1 新測試也 OK；A1 的 tests 是 shell / manual）
- [ ] 決策：軌 A **可行 / 不可行**（寫在 `A1-notes.md` 末尾）

---

## 8. 完成後的 handoff（給 Phase A2）

A1 通過即滿足 A2 的所有前置：
- 有 build driver → A2 加 `--preload-file` 換成翻譯過的 assets
- 有 stubbed audio → A2 可選擇補回或維持 stub
- 有瀏覽器主選單 → A2 加中文字型 + 掛翻譯 JSON

---

## 9. 待決 Open Questions（阻擋啟動）

| # | 問題 | 誰決 | 影響 |
|---|---|---|---|
| Q1 | 上游 patch 有沒有動 Allegro-specific 檔？ | AI grep 一下就知 | 決定 SDL 路線能否直接承接 patch |
| Q2 | 開發平台：Windows 直跑 emsdk 還是走 WSL / docker？ | USER | 影響 M1 步驟 |
| Q3 | Boron VM 是 submodule 還是 xu4 vendored？ | AI 看 tree 確認 | 決定 M2 build 順序 |

**Q1 先解**（不用 USER 介入，我 grep 就知）
**Q2 需 USER 回答**
**Q3 我看一眼 tree 就知**

---

## 10. 立即下一步

1. **[AI]** 解 §9 Q1（grep patch）+ Q3（看 xu4 tree）
2. **[AI]** 補 §3 fetch-data 白名單（不影響已抓資料）
3. **[USER]** 回 §9 Q2（Windows 直跑 / WSL / docker）
4. **[AI]** 進 M1 環境驗證
