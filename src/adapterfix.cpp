// Capcom Arcade 2nd Stadium — Adapter Fix (MixedNuts\Mods\adapterfix\adapterfix.dll)
// Created by MixedNuts - https://github.com/MixedNutsJP/ca2s-adapter-fix
// Licensed under the MIT License. See LICENSE for details.
//
// The game stores EnumAdapters results in IDXGIAdapter* adapters[4], but the loop
// bound lets it write adapters[4], which is the stack cookie. With four or more
// adapters the game dies with 0xc0000409 at startup.
//
// The exe is unpacked at startup, so the fix is applied in memory: `cmp ebx, 4`
// becomes `cmp ebx, 3`. The buggy function calls CreateDXGIFactory1 right before
// the loop, so the loader's factory hook always runs first.

#include <windows.h>

#include <cstring>

#include <mixednuts/log.hpp>
#include <mixednuts/plugin.h>

namespace {

using mixednuts::log::Write;

constexpr char kVersion[] = "1.1.0";

// Target build: exe 1.0.0.4, Steam build 15647585.
constexpr DWORD kExpectedSizeOfImage = 0xA051000;
constexpr DWORD kPatchRva = 0x25E82B0;
constexpr SIZE_T kPatchLength = 5;
constexpr BYTE kOriginalBytes[kPatchLength] = {0x83, 0xFB, 0x04, 0x73, 0x22};  // cmp ebx,4 / jae
constexpr BYTE kPatchedBytes[kPatchLength] = {0x83, 0xFB, 0x03, 0x73, 0x22};   // cmp ebx,3 / jae
constexpr SIZE_T kImmediateOffset = 2;

constexpr int kMaxMismatchLogs = 16;

bool g_finished = false;  // Hooks run one at a time, so no lock is needed.
int g_mismatchLogs = 0;

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
// bytes do not match yet, which is what a call before unpacking looks like.
bool TryApplyFix() {
    BYTE* base = reinterpret_cast<BYTE*>(GetModuleHandleW(nullptr));
    const DWORD imageSize = GetImageSize(base);
    if (imageSize != kExpectedSizeOfImage) {
        Write("SKIP: SizeOfImage is 0x%lX, expected 0x%lX. Unsupported game version.", imageSize,
              kExpectedSizeOfImage);
        return true;
    }

    BYTE* target = base + kPatchRva;
    if (!IsReadable(target, kPatchLength)) {
        Write("WAIT: target at %p is not readable yet.", target);
        return false;
    }
    if (memcmp(target, kPatchedBytes, kPatchLength) == 0) {
        Write("OK: already patched at %p.", target);
        return true;
    }
    if (memcmp(target, kOriginalBytes, kPatchLength) != 0) {
        if (g_mismatchLogs < kMaxMismatchLogs) {
            ++g_mismatchLogs;
            Write("WAIT: bytes at %p are %02X %02X %02X %02X %02X, not the expected code.", target,
                  target[0], target[1], target[2], target[3], target[4]);
        }
        return false;
    }

    BYTE* immediate = target + kImmediateOffset;
    DWORD oldProtect = 0;
    if (!VirtualProtect(immediate, 1, PAGE_EXECUTE_READWRITE, &oldProtect)) {
        Write("FAIL: VirtualProtect error %lu.", GetLastError());
        return true;
    }
    *immediate = kPatchedBytes[kImmediateOffset];
    DWORD restored = 0;
    const BOOL protectRestored = VirtualProtect(immediate, 1, oldProtect, &restored);
    FlushInstructionCache(GetCurrentProcess(), immediate, 1);

    Write("OK: patched %p (base %p + 0x%lX), cmp ebx,4 -> cmp ebx,3, old protect 0x%lX%s.",
          immediate, base, kPatchRva + static_cast<DWORD>(kImmediateOffset), oldProtect,
          protectRestored ? "" : ", restoring protection FAILED");
    return true;
}

void OnFactory(void*) {
    if (!g_finished) {
        g_finished = TryApplyFix();
    }
}

}  // namespace

MIXEDNUTS_PLUGIN_EXPORT int WINAPI MixedNutsPluginInit(const MixedNutsApi* api) {
    if (api == nullptr || api->size < sizeof(MixedNutsApi) ||
        api->version != MIXEDNUTS_API_VERSION) {
        return 0;
    }
    mixednuts::log::Open(api->pluginDir, L"adapterfix.log", true);
    Write("=== Adapter Fix %s / Created by MixedNuts ===", kVersion);
    return api->RegisterFactoryHook(api, &OnFactory, nullptr);
}
