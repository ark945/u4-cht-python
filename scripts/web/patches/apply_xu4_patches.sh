#!/bin/bash
# apply_xu4_patches.sh - patch xu4 upstream code drift for emscripten SDL1 build
# Called by build_xu4.sh with $1 = xu4-build root
set -e
cd "$1"

echo "--- apply xu4 code-rot patches ---"

# 1. screen_sdl.cpp: settings->gameTitle(buf) doesn't exist in this xu4 version
if grep -q "settings->gameTitle(buf)" src/screen_sdl.cpp; then
    sed -i 's|SDL_WM_SetCaption(settings->gameTitle(buf), NULL);|SDL_WM_SetCaption("xu4", NULL);|g' src/screen_sdl.cpp
    echo "  [OK] screen_sdl.cpp: gameTitle stubbed"
fi

# 2. gpu_opengl.cpp is 48KB and needs full GL3 context — use gpu_stub.cpp instead
#    (A1 spike goal is link+load, not rendering)
if ! grep -q "gpu_stub.cpp" src/Makefile.common; then
    sed -i 's|xu4.cpp \\|xu4.cpp \\\n        gpu_stub.cpp \\\n        sdl_compat.cpp \\|' src/Makefile.common
    echo "  [OK] Makefile.common: gpu_stub.cpp + sdl_compat.cpp added"
fi

echo "--- patches done ---"
