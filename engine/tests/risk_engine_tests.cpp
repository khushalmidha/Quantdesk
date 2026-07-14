#include <gtest/gtest.h>

#include <string>

#include "quantdesk/event_bus.hpp"
#include "quantdesk/risk_engine.hpp"

namespace {

using namespace quantdesk;

Order order(OrderId id, Side side, Price price, Quantity quantity) {
  return Order{id, "BTC-PERP", "desk", side, OrderType::Limit, price, quantity};
}

EngineEvent fill(Side side, Price price, Quantity quantity) {
  return EngineEvent{EventType::Fill, 100, 0, "BTC-PERP", side, price,
                     quantity, {}};
}

}  // namespace

TEST(RiskEngine, RejectsProjectedPositionBeyondLimit) {
  EventBus bus;
  RiskEngine risk(bus);
  auto limits = RiskLimits{};
  limits.max_position = 10;
  limits.max_order_notional = 1'000'000;
  limits.max_aggregate_notional = 1'000'000;
  risk.set_limits(limits);

  bus.publish(fill(Side::Buy, 100, 8));

  std::string reason;
  EXPECT_FALSE(risk.approve(order(1, Side::Buy, 100, 3), reason));
  EXPECT_EQ(reason, "MAX_POSITION");
}

TEST(RiskEngine, RejectsProjectedAggregateNotionalBeyondLimit) {
  EventBus bus;
  RiskEngine risk(bus);
  auto limits = RiskLimits{};
  limits.max_position = 100;
  limits.max_order_notional = 1'000'000;
  limits.max_aggregate_notional = 1'000;
  risk.set_limits(limits);

  bus.publish(fill(Side::Buy, 100, 8));

  std::string reason;
  EXPECT_FALSE(risk.approve(order(1, Side::Buy, 100, 3), reason));
  EXPECT_EQ(reason, "MAX_AGGREGATE_NOTIONAL");
}

TEST(RiskEngine, DailyLossLimitAutomaticallyHaltsApprovals) {
  EventBus bus;
  RiskEngine risk(bus);
  auto limits = RiskLimits{};
  limits.max_position = 100;
  limits.max_order_notional = 1'000'000;
  limits.max_aggregate_notional = 1'000'000;
  limits.daily_loss_limit = 50;
  risk.set_limits(limits);

  bus.publish(fill(Side::Buy, 100, 10));
  risk.update_last_trade("BTC-PERP", 90);

  std::string reason;
  EXPECT_FALSE(risk.approve(order(1, Side::Sell, 90, 1), reason));
  EXPECT_EQ(reason, "DAILY_LOSS_LIMIT");
  EXPECT_LE(risk.daily_pnl(), -50);
}

TEST(RiskEngine, ObservesFillEventsFromEventBus) {
  EventBus bus;
  RiskEngine risk(bus);

  bus.publish(fill(Side::Buy, 100, 7));
  bus.publish(fill(Side::Sell, 105, 2));

  EXPECT_EQ(risk.position("BTC-PERP"), 5);
  EXPECT_DOUBLE_EQ(risk.daily_pnl(), 35.0);
}
