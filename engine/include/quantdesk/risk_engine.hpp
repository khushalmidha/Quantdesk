#pragma once

#include <string>
#include <unordered_map>

#include "quantdesk/types.hpp"

namespace quantdesk {

struct RiskLimits {
  double max_order_notional{100000.0};
  Quantity max_position{100};
  double max_aggregate_notional{500000.0};
  double price_collar_fraction{0.05};
  double daily_loss_limit{10000.0};
};

/**
 * Pre-trade risk checker and kill-switch state holder.
 */
class RiskEngine {
 public:
  /**
   * Replaces the active risk limits.
   */
  void set_limits(RiskLimits limits);

  /**
   * Records the last traded price for price-collar checks.
   */
  void update_last_trade(const std::string& instrument, Price price);

  /**
   * Blocks all future order approvals until reset_for_test is called.
   */
  void halt_all();

  /**
   * Checks whether an outbound order is permitted by current limits.
   */
  bool approve(const Order& order, std::string& reason) const;

 private:
  RiskLimits limits_;
  bool halted_{false};
  std::unordered_map<std::string, Price> last_trade_;
};

}  // namespace quantdesk
