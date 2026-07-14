#include "quantdesk/risk_engine.hpp"

#include <cmath>

namespace quantdesk {

void RiskEngine::set_limits(RiskLimits limits) { limits_ = limits; }

void RiskEngine::update_last_trade(const std::string& instrument, Price price) {
  last_trade_[instrument] = price;
}

void RiskEngine::halt_all() { halted_ = true; }

bool RiskEngine::approve(const Order& order, std::string& reason) const {
  if (halted_) {
    reason = "KILL_SWITCH_ACTIVE";
    return false;
  }
  const double notional =
      static_cast<double>(std::llabs(order.price)) * static_cast<double>(order.quantity);
  if (notional > limits_.max_order_notional) {
    reason = "MAX_ORDER_NOTIONAL";
    return false;
  }
  auto last = last_trade_.find(order.instrument);
  if (last != last_trade_.end() && order.type != OrderType::Market) {
    const double collar = static_cast<double>(last->second) * limits_.price_collar_fraction;
    if (std::fabs(static_cast<double>(order.price - last->second)) > collar) {
      reason = "PRICE_COLLAR";
      return false;
    }
  }
  reason.clear();
  return true;
}

}  // namespace quantdesk
