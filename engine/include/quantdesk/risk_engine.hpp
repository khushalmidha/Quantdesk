#pragma once

#include <string>
#include <unordered_map>

#include "quantdesk/types.hpp"

namespace quantdesk {

class EventBus;

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
  RiskEngine() = default;

  /**
   * Creates a risk engine that observes fills from the shared event bus.
   */
  explicit RiskEngine(EventBus& event_bus);

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

  /**
   * Applies engine events to risk state. Fill events update position and P&L.
   */
  void observe(const EngineEvent& event);

  /**
   * Returns current signed position for an instrument.
   */
  Quantity position(const std::string& instrument) const;

  /**
   * Returns current mark-to-last daily P&L.
   */
  double daily_pnl() const;

 private:
  struct PositionState {
    Quantity position{0};
    double cash{0.0};
  };

  double aggregate_notional_after(const Order& order) const;
  double mark_to_last_pnl() const;
  void enforce_loss_limit();

  RiskLimits limits_;
  bool halted_{false};
  std::string halt_reason_{"KILL_SWITCH_ACTIVE"};
  std::unordered_map<std::string, Price> last_trade_;
  std::unordered_map<std::string, PositionState> positions_;
  double daily_pnl_{0.0};
};

}  // namespace quantdesk
