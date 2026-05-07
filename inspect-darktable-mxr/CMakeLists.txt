cmake_minimum_required(VERSION 3.10)
project(inspect_mxr)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(migraphx REQUIRED)

add_executable(inspect_mxr main.cpp)
target_link_libraries(inspect_mxr migraphx::migraphx)
