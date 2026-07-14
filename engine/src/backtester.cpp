#include "quantdesk/backtester.hpp"

namespace quantdesk {

Backtester::Backtester(MatchingEngine& engine) : engine_(engine) {}

void Backtester::replay(const std::vector<Order>& orders) {
  for (const auto& order : orders) {
    engine_.submit(order);
  }
}

}  // namespace quantdesk
