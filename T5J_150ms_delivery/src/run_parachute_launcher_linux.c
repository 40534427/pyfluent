/* Native Linux x86_64 launcher for the bundled Python 3.9 runtime.
 *
 * Layout: <package>/bin/linux-x86_64/run_parachute
 *         <package>/bin/linux-x86_64/runtime/bin/python3
 *         <package>/src/run_parachute.py
 *
 * Build (needs only glibc <= 2.17 symbols, so it runs on Kylin V10 / glibc 2.28):
 *   gcc -O2 -s -D_GNU_SOURCE -o run_parachute run_parachute_launcher_linux.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <libgen.h>

static int exists(const char *p) {
    return access(p, R_OK) == 0;
}

int main(int argc, char **argv) {
    char exe[4096];
    ssize_t n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (n <= 0) {
        if (argc < 1) return 2;
        n = (ssize_t)strlen(argv[0]);
        if (n >= (ssize_t)sizeof(exe)) return 2;
        memcpy(exe, argv[0], (size_t)n);
    }
    exe[n] = '\0';

    /* .../bin/linux-x86_64/run_parachute -> .../bin/linux-x86_64 */
    char bin[4096];
    snprintf(bin, sizeof(bin), "%s", exe);
    char *slash = strrchr(bin, '/');
    if (!slash) return 2;
    *slash = '\0';

    char root[4096];
    snprintf(root, sizeof(root), "%s", bin);
    slash = strrchr(root, '/');              /* .../bin */
    if (!slash) return 2;
    *slash = '\0';
    slash = strrchr(root, '/');              /* package root */
    if (!slash) return 2;
    *slash = '\0';

    char python[4096], script[4096];
    snprintf(python, sizeof(python), "%s/runtime/bin/python3", bin);
    snprintf(script, sizeof(script), "%s/src/run_parachute.py", root);

    if (!exists(python)) {
        fprintf(stderr, "[run_parachute] missing runtime: %s\n", python);
        return 3;
    }
    if (!exists(script)) {
        fprintf(stderr, "[run_parachute] missing script: %s\n", script);
        return 4;
    }

    char **args = (char **)calloc((size_t)argc + 2, sizeof(char *));
    if (!args) return 5;
    args[0] = python;
    args[1] = script;
    for (int i = 1; i < argc; i++) args[i + 1] = argv[i];
    args[argc + 1] = NULL;

    execv(python, args);
    perror("[run_parachute] execv");
    return 6;
}
