cmake_minimum_required(VERSION 3.20)
project(quantdesk_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)

add_library(quantdesk_engine
  src/backtester.cpp
  src/event_bus.cpp
  src/exchange_gateway.cpp
  src/matching_engine.cpp
  src/order_book.cpp
  src/risk_engine.cpp
)
target_include_directories(quantdesk_engine PUBLIC include)

option(QUANTDESK_BUILD_TESTS "Build QuantDesk engine tests" ON)
option(QUANTDESK_BUILD_BENCHMARKS "Build QuantDesk engine benchmarks" ON)

if(QUANTDESK_BUILD_TESTS)
  enable_testing()
  FetchContent_Declare(
    googletest
    URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
  )
  set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
  FetchContent_MakeAvailable(googletest)

  add_executable(order_book_tests tests/order_book_tests.cpp)
  target_link_libraries(order_book_tests PRIVATE quantdesk_engine GTest::gtest_main)
  add_executable(risk_engine_tests tests/risk_engine_tests.cpp)
  target_link_libraries(risk_engine_tests PRIVATE quantdesk_engine GTest::gtest_main)
  include(GoogleTest)
  gtest_discover_tests(order_book_tests)
  gtest_discover_tests(risk_engine_tests)
endif()

if(QUANTDESK_BUILD_BENCHMARKS)
  FetchContent_Declare(
    googlebenchmark
    URL https://github.com/google/benchmark/archive/refs/tags/v1.8.3.zip
  )
  set(BENCHMARK_ENABLE_TESTING OFF CACHE BOOL "" FORCE)
  FetchContent_MakeAvailable(googlebenchmark)

  add_executable(matching_engine_benchmark benchmarks/matching_engine_benchmark.cpp)
  target_link_libraries(matching_engine_benchmark PRIVATE quantdesk_engine benchmark::benchmark)
endif()
