/* Native Windows 7+ x64 launcher for the bundled Python 3.8 runtime.
 * Build: x86_64-w64-mingw32-gcc-win32 -Os -s -static -static-libgcc \
 *        -D_WIN32_WINNT=0x0601 -o run_parachute.exe run_parachute_launcher.c
 */
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

static int append_text(wchar_t *dst, size_t cap, const wchar_t *src) {
    size_t used = wcslen(dst), n = wcslen(src);
    if (used + n + 1 >= cap) return 0;
    wcsncpy(dst + used, src, cap - used - 1);
    dst[used + n] = L'\0';
    return 1;
}

/* Quote one argument using the CommandLineToArgvW escaping rules. */
static int append_arg(wchar_t *dst, size_t cap, const wchar_t *src) {
    if (!append_text(dst, cap, L"\"")) return 0;
    for (;;) {
        size_t slashes = 0;
        while (*src == L'\\') { slashes++; src++; }
        if (*src == L'\"') {
            for (size_t i = 0; i < 2 * slashes + 1; i++)
                if (!append_text(dst, cap, L"\\")) return 0;
            if (!append_text(dst, cap, L"\"")) return 0;
            src++;
        } else if (*src == L'\0') {
            for (size_t i = 0; i < 2 * slashes; i++)
                if (!append_text(dst, cap, L"\\")) return 0;
            break;
        } else {
            for (size_t i = 0; i < slashes; i++)
                if (!append_text(dst, cap, L"\\")) return 0;
            wchar_t ch[2] = {*src++, L'\0'};
            if (!append_text(dst, cap, ch)) return 0;
        }
    }
    return append_text(dst, cap, L"\"");
}

int wmain(int argc, wchar_t **argv) {
    wchar_t exe[32768], root[32768], runtime[32768], script[32768];
    wchar_t cmd[32768] = L"";
    if (!GetModuleFileNameW(NULL, exe, 32768)) return 2;
    wcscpy(root, exe);
    wchar_t *p = wcsrchr(root, L'\\');
    if (!p) return 2;
    *p = L'\0';                       /* ...\package\bin */
    p = wcsrchr(root, L'\\');
    if (!p) return 2;
    *p = L'\0';                       /* ...\package */
    _snwprintf(runtime, 32768, L"%s\\bin\\runtime\\python.exe", root);
    _snwprintf(script, 32768, L"%s\\src\\run_parachute.py", root);
    runtime[32767] = script[32767] = L'\0';
    if (GetFileAttributesW(runtime) == INVALID_FILE_ATTRIBUTES) {
        fwprintf(stderr, L"[run_parachute] missing runtime: %s\n", runtime);
        return 3;
    }
    if (GetFileAttributesW(script) == INVALID_FILE_ATTRIBUTES) {
        fwprintf(stderr, L"[run_parachute] missing solver: %s\n", script);
        return 4;
    }
    /* PYTHONHOME must point at the runtime, not the package root. */
    wchar_t runtime_dir[32768];
    _snwprintf(runtime_dir, 32768, L"%s\\bin\\runtime", root);
    SetEnvironmentVariableW(L"PYTHONHOME", runtime_dir);
    SetEnvironmentVariableW(L"PYTHONNOUSERSITE", L"1");
    SetEnvironmentVariableW(L"PYTHONDONTWRITEBYTECODE", L"1");
    SetEnvironmentVariableW(L"MPLBACKEND", L"Agg");
    SetCurrentDirectoryW(root);

    if (!append_arg(cmd, 32768, runtime) ||
        !append_text(cmd, 32768, L" ") ||
        !append_arg(cmd, 32768, script)) return 5;
    for (int i = 1; i < argc; i++) {
        if (!append_text(cmd, 32768, L" ") || !append_arg(cmd, 32768, argv[i]))
            return 5;
    }

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si)); si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
    si.hStdOutput = GetStdHandle(STD_OUTPUT_HANDLE);
    si.hStdError = GetStdHandle(STD_ERROR_HANDLE);
    ZeroMemory(&pi, sizeof(pi));
    if (!CreateProcessW(runtime, cmd, NULL, NULL, TRUE, 0, NULL, root, &si, &pi)) {
        fwprintf(stderr, L"[run_parachute] CreateProcess failed: %lu\n", GetLastError());
        return 6;
    }
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code = 1;
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return (int)code;
}
