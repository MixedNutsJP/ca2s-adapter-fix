// Proxy dxgi.dll that fixes an off-by-one in Capcom Arcade 2nd Stadium.
//
// The game stores EnumAdapters results in IDXGIAdapter* adapters[4], but the loop
// bound lets it write adapters[4], which is the stack cookie. With four or more
// adapters the game dies with 0xc0000409 at startup.
//
// The exe is unpacked at startup, so the fix is applied in memory: `cmp ebx, 4`
// becomes `cmp ebx, 3`. The buggy function calls CreateDXGIFactory1 right before
// the loop, through this DLL, so applying the fix from the factory exports always
// happens first. DllMain is too early, because the code is not unpacked yet.

#include <windows.h>

#include <cstdarg>
#include <cstdio>
#include <cwchar>

namespace {

// Target build: exe 1.0.0.4, Steam build 15647585.
constexpr wchar_t kGameExeName[] = L"CapcomArcade2ndStadium.exe";
constexpr DWORD kExpectedSizeOfImage = 0xA051000;
constexpr DWORD kPatchRva = 0x25E82B0;
constexpr SIZE_T kPatchLength = 5;
constexpr BYTE kOriginalBytes[kPatchLength] = {0x83, 0xFB, 0x04, 0x73, 0x22};  // cmp ebx,4 / jae
constexpr BYTE kPatchedBytes[kPatchLength] = {0x83, 0xFB, 0x03, 0x73, 0x22};   // cmp ebx,3 / jae
constexpr SIZE_T kImmediateOffset = 2;

constexpr int kMaxMismatchLogs = 16;

struct ExportEntry {
    const char* name;
    bool appliesFix;
};

// Index is ordinal - 1. Keep in the same order as dxgi.def and stubs.asm.
constexpr ExportEntry kExports[] = {
    {"ApplyCompatResolutionQuirking", false},
    {"CompatString", false},
    {"CompatValue", false},
    {"DXGIDumpJournal", false},
    {"PIXBeginCapture", false},
    {"PIXEndCapture", false},
    {"PIXGetCaptureState", false},
    {"SetAppCompatStringPointer", false},
    {"UpdateHMDEmulationStatus", false},
    {"CreateDXGIFactory", true},
    {"CreateDXGIFactory1", true},
    {"CreateDXGIFactory2", true},
    {"DXGID3D10CreateDevice", false},
    {"DXGID3D10CreateLayeredDevice", false},
    {"DXGID3D10GetLayeredDeviceSize", false},
    {"DXGID3D10RegisterLayers", false},
    {"DXGIDeclareAdapterRemovalSupport", false},
    {"DXGIDisableVBlankVirtualization", false},
    {"DXGIGetDebugInterface1", false},
    {"DXGIReportAdapterConfiguration", false},
};
constexpr unsigned kExportCount = sizeof(kExports) / sizeof(kExports[0]);

HMODULE g_self = nullptr;
bool g_isGame = false;  // Set once in DllMain. CrashReport.exe shares this folder.

SRWLOCK g_resolveLock = SRWLOCK_INIT;
HMODULE g_realDxgi = nullptr;
void* volatile g_realExports[kExportCount] = {};

SRWLOCK g_fixLock = SRWLOCK_INIT;
volatile LONG g_fixFinished = 0;  // No further attempt can change the outcome.
int g_mismatchLogs = 0;

wchar_t g_logPath[MAX_PATH + 32] = {};
SRWLOCK g_logLock = SRWLOCK_INIT;

void Log(const char* format, ...) {
    if (g_logPath[0] == L'\0') {
        return;
    }

    char text[512];
    SYSTEMTIME now;
    GetLocalTime(&now);
    int length = snprintf(text, sizeof(text), "%02u:%02u:%02u.%03u ", now.wHour, now.wMinute,
                          now.wSecond, now.wMilliseconds);

    va_list args;
    va_start(args, format);
    int body = vsnprintf(text + length, sizeof(text) - length - 2, format, args);
    va_end(args);
    if (body < 0) {
        return;
    }
    length += body;
    if (length > static_cast<int>(sizeof(text)) - 3) {
        length = static_cast<int>(sizeof(text)) - 3;
    }
    text[length++] = '\r';
    text[length++] = '\n';

    AcquireSRWLockExclusive(&g_logLock);
    HANDLE file = CreateFileW(g_logPath, FILE_APPEND_DATA, FILE_SHARE_READ, nullptr, OPEN_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file != INVALID_HANDLE_VALUE) {
        DWORD written = 0;
        WriteFile(file, text, static_cast<DWORD>(length), &written, nullptr);
        CloseHandle(file);
    }
    ReleaseSRWLockExclusive(&g_logLock);
}

void InitLog() {
    wchar_t path[MAX_PATH];
    DWORD length = GetModuleFileNameW(g_self, path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) {
        return;
    }
    wchar_t* slash = wcsrchr(path, L'\\');
    if (slash == nullptr) {
        return;
    }
    slash[1] = L'\0';
    swprintf_s(g_logPath, L"%sca2s-adapter-fix.log", path);

    // Start each run with a fresh log.
    HANDLE file = CreateFileW(g_logPath, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file != INVALID_HANDLE_VALUE) {
        CloseHandle(file);
    }
}

bool IsGameProcess() {
    wchar_t path[MAX_PATH];
    DWORD length = GetModuleFileNameW(nullptr, path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) {
        return false;
    }
    const wchar_t* slash = wcsrchr(path, L'\\');
    return _wcsicmp(slash != nullptr ? slash + 1 : path, kGameExeName) == 0;
}

bool IsReadable(const void* address, SIZE_T size) {
    MEMORY_BASIC_INFORMATION info;
    if (VirtualQuery(address, &info, sizeof(info)) == 0) {
        return false;
    }
    if (info.State != MEM_COMMIT || (info.Protect & (PAGE_NOACCESS | PAGE_GUARD)) != 0) {
        return false;
    }
    const BYTE* end = static_cast<const BYTE*>(info.BaseAddress) + info.RegionSize;
    return static_cast<const BYTE*>(address) + size <= end;
}

DWORD GetImageSize(const BYTE* base) {
    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        return 0;
    }
    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) {
        return 0;
    }
    return nt->OptionalHeader.SizeOfImage;
}

// Returns true when the fix is finished, one way or the other. Returns false when the
// bytes do not match yet, which is what an early call before unpacking looks like.
bool TryApplyFix() {
    BYTE* base = reinterpret_cast<BYTE*>(GetModuleHandleW(nullptr));
    const DWORD imageSize = GetImageSize(base);
    if (imageSize != kExpectedSizeOfImage) {
        Log("SKIP: SizeOfImage is 0x%lX, expected 0x%lX. Unsupported game version.", imageSize,
            kExpectedSizeOfImage);
        return true;
    }

    BYTE* target = base + kPatchRva;
    if (!IsReadable(target, kPatchLength)) {
        Log("WAIT: target at %p is not readable yet.", target);
        return false;
    }

    if (memcmp(target, kPatchedBytes, kPatchLength) == 0) {
        Log("OK: already patched at %p.", target);
        return true;
    }
    if (memcmp(target, kOriginalBytes, kPatchLength) != 0) {
        if (g_mismatchLogs < kMaxMismatchLogs) {
            ++g_mismatchLogs;
            Log("WAIT: bytes at %p are %02X %02X %02X %02X %02X, not the expected code.", target,
                target[0], target[1], target[2], target[3], target[4]);
        }
        return false;
    }

    BYTE* immediate = target + kImmediateOffset;
    DWORD oldProtect = 0;
    if (!VirtualProtect(immediate, 1, PAGE_EXECUTE_READWRITE, &oldProtect)) {
        Log("FAIL: VirtualProtect error %lu.", GetLastError());
        return true;
    }
    *immediate = kPatchedBytes[kImmediateOffset];
    DWORD restored = 0;
    const BOOL protectRestored = VirtualProtect(immediate, 1, oldProtect, &restored);
    FlushInstructionCache(GetCurrentProcess(), immediate, 1);

    Log("OK: patched %p (base %p + 0x%lX), cmp ebx,4 -> cmp ebx,3, old protect 0x%lX%s.", immediate,
        base, kPatchRva + static_cast<DWORD>(kImmediateOffset), oldProtect,
        protectRestored ? "" : ", restoring protection FAILED");
    return true;
}

void ApplyFixOnce() {
    if (!g_isGame || InterlockedCompareExchange(&g_fixFinished, 0, 0) != 0) {
        return;
    }
    AcquireSRWLockExclusive(&g_fixLock);
    if (g_fixFinished == 0 && TryApplyFix()) {
        InterlockedExchange(&g_fixFinished, 1);
    }
    ReleaseSRWLockExclusive(&g_fixLock);
}

bool LoadRealDxgi() {
    wchar_t path[MAX_PATH];
    const UINT length = GetSystemDirectoryW(path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH - 10) {
        Log("FAIL: GetSystemDirectory error %lu.", GetLastError());
        return false;
    }
    wcscat_s(path, L"\\dxgi.dll");  // A bare name would load this DLL again.

    g_realDxgi = LoadLibraryW(path);
    if (g_realDxgi == nullptr) {
        Log("FAIL: could not load the system dxgi.dll, error %lu.", GetLastError());
        return false;
    }
    Log("Loaded the system dxgi.dll at %p.", g_realDxgi);
    return true;
}

void* ResolveReal(unsigned index) {
    void* cached = InterlockedCompareExchangePointer(
        const_cast<void**>(&g_realExports[index]), nullptr, nullptr);
    if (cached != nullptr) {
        return cached;
    }

    void* resolved = nullptr;
    AcquireSRWLockExclusive(&g_resolveLock);
    if (g_realDxgi != nullptr || LoadRealDxgi()) {
        resolved = reinterpret_cast<void*>(GetProcAddress(g_realDxgi, kExports[index].name));
        if (resolved != nullptr) {
            InterlockedExchangePointer(const_cast<void**>(&g_realExports[index]), resolved);
        } else {
            Log("FAIL: the system dxgi.dll does not export %s.", kExports[index].name);
        }
    }
    ReleaseSRWLockExclusive(&g_resolveLock);
    return resolved;
}

HRESULT WINAPI ReportUnavailable() {
    return E_FAIL;
}

}  // namespace

extern "C" void* proxy_resolve(unsigned index) {
    if (index >= kExportCount) {
        return reinterpret_cast<void*>(&ReportUnavailable);
    }
    if (kExports[index].appliesFix) {
        ApplyFixOnce();
    }
    void* real = ResolveReal(index);
    return real != nullptr ? real : reinterpret_cast<void*>(&ReportUnavailable);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        g_self = instance;
        g_isGame = IsGameProcess();
        if (g_isGame) {
            InitLog();
            Log("Attached to %ls.", kGameExeName);
        }
    }
    return TRUE;
}
