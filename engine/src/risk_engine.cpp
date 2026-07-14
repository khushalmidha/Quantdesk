#include "quantdesk/risk_engine.hpp"

#include <cmath>
#include <cstdlib>

#include "quantdesk/event_bus.hpp"

namespace quantdesk {

RiskEngine::RiskEngine(EventBus& event_bus) {
  event_bus.subscribe([this](const EngineEvent& event) { observe(event); });
}

void RiskEngine::set_limits(RiskLimits limits) { limits_ = limits; }

void RiskEngine::update_last_trade(const std::string& instrument, Price price) {
  last_trade_[instrument] = price;
  enforce_loss_limit();
}

void RiskEngine::halt_all() {
  halted_ = true;
  halt_reason_ = "KILL_SWITCH_ACTIVE";
}

bool RiskEngine::approve(const Order& order, std::string& reason) const {
  if (halted_) {
    reason = halt_reason_;
    return false;
  }
  const double notional =
      static_cast<double>(std::llabs(order.price)) * static_cast<double>(order.quantity);
  if (notional > limits_.max_order_notional) {
    reason = "MAX_ORDER_NOTIONAL";
    return false;
  }

  const auto current_position = position(order.instrument);
  const auto signed_quantity =
      order.side == Side::Buy ? order.quantity : -order.quantity;
  const auto projected_position = current_position + signed_quantity;
  if (std::llabs(projected_position) > limits_.max_position) {
    reason = "MAX_POSITION";
    return false;
  }

  if (aggregate_notional_after(order) > limits_.max_aggregate_notional) {
    reason = "MAX_AGGREGATE_NOTIONAL";
    return false;
  }

  if (daily_pnl_ <= -limits_.daily_loss_limit) {
    reason = "DAILY_LOSS_LIMIT";
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

void RiskEngine::observe(const EngineEvent& event) {
  if (event.type != EventType::Fill) {
    return;
  }

  auto& state = positions_[event.instrument];
  const auto signed_quantity =
      event.side == Side::Buy ? event.quantity : -event.quantity;
  state.position += signed_quantity;
  state.cash -= static_cast<double>(signed_quantity) *
                static_cast<double>(event.price);
  last_trade_[event.instrument] = event.price;
  enforce_loss_limit();
}

Quantity RiskEngine::position(const std::string& instrument) const {
  auto found = positions_.find(instrument);
  if (found == positions_.end()) {
    return 0;
  }
  return found->second.position;
}

double RiskEngine::daily_pnl() const { return daily_pnl_; }

double RiskEngine::aggregate_notional_after(const Order& order) const {
  double aggregate = 0.0;
  for (const auto& [instrument, state] : positions_) {
    if (instrument == order.instrument) {
      continue;
    }
    auto last = last_trade_.find(instrument);
    const auto mark = last != last_trade_.end() ? last->second : order.price;
    aggregate += std::fabs(static_cast<double>(state.position)) *
                 std::fabs(static_cast<double>(mark));
  }

  const auto current_position = position(order.instrument);
  const auto signed_quantity =
      order.side == Side::Buy ? order.quantity : -order.quantity;
  const auto projected_position = current_position + signed_quantity;
  auto last = last_trade_.find(order.instrument);
  const auto mark = order.price != 0
                        ? order.price
                        : (last != last_trade_.end() ? last->second : 0);

  aggregate += std::fabs(static_cast<double>(projected_position)) *
               std::fabs(static_cast<double>(mark));
  return aggregate;
}

double RiskEngine::mark_to_last_pnl() const {
  double pnl = 0.0;
  for (const auto& [instrument, state] : positions_) {
    auto last = last_trade_.find(instrument);
    if (last == last_trade_.end()) {
      pnl += state.cash;
      continue;
    }
    pnl += state.cash + static_cast<double>(state.position) *
                            static_cast<double>(last->second);
  }
  return pnl;
}

void RiskEngine::enforce_loss_limit() {
  daily_pnl_ = mark_to_last_pnl();
  if (daily_pnl_ <= -limits_.daily_loss_limit) {
    halted_ = true;
    halt_reason_ = "DAILY_LOSS_LIMIT";
  }
}

}  // namespace quantdesk
