#include "main.h"
#include <stdbool.h>
#include <stdint.h>
#include <glib.h>

#include "libs/imgui/imgui.h"

// Lokalizace
#include "i18n.h"

#include "ui-imgui/topmenu/topmenu.h"
#if MZARCH == 700
#include "mzarch/mz700/gdg/mz700_gdg.h"
#include "hw-generic/gide/gide.h"
#include "baseui/baseui_filechooser.h"
extern "C" {
#include "baseui/baseui.h"
}
#endif

extern "C"
{
    void imgui_menu_devices(void);
}

#if MZARCH == 700
static void gide_open_cb(baseui_fchooser_t *fch) {
    if (fch->state==BASEUI_FCHOOSER_STATE_CLOSED_OK) {
        unsigned choice=GPOINTER_TO_UINT(fch->user_data);
        if (!gide_config_mount(choice&1,fch->selected_filePathName,(choice&2)!=0))
            baseui_show_error_message((char *)"GIDE: cannot open image. It must already exist and contain whole 512-byte sectors.");
    }
    baseui_filechooser_destroy(fch);
}
static void menu_gide(void) {
    if (!ImGui::BeginMenu("KC-Club GIDE")) return;
    if (ImGui::MenuItem("Card fitted",NULL,g_gide.enabled!=0)) gide_config_set_enabled(!g_gide.enabled);
    if (ImGui::BeginMenu("I/O base")) {
        for (unsigned base=0x10;base<=0xf0;base+=0x10) if (gide_base_valid(base)) {
            char title[24]; snprintf(title,sizeof(title),"%02X-%02X",base,base+15);
            if (ImGui::MenuItem(title,NULL,g_gide.base==base)) gide_set_base(base);
        }
        ImGui::EndMenu();
    }
    for (unsigned i=0;i<2;i++) {
        ImGui::PushID((int)i);
        if (ImGui::BeginMenu(i ? "Slave":"Master")) {
            gide_drive *d=&g_gide.drive[i];
            if (d->fp) {
                char *name=g_path_get_basename(d->path);
                ImGui::TextUnformatted(name); g_free(name);
                ImGui::Text("%u sectors, %s",d->blocks,d->readonly ? "read-only":"writable");
                if (ImGui::MenuItem("Eject image")) gide_config_eject(i);
            }
            for (unsigned ro=0;ro<2;ro++) {
                if (ImGui::MenuItem(ro ? "Open read-only image...":"Open writable image...")) {
                    baseui_filechooser_open_file(BASEUI_FCHOOSER_CAT_HDD,
                        ro ? "Select GIDE image (read-only)":"Select GIDE image (writable)",
                        ".img, .raw, .bin, .*",NULL,NULL,d->path,gide_open_cb,GUINT_TO_POINTER(i|(ro<<1)));
                }
            }
            ImGui::EndMenu();
        }
        ImGui::PopID();
    }
    ImGui::TextUnformatted("Raw ATA images, 512 bytes per sector. A CP/M GIDE BIOS is required.");
    ImGui::EndMenu();
}
#endif

void imgui_menu_devices(void)
{
    // Sekce Devices
    if (ImGui::BeginMenu(_L("HW & Devices")))
    {
        imgui_menu_cmt();
        imgui_menu_fdcontroller();

        imgui_menu_ramdisk();
        imgui_menu_qdisk();
        imgui_menu_unicard();
        imgui_menu_ide8();
        imgui_menu_memext();
        imgui_menu_rom();
#if MZARCH == 700
        menu_gide();
        if (ImGui::MenuItem(_L("SUC 80-column expansion"), NULL, g_gdg.suc80_enabled != 0)) {
            gdg_suc80_set_enabled(!g_gdg.suc80_enabled);
        }
        ImGui::SetItemTooltip("Optional John Edwards display. Reset selects 40 columns; software selects 80 via E00C-E00F.");
#endif

#if (MZARCH == 800) || (MZARCH == 1500)
        // Tiskárna (capture + plotter) existuje jen na architekturách se Z80 PIO
        imgui_menu_printer();
#endif

        imgui_menu_mz800_dip_switch();

#if MZARCH == 800
        ImGui::Separator();
        imgui_menu_mz800_hw_compat();
#endif

        ImGui::EndMenu();
    };
}
