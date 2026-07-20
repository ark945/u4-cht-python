// gpu_stub.cpp - no-op GPU backend for Phase A1 emscripten spike
// All rendering functions return safe defaults; goal is link success + wasm load
#include <stdlib.h>
#include <string.h>
#include "image32.h"
#include "gpu.h"

WorkBuffer* gpu_allocWorkBuffer(const int* regionSizes, int regionCount) {
    WorkBuffer* w = (WorkBuffer*)calloc(1, sizeof(WorkBuffer));
    w->regionCount = (uint16_t)regionCount;
    return w;
}
void        gpu_freeWorkBuffer(WorkBuffer* w) { free(w); }
float*      gpu_beginRegion(WorkBuffer*, int) { static float dummy[1]; return dummy; }
void        gpu_endRegion(WorkBuffer*, int, float*) {}

const char* gpu_init(void*, int, int, int, int) { return NULL; }
void     gpu_free(void*) {}
void     gpu_viewport(int, int, int, int) {}
uint32_t gpu_makeTexture(const Image32*) { return 0; }
void     gpu_blitTexture(uint32_t, int, int, const Image32*) {}
void     gpu_freeTexture(uint32_t) {}
uint32_t gpu_screenTexture(void*) { return 0; }
void     gpu_setTilesTexture(void*, uint32_t, uint32_t, float) {}
void     gpu_drawTextureScaled(void*, uint32_t) {}
void     gpu_clear(void*, const float*) {}
void     gpu_invertColors(void*) {}
void     gpu_setScissor(int*) {}
void     gpu_updateWorkBuffer(void*, int, WorkBuffer*) {}
void     gpu_drawTrisRegion(void*, int, const WorkRegion*) {}
float*   gpu_beginTris(void*, int) { static float dummy[1]; return dummy; }
void     gpu_endTris(void*, int, float*) {}
void     gpu_clearTris(void*, int) {}
void     gpu_drawTris(void*, int) {}
void     gpu_enableGui(void*, int, int) {}
void     gpu_drawGui(void*, int, int, int) {}
void     gpu_guiClutUV(void*, float*, float) {}
void     gpu_guiSetOrigin(void*, float, float) {}
float*   gpu_emitQuad(float* attr, const float*, const float*) { return attr; }
float*   gpu_emitQuadPq(float* attr, const float*, const float*, float, float) { return attr; }
void     gpu_resetMap(void*, const Map*) {}
void     gpu_drawMap(void*, const TileView*, const float*, const BlockingGroups*, int, int, float) {}
