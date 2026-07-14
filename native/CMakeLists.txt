cmake_minimum_required(VERSION 3.16)
project(rc522_mfc_native LANGUAGES C CXX)

option(RC522_HARDWARE "Build with WiringPi hardware access" ON)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(HAKON_DIR "${CMAKE_CURRENT_SOURCE_DIR}/vendor/hakon/src")

add_library(rc522_hakon STATIC
    ${HAKON_DIR}/RC522.cpp
    ${HAKON_DIR}/MFrec.cpp
    ${HAKON_DIR}/crapto1.c
    ${HAKON_DIR}/crypto1.c
)

target_include_directories(rc522_hakon PUBLIC ${HAKON_DIR})
target_compile_options(rc522_hakon PRIVATE -Wall -Wextra -Wno-unused-parameter)

if(RC522_HARDWARE)
    target_compile_definitions(rc522_hakon PUBLIC RC522_WIRE=1)
    find_library(WIRINGPI_LIBRARY wiringPi REQUIRED)
    target_link_libraries(rc522_hakon PUBLIC ${WIRINGPI_LIBRARY} pthread)
else()
    target_compile_definitions(rc522_hakon PUBLIC RC522_WIRE=0)
    target_link_libraries(rc522_hakon PUBLIC pthread)
endif()

add_executable(rc522-mfc-native src/rc522_mfc_native.cpp)
target_link_libraries(rc522-mfc-native PRIVATE rc522_hakon)
target_compile_options(rc522-mfc-native PRIVATE -Wall -Wextra -Wpedantic)

install(TARGETS rc522-mfc-native RUNTIME DESTINATION bin)
