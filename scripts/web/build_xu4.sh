#!/bin/bash
# M4: xu4 SDL emscripten build for Phase A1 spike
# Assumes: /w=build/web mount, /scripts=scripts/web mount, /data/xu4=xu4 source (ro)
#          libboron.a + boron-install/ already produced by M2 build_boron.sh
set -e

W=/w
SCRIPTS=/scripts
XU4_SRC=/data/xu4
BORON_DIR=$W/boron
XU4_BUILD=$W/xu4-build

echo "=== M4 xu4 SDL emscripten build ==="

test -f "$BORON_DIR/libboron.a" || { echo "FAIL: libboron.a missing"; exit 1; }
test -d "$XU4_SRC/src" || { echo "FAIL: xu4 src not mounted"; exit 1; }
test -d "$W/boron-install/include/boron" || { echo "FAIL: boron-install missing"; exit 1; }

rm -rf "$XU4_BUILD"
mkdir -p "$XU4_BUILD"
cp -r "$XU4_SRC"/* "$XU4_BUILD"/
cd "$XU4_BUILD"

cp "$SCRIPTS/patches/sound_stub.cpp" src/sound_stub.cpp
cp "$SCRIPTS/patches/gpu_stub.cpp" src/gpu_stub.cpp
cp "$SCRIPTS/patches/sdl_compat.cpp" src/sdl_compat.cpp

bash "$SCRIPTS/patches/apply_xu4_patches.sh" "$XU4_BUILD"

cat > make.config <<'EOF'
PREFIX=/usr/local
UI=sdl
GPU=scale
EOF

SHIM=/tmp/emshim
rm -rf "$SHIM"
mkdir -p "$SHIM"
cat > "$SHIM/cc" <<'EOF'
#!/bin/bash
exec emcc "$@"
EOF
cat > "$SHIM/gcc" <<'EOF'
#!/bin/bash
exec emcc "$@"
EOF
cat > "$SHIM/c++" <<'EOF'
#!/bin/bash
exec em++ "$@"
EOF
cat > "$SHIM/g++" <<'EOF'
#!/bin/bash
exec em++ "$@"
EOF
cat > "$SHIM/ar" <<'EOF'
#!/bin/bash
exec emar "$@"
EOF
cat > "$SHIM/ranlib" <<'EOF'
#!/bin/bash
exec emranlib "$@"
EOF
cat > "$SHIM/sdl-config" <<'EOF'
#!/bin/bash
case "$1" in
  --cflags) echo "-sUSE_SDL=1" ;;
  --libs)   echo "-sUSE_SDL=1" ;;
esac
EOF
chmod +x "$SHIM"/*
export PATH="$SHIM:$PATH"

cd src

BORON_INC=$W/boron-install/include
BORON_LIB=$W/boron-install/lib
COMMON_FLAGS="-sUSE_SDL=1 -sUSE_ZLIB=1 -sUSE_LIBPNG=1 -O2 -I$BORON_INC -DEMSCRIPTEN -DXU4_HAS_STUB_SOUND -DUSE_BORON -DCONF_MODULE -DNDEBUG -DVERSION=\\\"DR-1.0\\\""

echo "--- start make xu4 ---"
emmake make xu4.html \
    UI=sdl \
    SOUND=stub \
    CXX=em++ \
    CC=emcc \
    MAIN=xu4.html \
    UILIBS= \
    UIFLAGS="-sUSE_SDL=1 -sUSE_ZLIB=1 -sUSE_LIBPNG=1 -DUSE_BORON -DCONF_MODULE" \
    CXXFLAGS="-Wall -I. -Isupport $COMMON_FLAGS" \
    CFLAGS="-Wall -I. -Isupport $COMMON_FLAGS" \
    LIBS="$COMMON_FLAGS -L$BORON_LIB -lboron" \
    LDFLAGS="-sUSE_SDL=1 -sUSE_ZLIB=1 -sUSE_LIBPNG=1 -sALLOW_MEMORY_GROWTH=1 -sFORCE_FILESYSTEM=1" \
    2>&1 | tail -60
    UILIBS= \
    UIFLAGS="-sUSE_SDL=1 -sUSE_ZLIB=1 -sUSE_LIBPNG=1 -DUSE_BORON -DCONF_MODULE" \
    CXXFLAGS="-Wall -I. -Isupport $COMMON_FLAGS" \
    CFLAGS="-Wall -I. -Isupport $COMMON_FLAGS" \
    LIBS="$COMMON_FLAGS -L$BORON_LIB -lboron" \
    LDFLAGS="-sUSE_SDL=1 -sUSE_ZLIB=1 -sUSE_LIBPNG=1 -sALLOW_MEMORY_GROWTH=1 -sFORCE_FILESYSTEM=1" \
    2>&1 | tail -60

echo ""
echo "=== output check ==="
if [ -f xu4.html ] && [ -f xu4.js ] && [ -f xu4.wasm ]; then
    ls -la xu4.html xu4.js xu4.wasm
    echo "OK: M4 build succeeded"
else
    echo "FAIL: expected outputs missing"
    ls -la xu4.* 2>&1 || true
    exit 1
fi
