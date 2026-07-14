#pragma once

#include <vector>

#include "quantdesk/matching_engine.hpp"

namespace quantdesk {

/**
 * Event-replay harness that drives the same MatchingEngine used in live mode.
 */
class Backtester {
 public:
  /**
   * Creates a backtester over an externally owned matching engine.
   */
  explicit Backtester(MatchingEngine& engine);

  /**
   * Replays orders in deterministic input order.
   */
  void replay(const std::vector<Order>& orders);

 private:
  MatchingEngine& engine_;
};

}  // namespace quantdesk
