/* SPDX-License-Identifier: GPL-3.0-or-later
 * Native macOS launcher: a preserved image is copied only on first use.
 * No Python, Homebrew, shell or network access is needed at runtime.
 */
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static void fail(const char *what) { perror(what); exit(1); }
static void join(char *dst, const char *a, const char *b) {
    if (snprintf(dst, PATH_MAX, "%s/%s", a, b) >= PATH_MAX) {
        errno = ENAMETOOLONG; fail("Path");
    }
}
static void makedirs(const char *path) {
    char tmp[PATH_MAX];
    if (strlen(path) >= sizeof tmp) { errno = ENAMETOOLONG; fail(path); }
    strcpy(tmp, path);
    for (char *p = tmp + 1; ; ++p) {
        if (*p == '/' || !*p) {
            char save = *p; *p = 0;
            if (mkdir(tmp, 0700) && errno != EEXIST) fail(tmp);
            struct stat st;
            if (stat(tmp, &st) || !S_ISDIR(st.st_mode)) { errno = ENOTDIR; fail(tmp); }
            *p = save;
            if (!save) break;
        }
    }
}
static void first_copy(const char *from, const char *to) {
    int out = open(to, O_WRONLY | O_CREAT | O_EXCL, 0600);
    if (out < 0) {
        if (errno == EEXIST) return;
        fail(to);
    }
    int in = open(from, O_RDONLY);
    if (in < 0) { close(out); unlink(to); fail(from); }
    char buf[65536]; ssize_t n;
    while ((n = read(in, buf, sizeof buf)) > 0) {
        ssize_t done = 0;
        while (done < n) {
            ssize_t written = write(out, buf + done, (size_t)(n - done));
            if (written <= 0) { close(in); close(out); unlink(to); fail(to); }
            done += written;
        }
    }
    if (n < 0) { close(in); close(out); unlink(to); fail(from); }
    close(in);
    if (close(out)) { unlink(to); fail(to); }
}
int main(int argc, char **argv) {
    char raw[PATH_MAX], here[PATH_MAX], resources[PATH_MAX], binary[PATH_MAX];
    char work[PATH_MAX], disk[PATH_MAX], config[PATH_MAX], source[PATH_MAX];
    char base[PATH_MAX], f000[PATH_MAX], e800[PATH_MAX];
    uint32_t size = sizeof raw;
    if (_NSGetExecutablePath(raw, &size) || !realpath(raw, here)) fail("Launcher path");
    char *slash = strrchr(here, '/'); if (!slash) return 1; *slash = 0;
    join(binary, here, "mz700emu-pal");
    join(raw, here, "../Resources");
    if (!realpath(raw, resources)) fail("Resources");
    int factory = 0, automatic = 0, readonly = 0, prepare = 0;
    const char *custom = NULL;
    char **extra = calloc((size_t)argc + 16, sizeof *extra); if (!extra) fail("calloc");
    int count = 0;
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--factory")) factory = 1;
        else if (!strcmp(argv[i], "--automatic")) automatic = 1;
        else if (!strcmp(argv[i], "--read-only")) readonly = 1;
        else if (!strcmp(argv[i], "--prepare-only")) prepare = 1;
        else if (!strcmp(argv[i], "--work-dir")) {
            if (++i == argc) { fprintf(stderr, "--work-dir requires a directory\n"); return 2; }
            custom = argv[i];
        } else extra[count++] = argv[i];
    }
    if (custom) {
        if (strlen(custom) >= sizeof work) { errno = ENAMETOOLONG; fail(custom); }
        strcpy(work, custom);
    } else {
        const char *home = getenv("HOME");
        if (!home) { fprintf(stderr, "HOME is not set\n"); return 1; }
        join(raw, home, "Library/Application Support/MZ700-ZPM3");
        join(work, raw, factory ? "factory" : "sharp-applications");
    }
    makedirs(work);
    if (!realpath(work, raw)) fail(work);
    strcpy(work, raw);
    join(disk, work, "gide.img"); join(config, work, "mz700.ini");
    join(source, resources, factory ? "system/images/keyboard-fast-factory.img" : "system/images/sharp-applications.img");
    first_copy(source, disk);
    join(base, resources, "system/roms/stock-monitor-font.bin");
    join(f000, resources, "system/roms/boot-f000.bin");
    join(e800, resources, "system/roms/boot-e800.bin");
    FILE *cfg = fopen(config, "w"); if (!cfg) fail(config);
    fprintf(cfg, "[VIDEO_MZ700]\nsuc80_enabled=1\n"
        "[ROM]\nrom_type=USER_DEFINED\nuser_defined_allinone=1\n"
        "user_defined_allinone_filepath=%s\nboot_rom_mode=%s\n"
        "boot_rom_f000_filepath=%s\nboot_rom_e800_filepath=%s\n"
        "[MEMEXT]\nconnected=1\ntype=PEHU\nfilling_on_init=NULL\n"
        "[GIDE]\nenabled=1\nbase=0xa0\nhdd0_filepath=%s\nhdd0_readonly=%d\n"
        "hdd1_filepath=\nhdd1_readonly=1\n"
        "[BREAKPOINTS]\nauto_save=0\nauto_load=0\n"
        "[DEBUGGER]\nauto_save_breakpoints=0\n",
        base, automatic ? "E800" : "F000", f000, e800, disk, readonly);
    if (ferror(cfg) || fclose(cfg)) fail(config);
    if (prepare) { printf("%s\n", config); free(extra); return 0; }
    char **cmd = calloc((size_t)count + 14, sizeof *cmd); if (!cmd) fail("calloc");
    int n = 0; cmd[n++] = binary;
    for (int i = 0; i < count; ++i) cmd[n++] = extra[i];
    cmd[n++] = "--home-dir"; cmd[n++] = resources;
    cmd[n++] = "--cfg-dir"; cmd[n++] = work;
    cmd[n++] = "--work-dir"; cmd[n++] = work;
    cmd[n++] = "--config"; cmd[n++] = config;
    cmd[n++] = "--no-first-run-windows"; cmd[n] = NULL;
    execv(binary, cmd); fail(binary); return 1;
}
