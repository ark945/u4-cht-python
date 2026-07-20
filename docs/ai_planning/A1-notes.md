# Phase A1 — 實測筆記

> 對照計畫書：[phase_a1_emscripten_spike.md](./phase_a1_emscripten_spike.md)
> 環境：Windows 11 + Docker Desktop (WSL2 backend) + `emscripten/emsdk:latest`

---

## Session log

### 2026-07-20 — M1 環境驗證 ✅

**工具鏈**
- Docker Desktop 28.3.2，WSL2 backend，16 CPU、11.39 GB RAM
- `emscripten/emsdk:latest` (image ID `bb0910e6a18b`, 3.18 GB, 6 天前)
- `emcc` 6.0.3 (`283e2d130132859fde6a4e4c87fd254b38127651`)

**Hello-world spike**
```bash
docker run --rm -v "${PWD}:/src" -w /src/build/web \
    emscripten/emsdk:latest \
    emcc m1_hello.c -o m1_hello.html
```

產出：
| 檔案 | 大小 |
|---|---|
| `build/web/m1_hello.wasm` | 15,147 B |
| `build/web/m1_hello.js` | 76,829 B |
| `build/web/m1_hello.html` | 21,963 B |

**M1 Pass**：docker + emcc toolchain 通、能 build 出四檔套組（除了 `.data`，因為 no preload）。

**注意**
- Windows PowerShell 對 stderr warning（`WARNING: DOCKER_INSECURE_NO_IPTABLES_RAW is set`）會誤報 exit code 1。實際 daemon 正常。日後 build script 用 `*>` redirect + 檢 exit code 才準。
- 掛 volume 用 `-v "${PWD}:/src"`（PowerShell 語法），container 內以 Linux 路徑操作。

---

## 待跑

- [x] M1 環境驗證
- [x] M2 Boron VM emscripten build
- [ ] M3 Faun / 音訊 stub
- [ ] M4 xu4 SDL backend + emscripten link
- [ ] M5 瀏覽器實跑

## 決策記錄

- **Boron repo URL 修正**：Dockerfile.zh 寫的 `wickedsmoke/boron.git` 是**過時 / 錯誤** URL（GitHub 404）。正解是 `0branch/boron.git`（Rebol-like scripting language，Sourceforge 官方鏡像）。日後所有 build 腳本用此 URL。
- **Boron Makefile 用 `cc` 硬編碼**（不用 `$(CC)`），`emmake` 沒用；解法：PATH shim `/tmp/emshim/{cc,gcc,ar,ranlib}` 用 bash exec wrapper 包 `emcc/emar/emranlib`（**不能用 symlink** — emcc 是 Python 腳本會自我定位）。
- **Boron configure flags for browser**：`--no-execute --no-readline --no-socket --no-checksum --no-compress --static`。移掉的功能對 xu4 遊戲邏輯應該沒影響（存檔用 Boron，socket/execute 都不需要），但 A1 過關後要驗證 xu4 game.cpp 不呼叫這些。
- 未觸發任何 kill switch。

## Session log

### 2026-07-20 — M2 Boron VM emscripten build ✅

**腳本**：`scripts/web/build_boron.sh`（idempotent，可反覆跑）

**Host 端呼叫**
```bash
docker run --rm \
    -v "${PWD}/build/web:/w" \
    -v "${PWD}/scripts/web:/scripts" \
    -w /w emscripten/emsdk:latest \
    bash /scripts/build_boron.sh
```

**流程**
1. `git clone --depth 1 https://github.com/0branch/boron.git` (v2.0.8)
2. PATH shim: `cc/gcc/ar/ranlib` → 各自 exec `emcc/emar/emranlib`
3. `./configure --no-{execute,readline,socket,checksum,compress} --static`
4. `make libboron.a`
5. 驗證 `env.o` magic bytes = `0x00 61 73 6d` (`\0asm`) → **WASM object ✅**

**產出**：`build/web/boron/libboron.a` = 286 KB（native x86 版是 436 KB — 縮小是因為 emcc `-O3` + 少了 zlib/socket 分支）

**編譯警告**（非致命）：`eval/random.c:30` `_clockSeed()` 沒 prototype — pedantic mode 抱怨，C23 相容問題。忽略。

**M2 Pass**：Boron 全樹能編成 WASM，`libboron.a` 準備好給 M4 xu4 link。

