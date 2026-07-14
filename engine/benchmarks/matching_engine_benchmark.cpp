#include <benchmark/benchmark.h>

#include "quantdesk/matching_engine.hpp"

static void BM_MatchingEngineSubmit(benchmark::State& state) {
  using namespace quantdesk;
  EventBus bus;
  MatchingEngine engine(bus);
  OrderId id = 1;

  for (auto _ : state) {
    engine.submit(Order{id++, "BTC-PERP", "bench", Side::Buy, OrderType::Limit,
                        100000, 1});
    benchmark::DoNotOptimize(id);
  }
  state.SetItemsProcessed(state.iterations());
}

BENCHMARK(BM_MatchingEngineSubmit);
BENCHMARK_MAIN();
