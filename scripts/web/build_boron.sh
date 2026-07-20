#!/bin/bash
# Boron VM emscripten build for xu4-cht-python Phase A1 spike
# 在 emscripten/emsdk:latest 容器內執行；假設 cwd = /w
# Host 端呼叫：
#   docker run --rm -v "${PWD}/build/web:/w" -v "${PWD}/scripts/web:/scripts" \
#              -w /w emscripten/emsdk:latest bash /scripts/build_boron.sh
set -e

BORON_URL="https://github.com/0branch/boron.git"
BORON_DIR="/w/boron"

# 1. Clone (idempotent)
if [ ! -d "$BORON_DIR" ]; then
    git clone --depth 1 "$BORON_URL" "$BORON_DIR"
fi
cd "$BORON_DIR"
make clean 2>/dev/null || true
rm -f config.opt libboron.a

# 2. 用 PATH shim 把 cc/ar/ranlib 全部指向 emscripten toolchain
#    emcc 是 Python 腳本會自我定位路徑，不能用 symlink，要用 exec 包一層
SHIM="/tmp/emshim"
mkdir -p "$SHIM"
cat > "$SHIM/cc" <<'EOF'
#!/bin/bash
exec emcc "$@"
EOF
cat > "$SHIM/gcc" <<'EOF'
#!/bin/bash
exec emcc "$@"
EOF
cat > "$SHIM/ar" <<'EOF'
#!/bin/bash
exec emar "$@"
EOF
cat > "$SHIM/ranlib" <<'EOF'
#!/bin/bash
exec emranlib "$@"
EOF
chmod +x "$SHIM"/*
export PATH="$SHIM:$PATH"

# 3. Configure：關掉所有瀏覽器不需要 / 帶麻煩依賴的功能
./configure \
    --no-execute \
    --no-readline \
    --no-socket \
    --no-checksum \
    --no-compress \
    --static

# 4. Build 只需要 libboron.a
make libboron.a

# 5. 驗證產出的 .o 是 WASM 不是 ELF
ar x libboron.a env.o
magic_hex=$(od -An -tx1 -N 4 env.o | tr -d ' \n')
echo "env.o magic: $magic_hex"
if [ "$magic_hex" = "0061736d" ]; then
    echo "OK: libboron.a 是 WASM object (magic 0x00 'asm')"
elif echo "$magic_hex" | grep -qi "^7f454c46$"; then
    echo "FAIL: 產出是 native ELF, 不是 WASM"
    exit 1
else
    echo "WARN: 不確定格式 (magic=$magic_hex)，繼續但需人工檢查"
fi
rm env.o

echo ""
echo "=== 產出 ==="
ls -la libboron.a
