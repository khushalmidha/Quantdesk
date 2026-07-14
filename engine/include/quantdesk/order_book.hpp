#pragma once

#include <list>
#include <map>
#include <optional>
#include <string>
#include <unordered_map>

#include "quantdesk/event_bus.hpp"
#include "quantdesk/types.hpp"

namespace quantdesk {

/**
 * Price-time priority limit order book for one instrument.
 */
class OrderBook {
 public:
  /**
   * Creates an order book bound to one instrument and event bus.
   */
  OrderBook(std::string instrument, EventBus& event_bus);

  /**
   * Submits an order and emits ack, fill, cancel, or reject events.
   */
  void submit(const Order& order);

  /**
   * Cancels a resting order by id in average O(1) lookup time.
   */
  bool cancel(OrderId order_id);

  /**
   * Returns the current best bid price when present.
   */
  std::optional<Price> best_bid() const;

  /**
   * Returns the current best ask price when present.
   */
  std::optional<Price> best_ask() const;

  /**
   * Returns the remaining resting quantity for an order id.
   */
  std::optional<Quantity> resting_quantity(OrderId order_id) const;

  /**
   * Returns true when the order id is currently resting.
   */
  bool contains(OrderId order_id) const;

 private:
  struct RestingOrder {
    Order order;
    Quantity remaining{};
    std::uint64_t sequence{};
  };

  using Level = std::list<RestingOrder>;
  using BidLevels = std::map<Price, Level, std::greater<Price>>;
  using AskLevels = std::map<Price, Level, std::less<Price>>;

  struct OrderLocation {
    Side side{Side::Buy};
    Price price{};
    Level::iterator iterator;
  };

  bool validate(const Order& order);
  bool crosses(const Order& order) const;
  Quantity available_to_fill(const Order& order) const;
  void match(Order& incoming, bool rest_remainder);
  void rest(Order& order);
  void erase_location(OrderId order_id);
  void reject(const Order& order, std::string reason);
  void ack(const Order& order);
  void fill(const Order& incoming, const RestingOrder& resting, Price price,
            Quantity quantity);

  std::string instrument_;
  EventBus& event_bus_;
  BidLevels bids_;
  AskLevels asks_;
  std::unordered_map<OrderId, OrderLocation> locations_;
  std::uint64_t next_sequence_{1};
};

}  // namespace quantdesk
