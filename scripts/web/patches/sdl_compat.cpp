// sdl_compat.cpp - no-op SDL1 cursor stubs (emscripten SDL1 doesn't ship impls)
#include <SDL.h>

extern "C" {

SDL_Cursor* SDL_CreateCursor(const Uint8*, const Uint8*, int, int, int, int) { return NULL; }
SDL_Cursor* SDL_GetCursor(void)                                                { return NULL; }
void        SDL_FreeCursor(SDL_Cursor*)                                        {}
void        SDL_SetCursor(SDL_Cursor*)                                         {}

}
