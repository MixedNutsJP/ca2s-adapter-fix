cmake_minimum_required(VERSION 3.20)
project(ca2s_adapter_fix LANGUAGES CXX ASM_MASM)

if(NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "The game is x64 only. Configure with -A x64.")
endif()

# Static CRT, so the proxy adds no runtime dependency of its own to the game.
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

add_library(dxgi SHARED
  src/dxgi_proxy.cpp
  src/stubs.asm
  src/dxgi.def
)
target_compile_features(dxgi PRIVATE cxx_std_17)
target_compile_definitions(dxgi PRIVATE WIN32_LEAN_AND_MEAN NOMINMAX UNICODE _UNICODE)
target_compile_options(dxgi PRIVATE $<$<COMPILE_LANGUAGE:CXX>:/W4 /WX /utf-8>)
