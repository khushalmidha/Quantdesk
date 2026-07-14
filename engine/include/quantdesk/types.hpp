#pragma once

#include <cstdint>
#include <string>

namespace quantdesk {

using OrderId = std::uint64_t;
using Price = std::int64_t;
using Quantity = std::int64_t;

enum class Side { Buy, Sell };
enum class OrderType { Limit, Market, Ioc, Fok, Gtc };
enum class TimeInForce { Ioc, Fok, Gtc };
enum class EventType { OrderAck, Fill, Cancel, Reject };

struct Order {
  OrderId id{};
  std::string instrument;
  std::string participant;
  Side side{Side::Buy};
  OrderType type{OrderType::Limit};
  Price price{};
  Quantity quantity{};
};

struct EngineEvent {
  EventType type{EventType::OrderAck};
  OrderId order_id{};
  OrderId resting_order_id{};
  std::string instrument;
  Side side{Side::Buy};
  Price price{};
  Quantity quantity{};
  std::string reason;
};

}  // namespace quantdesk
