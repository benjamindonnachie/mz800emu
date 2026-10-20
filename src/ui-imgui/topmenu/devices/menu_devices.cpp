#include "main.h"
#include <stdbool.h>
#include <stdint.h>
#include <glib.h>

#include "libs/imgui/imgui.h"

// Lokalizace
#include "i18n.h"

#include "ui-imgui/topmenu/topmenu.h"
#if MZARCH == 700
#include "hw-generic/pcg700/pcg700.h"
#include "mzarch/mz700/gdg/mz700_framebuffer.h"
#endif

extern "C"
{
    void imgui_menu_devices(void);
}

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
        if (ImGui::BeginMenu("HAL PCG-700")) {
            if (ImGui::MenuItem("Card fitted", NULL, g_pcg700.fitted != 0)) {
                g_pcg700.fitted = !g_pcg700.fitted;
                g_framebuffer.screen_changes = SCRSTS_THIS_IS_CHANGED;
            }
            if (ImGui::MenuItem("HSW: PCG display", NULL, g_pcg700.hsw != 0)) {
                g_pcg700.hsw = !g_pcg700.hsw;
                g_framebuffer.screen_changes = SCRSTS_THIS_IS_CHANGED;
            }
            ImGui::EndMenu();
        }
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
