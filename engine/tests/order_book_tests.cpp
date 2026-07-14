#include <gtest/gtest.h>

#include <vector>

#include "quantdesk/matching_engine.hpp"

namespace {

using namespace quantdesk;

Order limit(OrderId id, Side side, Price price, Quantity quantity,
            std::string participant = "p") {
  return Order{id, "BTC-PERP", std::move(participant), side, OrderType::Limit,
               price, quantity};
}

std::vector<EngineEvent> capture(EventBus& bus) {
  auto events = std::vector<EngineEvent>{};
  bus.subscribe([&](const EngineEvent& event) { events.push_back(event); });
  return events;
}

}  // namespace

TEST(OrderBook, PriceTimePriority) {
  EventBus bus;
  std::vector<EngineEvent> events;
  bus.subscribe([&](const EngineEvent& event) { events.push_back(event); });
  MatchingEngine engine(bus);

  engine.submit(limit(1, Side::Sell, 101, 5, "a"));
  engine.submit(limit(2, Side::Sell, 101, 5, "b"));
  engine.submit(limit(3, Side::Buy, 101, 7, "c"));

  std::vector<OrderId> resting_ids;
  for (const auto& event : events) {
    if (event.type == EventType::Fill) {
      resting_ids.push_back(event.resting_order_id);
    }
  }

  ASSERT_EQ(resting_ids.size(), 2U);
  EXPECT_EQ(resting_ids[0], 1U);
  EXPECT_EQ(resting_ids[1], 2U);
  EXPECT_EQ(engine.book("BTC-PERP").resting_quantity(2), 3);
}

TEST(OrderBook, PartialFillSequencing) {
  EventBus bus;
  std::vector<EngineEvent> events;
  bus.subscribe([&](const EngineEvent& event) { events.push_back(event); });
  MatchingEngine engine(bus);

  engine.submit(limit(1, Side::Sell, 100, 10, "a"));
  engine.submit(limit(2, Side::Buy, 100, 4, "b"));
  engine.submit(limit(3, Side::Buy, 100, 6, "c"));

  std::vector<Quantity> fills;
  for (const auto& event : events) {
    if (event.type == EventType::Fill) {
      fills.push_back(event.quantity);
    }
  }

  ASSERT_EQ(fills.size(), 2U);
  EXPECT_EQ(fills[0], 4);
  EXPECT_EQ(fills[1], 6);
  EXPECT_FALSE(engine.book("BTC-PERP").contains(1));
}

TEST(OrderBook, SelfCrossPrevention) {
  EventBus bus;
  std::vector<EngineEvent> events;
  bus.subscribe([&](const EngineEvent& event) { events.push_back(event); });
  MatchingEngine engine(bus);

  engine.submit(limit(1, Side::Sell, 100, 10, "desk"));
  engine.submit(limit(2, Side::Buy, 101, 5, "desk"));

  ASSERT_EQ(events.back().type, EventType::Reject);
  EXPECT_EQ(events.back().reason, "SELF_CROSS");
  EXPECT_EQ(engine.book("BTC-PERP").resting_quantity(1), 10);
}

TEST(OrderBook, CancelAfterPartialFill) {
  EventBus bus;
  MatchingEngine engine(bus);

  engine.submit(limit(1, Side::Sell, 100, 10, "a"));
  engine.submit(limit(2, Side::Buy, 100, 4, "b"));

  EXPECT_EQ(engine.book("BTC-PERP").resting_quantity(1), 6);
  EXPECT_TRUE(engine.cancel("BTC-PERP", 1));
  EXPECT_FALSE(engine.book("BTC-PERP").contains(1));
}

TEST(OrderBook, IocCancelsRemainder) {
  EventBus bus;
  std::vector<EngineEvent> events;
  bus.subscribe([&](const EngineEvent& event) { events.push_back(event); });
  MatchingEngine engine(bus);

  engine.submit(limit(1, Side::Sell, 100, 3, "a"));
  engine.submit(Order{2, "BTC-PERP", "b", Side::Buy, OrderType::Ioc, 100, 5});

  EXPECT_FALSE(engine.book("BTC-PERP").contains(2));
  EXPECT_FALSE(engine.book("BTC-PERP").contains(1));
  EXPECT_EQ(events.back().type, EventType::Cancel);
  EXPECT_EQ(events.back().quantity, 2);
}

TEST(OrderBook, FokRejectsWhenNotFullyFillable) {
  EventBus bus;
  std::vector<EngineEvent> events;
  bus.subscribe([&](const EngineEvent& event) { events.push_back(event); });
  MatchingEngine engine(bus);

  engine.submit(limit(1, Side::Sell, 100, 3, "a"));
  engine.submit(Order{2, "BTC-PERP", "b", Side::Buy, OrderType::Fok, 100, 5});

  EXPECT_EQ(engine.book("BTC-PERP").resting_quantity(1), 3);
  EXPECT_EQ(events.back().type, EventType::Reject);
  EXPECT_EQ(events.back().reason, "FOK_NOT_FILLABLE");
}
