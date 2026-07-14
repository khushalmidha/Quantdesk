#pragma once

#include <memory>
#include <string>
#include <unordered_map>

#include "quantdesk/order_book.hpp"

namespace quantdesk {

/**
 * Deterministic multi-instrument matching engine.
 */
class MatchingEngine {
 public:
  /**
   * Creates a matching engine that publishes onto the supplied event bus.
   */
  explicit MatchingEngine(EventBus& event_bus);

  /**
   * Submits an order through the same path used by live and backtest modes.
   */
  void submit(const Order& order);

  /**
   * Cancels an order on the specified instrument.
   */
  bool cancel(const std::string& instrument, OrderId order_id);

  /**
   * Returns a mutable book for advanced test and integration harnesses.
   */
  OrderBook& book(const std::string& instrument);

 private:
  EventBus& event_bus_;
  std::unordered_map<std::string, std::unique_ptr<OrderBook>> books_;
};

}  // namespace quantdesk
