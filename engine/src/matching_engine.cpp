#include "quantdesk/matching_engine.hpp"

namespace quantdesk {

MatchingEngine::MatchingEngine(EventBus& event_bus) : event_bus_(event_bus) {}

void MatchingEngine::submit(const Order& order) { book(order.instrument).submit(order); }

bool MatchingEngine::cancel(const std::string& instrument, OrderId order_id) {
  return book(instrument).cancel(order_id);
}

OrderBook& MatchingEngine::book(const std::string& instrument) {
  auto found = books_.find(instrument);
  if (found == books_.end()) {
    auto inserted = books_.emplace(
        instrument, std::make_unique<OrderBook>(instrument, event_bus_));
    found = inserted.first;
  }
  return *found->second;
}

}  // namespace quantdesk
