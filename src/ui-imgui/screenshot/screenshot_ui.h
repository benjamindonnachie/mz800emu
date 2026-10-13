/**
 * @file   screenshot_ui.h
 * @brief  Screenshot z GUI: menu Tools -> Screenshot, zkratka Alt+F, dialog nastavení.
 *
 * Ukládá PNG obrazu, který okno emulátoru právě zobrazuje
 * (iface_sdl3_video_get_screen_surface()), s oblastí a měřítkem podle
 * g_screenshot_settings (INI `[SCREENSHOT]`, viz screenshot_config.h).
 *
 * @par Vlákna
 * Všechny funkce jen z UI vlákna.
 *
 * @par Licence: GPLv3
 */

#ifndef SCREENSHOT_UI_H
#define SCREENSHOT_UI_H

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Uloží screenshot do výstupního adresáře pod jménem podle času.
 *
 * Výsledek ohlásí notifikací (cesta a rozměr, nebo chyba).
 */
void screenshot_ui_save_quick(void);

/** @brief Otevře dialog pro uložení screenshotu do zvoleného souboru. */
void screenshot_ui_save_as(void);

/** @brief Podmenu "Screenshot" v menu Tools (uložit, uložit jako, nastavení, složka). */
void imgui_screenshot_menu(void);

/** @brief Zkratka Alt+F (uložit screenshot); volá se v Alt větvi globálních zkratek. */
void imgui_screenshot_shortcuts(void);

/**
 * @brief Dialog nastavení screenshotu (zobrazí se při g_gui->showScreenshotSetupWindow).
 *
 * Edituje kopii nastavení, OK ji zapíše do g_screenshot_settings (uloží se
 * do INI při ukončení emulátoru), Cancel ji zahodí.
 */
void imgui_screenshot_setup_dialog(void);

#ifdef __cplusplus
}
#endif

#endif /* SCREENSHOT_UI_H */
