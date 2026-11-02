cmake_minimum_required(VERSION 3.20)
project(ca2s_adapter_fix LANGUAGES CXX)

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "The game is x64 only. Configure with -A x64.")
endif()

# The loader's API and shared headers. Defaults to the mod-loader submodule;
# pass -DMIXEDNUTS_LOADER=<path> to build against another checkout.
set(MIXEDNUTS_LOADER "${CMAKE_CURRENT_SOURCE_DIR}/mod-loader" CACHE PATH "MixedNuts Mod Loader checkout")
if(NOT EXISTS "${MIXEDNUTS_LOADER}/api/mixednuts/plugin.h")
  message(FATAL_ERROR "mod-loader is missing. Run: git submodule update --init")
endif()

# Static CRT, so nothing here adds a runtime dependency to the game.
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

# MixedNuts\Mods\adapterfix\adapterfix.dll
add_library(adapterfix SHARED src/adapterfix.cpp)
target_compile_features(adapterfix PRIVATE cxx_std_17)
target_compile_definitions(adapterfix PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX UNICODE _UNICODE)
target_compile_options(adapterfix PRIVATE /W4 /WX /utf-8)
target_include_directories(adapterfix PRIVATE
  "${MIXEDNUTS_LOADER}/common"
  "${MIXEDNUTS_LOADER}/api")

# cmake --install build --config Release --prefix dist
# lays out the files exactly as they go into the game folder.
install(TARGETS adapterfix RUNTIME DESTINATION MixedNuts/Mods/adapterfix)
install(FILES LICENSE DESTINATION MixedNuts/Mods/adapterfix RENAME LICENSE.txt)
