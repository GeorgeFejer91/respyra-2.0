cmake_minimum_required(VERSION 3.20)
project(respyrecorder LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
find_package(LSL REQUIRED CONFIG)
add_executable(respyrecorder main.cpp
    "${RECORDER_SOURCE}/src/recording.cpp"
    "${RECORDER_SOURCE}/xdfwriter/xdfwriter.cpp")
target_include_directories(respyrecorder PRIVATE
    "${RECORDER_SOURCE}/src" "${RECORDER_SOURCE}/xdfwriter")
target_link_libraries(respyrecorder PRIVATE LSL::lsl)
