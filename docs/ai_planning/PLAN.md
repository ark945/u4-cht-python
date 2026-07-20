# u4-cht-python — 移植計畫 (PLAN)

> 立案日：2026-07-20 ・ 更新：2026-07-20（雙軌路線） ・ 維護：L.CY (anr2) + Copilot
> 上游：[`../u4-cht`](../../../u4-cht)（C++/Allegro 5 + 中文化 patches）
> 本檔遵循 `.ai_rules.md` §「文件與規劃路徑規範」。

---

## 0. TL;DR

| 問題 | 結論 |
|---|---|
| 終極目標 | **瀏覽器可玩的 U4 繁中版**，部署到 **HuggingFace Space**（Render 不適合互動遊戲，出局） |
| 路線 | **雙軌混合**：軌 A（xu4 WASM）短期上線，軌 B（Python 重寫）長期研究並行 |
| `u4-cht-python` 定位 | **兩軌共用的工具鏈** — 抽字、atlas 建置、翻譯打包、build 驅動、Space 部署 |
| 軌 A 是什麼 | 上游 xu4 C++ 用 emscripten 編 WASM，保留全部 2775 行中文化 patches + F2 跨平台美術 + YM2151 |
| 軌 B 是什麼 | 純 Python + pygame + pygbag 重寫，**強制 pygbag PoC 通過才擴展**（避免陷入無底洞） |

---

## 1. 範疇（Scope）

### 1.1 In scope

**共用工具鏈**（Phase 1–3）：
- 抽字：`.TLK` / stringtable / hardcoded / vendor Boron
- 資產建置：CJK bitmap atlas / CJK SDF (txf) / binary lookup 表
- 多平台 tileset / 音樂解碼（FM Towns / Amiga / MSX2 / X68000 / SMS）
- 統一 CLI（`u4cht <verb>`）

**軌 A（xu4 WASM）**（Phase A1–A3）：
- xu4 emscripten build 腳本（`u4cht build-web`）
- HF Static Space 打包器（HTML shell + WASM + 資料 pack）
- HF Space repo push CLI（`u4cht deploy-hf`）

**軌 B（Python 遊戲重寫）**（Phase B0 為 gate；B1+ 為延伸）：
- Phase B0：pygbag PoC — 最小可運行 pygame U4 map viewer，在瀏覽器實測 fps
- Phase B1+：**僅在 B0 通過後啟動**；否則本軌轉為 Gradio 展示館

### 1.2 Out of scope

- 修改上游 `patches/engine/*.patch` 的 C++ 邏輯（若軌 A 需微調，patch 檔改在上游 repo）
- Docker Space + noVNC 路線（每訪客一容器，免費 tier 併發會爆）
- Render 部署（產品定位不符）
- 音效 realtime 合成（軌 A：用上游 YM2151 已離線 render 的 WAV；軌 B PoC 先用 mp3/ogg）

---

## 2. 上游現況（實測 2026-07-20）

| 區塊 | 規模 | 對兩軌的意義 |
|---|---|---|
| xu4 引擎（git submodule） | ~40–60k 行 C++ + Allegro 5 + Boron VM + Faun 音訊 | **軌 A**：直接 emscripten 編；**軌 B**：作為行為 oracle 對照 |
| `patches/engine/cht-engine.patch` | 2775 行 | **軌 A**：套用後跟著編 WASM；**軌 B**：作為中文化邏輯參考，Python 重刻 |
| `tools/*.py` | 44 個 Python 檔 | 兩軌都用；本專案的 Phase 1–3 就是移植它們 |
| `assets/`（cjk_font*.bin、u4_cht.tab） | 3.6 MB | 兩軌共用；直接複用或用 build 工具重生 |
| `dumps/`（雙語 JSON） | 0.6 MB | 兩軌共用翻譯資料 |

---

## 3. 對照表：上游 tool → 本專案模組

| 上游 `../u4-cht/tools/…` | 本專案 `src/u4cht/…` | 產出 | 用於哪軌 |
|---|---|---|---|
| `extract_tlk.py` | `extract/tlk.py` | `dumps/talk_bilingual.json` | A + B |
| `extract_stringtable.py` | `extract/strings.py` | `dumps/stringtable_bilingual.json` | A + B |
| `extract_hardcoded.py` | `extract/hardcoded.py` | `dumps/hardcoded_strings.json` | A + B |
| `extract_vendor_boron.py` | `extract/vendor.py` | `dumps/vendor_bilingual.json` | A + B |
| `build_lookup.py` | `build/lookup.py` | `assets/u4_cht.tab` | **A**（B 直接 import JSON） |
| `build_cjk_font.py` | `build/cjk_font.py` | `assets/cjk_font*.bin` | **A**（B 用 pygame Font） |
| `build_cjk_txf.py` | `build/cjk_txf.py` | `assets/cfont-cjk.txf` | **A** only |
| `patch_vendor_boron.py` | `build/vendor_patch.py` | 改寫過的 `vendors.b` | **A** only |
| `render_tilesheet.py` | `build/tilesheet.py` | `docs/sprites/*.png` | A + B |
| `build_fmtowns_tileset.py` + `fmtowns/` | `platforms/fmtowns.py` | FM Towns tileset PNG + WAV | A + B |
| `build_msx2_tileset.py` + `msx2/` | `platforms/msx2.py` | MSX2 tileset + intro | A + B |
| `amiga/` | `platforms/amiga.py` | Amiga tileset + Paula 音效 | A + B |
| `x68000/` | `platforms/x68000.py` | X68000 tileset + YM2151 MGD | A + B |
| `sms/` | `platforms/sms.py` | SMS tileset | A + B |
| `apply_cht.sh` | `cli:apply` | 對 xu4 source 套 patch + 複製 assets | **A** only |
| — | `web/emscripten.py` + `cli:build-web` | xu4 WASM build orchestration | **A** only（新增） |
| — | `web/hf_space.py` + `cli:deploy-hf` | HF Space repo 打包 + push | **A** only（新增） |
| — | `game/*` | Python 重寫的遊戲主體 | **B** only（僅 Phase B0 PoC） |

---

## 4. 分階段交付

### Phase 0：骨架 + 規劃 ✅ 完成

- [x] `pyproject.toml`（hatchling、Python 3.10+）
- [x] `src/u4cht/` 空 package + CLI + tests
- [x] `README.md`、`docs/ai_planning/PLAN.md`（本檔）
- [ ] GitHub Actions（lint + pytest）— 併入 Phase 1

**Pass**：`u4cht info` 印版本、`pytest` 3 綠燈 ✅

---

### Phase 1：共用抽字管線（兩軌都需要）

從最有代表性、無外部依賴的 extractor 開始：

1. `extract/tlk.py` — 讀 16 個 DOS `.TLK`，輸出 256 NPC × 12 欄 JSON
2. `extract/strings.py` — `u4read_stringtable` 演算法（`title.exe` + `avatar.exe`）
3. `extract/hardcoded.py` — 靜態分析 xu4 `src/*.cpp` 內 `screenMessage()` 系列字面
4. `extract/vendor.py` — Boron `vendors.b` tokenizer + 字串抽取

**Pass/Fail loop**：每個 extractor 產出的 JSON 的 `en` 欄位與上游 `../u4-cht/dumps/*_bilingual.json` **完全一致**（sha256 golden test）。

**副產品**：GitHub Actions（ubuntu + windows + macOS matrix，pytest + ruff）。

---

### Phase 2：共用資產打包

1. `build/lookup.py` — 合併四源 JSON → binary length-prefixed table，sha256 match `assets/u4_cht.tab`
2. `build/cjk_font.py` — Pillow + freetype-py 從 TTF 烘 16×16 灰階 atlas，sha256 match 三份 `cjk_font*.bin`
3. `build/cjk_txf.py` — SDF atlas（`msdf-atlas-gen` binary driver）

**Pass/Fail loop**：對上游三份 atlas 逐 byte 比對；lookup 表 sha256 match。

---

### Phase 3：共用多平台 tileset 解碼

依難度排序：`fmtowns` → `msx2` → `amiga` → `x68000` → `sms`（SMS 需 libretro headless，另立子任務）。

**Pass/Fail loop**：產出 PNG 與上游 `assets/sprites/` 或 `docs/sprites/` 對應圖像 pixel-perfect match。

---

### 【軌 A】Phase A1：xu4 emscripten build spike ★ 決定性 ✅ 完成 2026-07-20

**目的**：驗證 xu4 + Boron VM 能不能 emscripten build 起來。**這是整個軌 A 的門檻**。

**實際路線**（與原計畫的差異）：
- 上游 `data/xu4/` 是 SDL 1.2 版本（不是 Allegro 5），所以走 `-sUSE_SDL=1` emscripten SDL1 emulation
- Boron VM 用 `0branch/boron.git` v2.0.8（Dockerfile.zh 記的 `wickedsmoke/boron` URL 錯誤已修）
- Faun 音訊：走 D2 (a) stub 路線；`sound_stub.cpp` no-op 全 15 隻 API
- GPU 也走 stub 路線；`gpu_stub.cpp` no-op 全 `gpu.h` API（`gpu_opengl.cpp` 48KB 需 WebGL2 整合，留給 A2）

**五個里程碑**（全通）：
| M | 內容 | 產出 |
|---|---|---|
| M1 | emscripten toolchain 驗證 | hello-world 15KB WASM |
| M2 | Boron VM emscripten build | `libboron.a` 286KB WASM object |
| M3 | 音訊 stub | `sound_stub.cpp`（15 隻 no-op） |
| M4 | xu4 SDL backend + link | `xu4.html` 19KB + `xu4.js` 122KB + `xu4.wasm` 674KB |
| M5 | 瀏覽器實跑 | `main()` 執行、印出 xu4 原生「need U4 data」訊息 |

**產出**：
- `scripts/web/build_boron.sh` — Boron WASM build + install layout
- `scripts/web/build_xu4.sh` — xu4 SDL emmake + PATH shim orchestration
- `scripts/web/patches/{sound,gpu}_stub.cpp` + `sdl_compat.cpp` + `apply_xu4_patches.sh`
- `docs/ai_planning/A1-notes.md`（session log + 決策 + 陷阱）

**Pass 判準達成**：M5 印出 xu4 原生 filesystem error → WASM 完整 load、`main()` 執行、Boron/SDL1/gpu/sound 全 runtime 起。畫面尚未渲染（gpu stub），需 A2 接 WebGL2。

**未觸發任何 kill switch**。技術路徑成立。

---

### 【軌 A】Phase A2：HF Static Space 打包 + 部署

**任務**：
1. `src/u4cht/web/hf_space.py` — 從 A1 產出生 HF Space 目錄結構（`app.html` + `xu4.wasm` + `xu4.js` + `data.pack` + `README.md` YAML front matter）
2. 遊戲資料下載策略：
   - **選項 (i)**：build 時把 freeware `.zip` 抓下並包進 `data.pack`（Space 直接可玩，但要注意授權宣告）
   - **選項 (ii)**：Space 第一次載入時從瀏覽器 fetch freeware URL（`ultima.thatfleminggent.com`），存 IndexedDB
3. 存檔透過 emscripten IDBFS → 瀏覽器 IndexedDB
4. `u4cht deploy-hf` — 用 `huggingface_hub` API push 到 `hf` remote
5. 依 `.ai_rules.md` DoD：commit 完自動 `git push hf HEAD`

**Pass**：HF 上一個公開 Space URL，任何人開瀏覽器即可玩繁中 U4 至少到主選單。

---

### 【軌 A】Phase A3：整合微調

- `F2` 跨平台美術切換在瀏覽器裡驗證
- 三套 CJK 字型切換（原本 env variable，可能要改成 URL query 或 in-game menu）
- YM2151 招魂 WAV 播放（Web Audio API）
- Mobile browser 相容性（touch input mapping）

---

### 【軌 B】Phase B0：pygbag PoC ★ Gate（強制）

**目的**：實測 pygame + pygbag 在瀏覽器裡跑 U4 那種格局的即時遊戲是否可行。**不通過就砍軌 B**。

**PoC 內容**（最小可行）：
1. 用 `../u4-cht/assets/tileset.png` 畫一張 20×20 Britannia 地圖區塊
2. 鍵盤方向鍵移動 `@` 圖示
3. 播放一段 YM2151 招魂 WAV（測 audio latency）
4. 螢幕角落顯示 fps
5. `pip install pygbag` → `pygbag src/u4cht/game/poc_main.py` → 產出 WASM
6. Push 到臨時 HF Space，實機測（Chrome / Firefox / mobile Safari）

**Pass 條件**（全部要達成）：
- Desktop Chrome ≥ 55 fps 穩定
- Mobile Safari ≥ 30 fps
- 鍵盤 latency < 100ms（touch input 可更寬鬆）
- Audio 可正常播、無明顯延遲
- WASM bundle ≤ 15 MB（不含遊戲資料）

**Fail 應變**：軌 B 永久暫停；`src/u4cht/game/` 保留為 Gradio 展示館（NPC 瀏覽器 + tileset viewer + 字型對比），仍走 HF Gradio Space 但**不是遊戲**。

**產出**：`docs/ai_planning/B0-pygbag-poc.md`（實測 fps / latency 數據）。

---

### 【軌 B】Phase B1+：完整 Python 遊戲重寫（僅在 B0 通過後）

**若 B0 通過**，長期並行實作：
- B1：主選單 + 角色創建（8 塔羅牌問答 → 決定職業）
- B2：Britannia 世界地圖 + 移動 + 對話系統（讀 `dumps/talk_bilingual.json`）
- B3：戰鬥系統
- B4：dungeon 3D 渲染
- B5：完整遊戲循環（存檔、真言、聖壇）

這是**幾百-幾千小時工程**，不定期推進，不設 deadline。

---

### Phase 6（如 B0 fail）：Gradio 展示館替代交付

- NPC 對話瀏覽器（搜尋 256 個 NPC、EN/ZH 並列）
- 跨平台 tileset F2 viewer（EGA / VGA / FM Towns / Amiga / MSX2 / X68000 / SMS）
- 三套 CJK 字型 render 對比
- YM2151 招魂 WAV 試聽
- 上傳 `.TLK` → 即時抽字 demo

**Pass**：HF Gradio Space 公開網址可訪。

---

## 5. 相依性與資產策略

### 5.1 相依 `../u4-cht`

Phase 1–3 + 軌 A 需要以下路徑存在：

```
../u4-cht/dumps/*.json         # golden 對照
../u4-cht/assets/*.bin         # golden 對照
../u4-cht/patches/engine/*     # 軌 A build 用
../u4-cht/xu4/                 # 軌 A emscripten build 目標（submodule）
```

### 5.2 遊戲原始資料

**不入庫**（版權）。策略：
- 開發：本機 `data/ultima4/`（`.gitignore`）
- 軌 A HF Space：build 時抓 freeware zip，或 runtime IDBFS fetch
- 軌 B HF Space：與 A 相同策略

### 5.3 assets/ 內容策略

- **允許入庫**：小型 sha256 對照檔、字型子集清單（TXT）
- **不入庫**：`.bin` atlas、`.tab` lookup、`.wasm`（可 rebuild）

---

## 6. Open decisions（待確認）

| # | 決策點 | 選項 | 狀態 |
|---|---|---|---|
| ~~D1~~ | ~~是否重寫 xu4 引擎為 Python~~ | ~~yes/no~~ | ✅ **已決**：走雙軌，B 為 gated 長期研究 |
| ~~D2~~ | ~~軌 A Faun 音訊子系統 emscripten 支援未知~~ | ~~(a) stub / (b) 一次做完~~ | ✅ **已決** (A1)：走 (a) stub；`sound_stub.cpp` 完整 no-op |
| **D3** | 軌 A HF Space 遊戲資料策略 | (i) build 時打包 / (ii) runtime IDBFS fetch | 依 freeware 條款，Phase A2 決 |
| ~~D4~~ | ~~若 Allegro 5 emscripten 卡死是否轉 SDL2 fork~~ | ~~(a) 轉 / (b) 砍 A~~ | ✅ **已決** (A1)：上游本就是 SDL 1.2，用 `-sUSE_SDL=1` emu 直接編通，不需轉 |
| **D5** | 軌 B PoC 通過門檻（fps / latency）鬆緊 | 目前定 55/30 fps；可微調 | Phase B0 前確認 |
| **D6** | Mobile browser 支援優先度 | (a) desktop-only ship 先 / (b) 同步 mobile | 建議 (a) |

---

## 7. 風險與待決 (RAID)

| # | 風險 | 等級 | 影響軌 | 處置 |
|---|---|---|---|---|
| ~~R1~~ | ~~xu4 沒有 emscripten build 先例~~ | ~~🔴~~ | A | ✅ **關閉** (A1)：xu4 SDL 版能編、load、run |
| ~~R2~~ | ~~Allegro 5 emscripten 支援品質不確定~~ | ~~🟠~~ | A | ✅ **關閉** (A1)：上游用 SDL 1.2，走 `-sUSE_SDL=1` emu |
| ~~R3~~ | ~~Boron VM emcc 相容性~~ | ~~🟡~~ | A | ✅ **關閉** (A1)：`0branch/boron` 純 C，configure 關掉 socket/exec 就編通 |
| ~~R4~~ | ~~Faun 音訊 emscripten backend~~ | ~~🟡~~ | A | ✅ **關閉** (A1)：走 stub 路線 |
| R2b | `gpu_opengl.cpp` 需接 WebGL2 / GLES3 | 🟠 | A | **A2 主任務**；A1 已用 stub 驗證 link 通 |
| R5 | pygbag 效能不足以跑 U4 即時遊戲 | 🟠 | B | Phase B0 gate；不過就砍 |
| R6 | HF Space free tier 對 WASM bundle size 限制 | 🟡 | A + B | 現實約 5GB repo，10 MB WASM 綽綽有餘 |
| R7 | 遊戲原始資料版權處理 | 🟠 | A + B | D3 決定策略，宣告寫在 Space README |
| R8 | Mobile browser 相容（尤其 iOS Safari） | 🟠 | A + B | D6：先 desktop，mobile 後補 |

---

## 8. 立即下一步（A1 完成後更新 2026-07-20）

**已完成**：Phase 0 + Phase 1 (fetch-data) + Phase A1 全五個 M ✅

**下一步兩條路可挑**（等使用者決）：

**路 α：續攻軌 A → Phase A2**（推薦；順著 A1 momentum）
1. **A2-M1** Preload freeware U4 → `--preload-file ultima4@/ultima4`，讓 xu4 過 filesystem check
2. **A2-M2** 接 `gpu_opengl.cpp` + `-sMIN_WEBGL_VERSION=2 -sFULL_ES3=1`，看到 xu4 標題畫面
3. **A2-M3** 中文字型 patch 上瀏覽器（`assets/cjk_font*.bin` preload + xu4 render 路徑）
4. **A2-M4** HF Static Space 打包 + `u4cht deploy-hf` CLI

**路 β：回頭補 Phase 1 抽字管線**（穩健派；為軌 A + B 都準備好資料）
1. `extract/tlk.py` — 讀 `.TLK` → JSON、golden 對照
2. `extract/strings.py` — u4read_stringtable 演算法
3. `extract/hardcoded.py` + `extract/vendor.py`
4. GitHub Actions matrix

**混合建議**：先跑 A2-M1（半天，把 data 打進 wasm），驗證 xu4 至少能過 title screen（就算 gpu stub 只黑螢幕，也能看 stdout 印字），再回 Phase 1。

---

依 `.ai_rules.md` DoD：`OK / 完成 / 可以推了` → `git add . && git commit && git push origin HEAD`

---

## 附錄 A：路線決策記錄

- 2026-07-20 立案時原假設純 tools 現代化；使用者提出「HF/Render 部署」需求
- 分析：Render 產品定位不符（web service / cron，非互動遊戲）→ 排除
- 分析：pygbag（Python 全重寫）風險高、效能未知 → 不獨走
- 分析：xu4 WASM 保留全部上游中文化成果，emscripten build 是最短路徑 → 定為主線
- 使用者拍板：**混合路線 C** — A 主 B 副，B 以 pygbag PoC 為 gate
