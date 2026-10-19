/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "main.h"
#if MZARCH == 700
#include "gide.h"
#include "cfgmain.h"
#include "replay.h"
#include <glib.h>
#include "libs/sdlapp/sdlapp_paths.h"
static char *image[2];
static unsigned readonly[2];
void gide_init(void) {
    CFGMOD *m=cfgroot_register_new_module(g_cfgmain,"GIDE");
    CFGELM *e=cfgmodule_register_new_element(m,"enabled",CFGENTYPE_BOOL,0);
    cfgelement_set_handlers(e,&g_gide.enabled,&g_gide.enabled);
    e=cfgmodule_register_new_element(m,"base",CFGENTYPE_UNSIGNED,160,0,240);
    cfgelement_set_handlers(e,&g_gide.base,&g_gide.base);
    for (unsigned i=0;i<2;i++) {
        char key[32];
        g_snprintf(key,sizeof(key),"hdd%u_filepath",i);
        e=cfgmodule_register_new_element(m,key,CFGENTYPE_TEXT,"");
        cfgelement_set_pointers(e,&image[i],&image[i]);
        g_snprintf(key,sizeof(key),"hdd%u_readonly",i);
        e=cfgmodule_register_new_element(m,key,CFGENTYPE_BOOL,1);
        cfgelement_set_handlers(e,&readonly[i],&readonly[i]);
    }
    cfgmodule_parse(m); cfgmodule_propagate(m);
    if (!gide_base_valid(g_gide.base)) {
        fprintf(stderr,"GIDE: conflicting or invalid base %02X; card disabled (base reset to A0)\n",g_gide.base);
        g_gide.enabled=0; g_gide.base=0xa0;
    }
    gide_rtc_init();
    gide_config_set_enabled(g_gide.enabled!=0);
}
void gide_config_set_enabled(bool enabled) {
    if (replay_is_active()) return;
    /* Do not open writable media for a disabled card. Refit reopens saved paths. */
    if (enabled) for (unsigned i=0;i<2;i++) if (!g_gide.drive[i].fp && image[i] && *image[i]) {
        char *path=sdlapp_paths_resolve_cfg(g_sdlapp->paths,image[i]);
        if (!gide_mount(i,path,readonly[i])) fprintf(stderr,"GIDE: cannot open valid 512-byte-sector image '%s'\n",path);
        g_free(path);
    }
    gide_set_enabled(enabled);
}
bool gide_config_mount(unsigned id, const char *path, bool ro) {
    if (replay_is_active()) return false;
    if (!gide_mount(id,path,ro)) return false;
    g_free(image[id]); image[id]=g_strdup(g_gide.drive[id].path); readonly[id]=ro;
    return true;
}
void gide_config_eject(unsigned id) {
    if (replay_is_active()) return;
    if (id>1) return;
    gide_eject(id); g_free(image[id]); image[id]=g_strdup("");
}
void gide_exit(void) {
    for (unsigned i=0;i<2;i++) { gide_eject(i); g_free(image[i]); image[i]=NULL; }
}
#endif
