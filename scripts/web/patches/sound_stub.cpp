// sound_stub.cpp - no-op sound + music backend for Phase A1 emscripten spike
// Matches all APIs in sound.h; goal is link success
#include <stdint.h>
#include "sound.h"

int  soundInit(void)                                  { return 0; }
void soundDelete(void)                                {}
void soundSuspend(int)                                {}
void soundFreeResourceGroup(uint16_t)                 {}
void soundPlay(Sound, int)                            {}
void soundSpeakLine(int, int, bool)                   {}
int  soundDuration(Sound)                             { return 0; }
void soundStop()                                      {}
void soundSetVolume(int)                              {}
int  soundVolumeDec()                                 { return 0; }
int  soundVolumeInc()                                 { return 0; }

void musicPlay(int)                                   {}
void musicPlayLocale()                                {}
void musicStop()                                      {}
void musicFadeOut(int)                                {}
void musicFadeIn(int, bool)                           {}
void musicSetVolume(int)                              {}
int  musicVolumeDec()                                 { return 0; }
int  musicVolumeInc()                                 { return 0; }
bool musicToggle()                                    { return false; }
