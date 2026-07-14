#include "quantdesk/order_book.hpp"

#include <utility>

namespace quantdesk {

OrderBook::OrderBook(std::string instrument, EventBus& event_bus)
    : instrument_(std::move(instrument)), event_bus_(event_bus) {}

void OrderBook::submit(const Order& input) {
  Order order = input;
  if (order.instrument.empty()) {
    order.instrument = instrument_;
  }
  if (!validate(order)) {
    return;
  }

  ack(order);

  if (order.type == OrderType::Fok && available_to_fill(order) < order.quantity) {
    reject(order, "FOK_NOT_FILLABLE");
    return;
  }

  const bool can_rest =
      order.type == OrderType::Limit || order.type == OrderType::Gtc;
  match(order, can_rest);
}

bool OrderBook::cancel(OrderId order_id) {
  auto found = locations_.find(order_id);
  if (found == locations_.end()) {
    return false;
  }

  const auto location = found->second;
  const Quantity remaining = location.iterator->remaining;
  if (location.side == Side::Buy) {
    auto level = bids_.find(location.price);
    level->second.erase(location.iterator);
    if (level->second.empty()) {
      bids_.erase(level);
    }
  } else {
    auto level = asks_.find(location.price);
    level->second.erase(location.iterator);
    if (level->second.empty()) {
      asks_.erase(level);
    }
  }
  locations_.erase(found);

  event_bus_.publish(EngineEvent{EventType::Cancel, order_id, 0, instrument_,
                                 Side::Buy, location.price, remaining, {}});
  return true;
}

std::optional<Price> OrderBook::best_bid() const {
  if (bids_.empty()) {
    return std::nullopt;
  }
  return bids_.begin()->first;
}

std::optional<Price> OrderBook::best_ask() const {
  if (asks_.empty()) {
    return std::nullopt;
  }
  return asks_.begin()->first;
}

std::optional<Quantity> OrderBook::resting_quantity(OrderId order_id) const {
  auto found = locations_.find(order_id);
  if (found == locations_.end()) {
    return std::nullopt;
  }
  return found->second.iterator->remaining;
}

bool OrderBook::contains(OrderId order_id) const {
  return locations_.find(order_id) != locations_.end();
}

bool OrderBook::validate(const Order& order) {
  if (order.id == 0) {
    reject(order, "MISSING_ORDER_ID");
    return false;
  }
  if (order.instrument != instrument_) {
    reject(order, "WRONG_INSTRUMENT");
    return false;
  }
  if (order.quantity <= 0) {
    reject(order, "NON_POSITIVE_QUANTITY");
    return false;
  }
  if (locations_.find(order.id) != locations_.end()) {
    reject(order, "DUPLICATE_ORDER_ID");
    return false;
  }
  if (order.type != OrderType::Market && order.price <= 0) {
    reject(order, "NON_POSITIVE_PRICE");
    return false;
  }
  if (crosses(order)) {
    reject(order, "SELF_CROSS");
    return false;
  }
  return true;
}

bool OrderBook::crosses(const Order& order) const {
  if (order.participant.empty()) {
    return false;
  }

  if (order.side == Side::Buy) {
    for (const auto& [price, level] : asks_) {
      if (order.type != OrderType::Market && price > order.price) {
        break;
      }
      for (const auto& resting : level) {
        if (resting.order.participant == order.participant) {
          return true;
        }
      }
    }
  } else {
    for (const auto& [price, level] : bids_) {
      if (order.type != OrderType::Market && price < order.price) {
        break;
      }
      for (const auto& resting : level) {
        if (resting.order.participant == order.participant) {
          return true;
        }
      }
    }
  }
  return false;
}

Quantity OrderBook::available_to_fill(const Order& order) const {
  Quantity available = 0;
  if (order.side == Side::Buy) {
    for (const auto& [price, level] : asks_) {
      if (order.type != OrderType::Market && price > order.price) {
        break;
      }
      for (const auto& resting : level) {
        available += resting.remaining;
        if (available >= order.quantity) {
          return available;
        }
      }
    }
  } else {
    for (const auto& [price, level] : bids_) {
      if (order.type != OrderType::Market && price < order.price) {
        break;
      }
      for (const auto& resting : level) {
        available += resting.remaining;
        if (available >= order.quantity) {
          return available;
        }
      }
    }
  }
  return available;
}

void OrderBook::match(Order& incoming, bool rest_remainder) {
  auto consume_ask = [&](auto level_it) {
    auto& level = level_it->second;
    auto resting_it = level.begin();
    while (resting_it != level.end() && incoming.quantity > 0) {
      const Quantity traded = std::min(incoming.quantity, resting_it->remaining);
      fill(incoming, *resting_it, level_it->first, traded);
      incoming.quantity -= traded;
      resting_it->remaining -= traded;
      if (resting_it->remaining == 0) {
        locations_.erase(resting_it->order.id);
        resting_it = level.erase(resting_it);
      } else {
        ++resting_it;
      }
    }
  };

  if (incoming.side == Side::Buy) {
    while (!asks_.empty() && incoming.quantity > 0) {
      auto level_it = asks_.begin();
      if (incoming.type != OrderType::Market && level_it->first > incoming.price) {
        break;
      }
      consume_ask(level_it);
      if (level_it->second.empty()) {
        asks_.erase(level_it);
      }
    }
  } else {
    while (!bids_.empty() && incoming.quantity > 0) {
      auto level_it = bids_.begin();
      if (incoming.type != OrderType::Market && level_it->first < incoming.price) {
        break;
      }
      auto& level = level_it->second;
      auto resting_it = level.begin();
      while (resting_it != level.end() && incoming.quantity > 0) {
        const Quantity traded =
            std::min(incoming.quantity, resting_it->remaining);
        fill(incoming, *resting_it, level_it->first, traded);
        incoming.quantity -= traded;
        resting_it->remaining -= traded;
        if (resting_it->remaining == 0) {
          locations_.erase(resting_it->order.id);
          resting_it = level.erase(resting_it);
        } else {
          ++resting_it;
        }
      }
      if (level.empty()) {
        bids_.erase(level_it);
      }
    }
  }

  if (incoming.quantity > 0 && rest_remainder) {
    rest(incoming);
  } else if (incoming.quantity > 0 &&
             (incoming.type == OrderType::Ioc || incoming.type == OrderType::Market)) {
    event_bus_.publish(EngineEvent{EventType::Cancel, incoming.id, 0,
                                   instrument_, incoming.side, incoming.price,
                                   incoming.quantity, "UNFILLED_REMAINDER"});
  }
}

void OrderBook::rest(Order& order) {
  auto resting = RestingOrder{order, order.quantity, next_sequence_++};
  if (order.side == Side::Buy) {
    auto& level = bids_[order.price];
    level.push_back(resting);
    auto it = std::prev(level.end());
    locations_[order.id] = OrderLocation{order.side, order.price, it};
  } else {
    auto& level = asks_[order.price];
    level.push_back(resting);
    auto it = std::prev(level.end());
    locations_[order.id] = OrderLocation{order.side, order.price, it};
  }
}

void OrderBook::reject(const Order& order, std::string reason) {
  event_bus_.publish(EngineEvent{EventType::Reject, order.id, 0, instrument_,
                                 order.side, order.price, order.quantity,
                                 std::move(reason)});
}

void OrderBook::ack(const Order& order) {
  event_bus_.publish(EngineEvent{EventType::OrderAck, order.id, 0, instrument_,
                                 order.side, order.price, order.quantity, {}});
}

void OrderBook::fill(const Order& incoming, const RestingOrder& resting,
                     Price price, Quantity quantity) {
  event_bus_.publish(EngineEvent{EventType::Fill, incoming.id, resting.order.id,
                                 instrument_, incoming.side, price, quantity,
                                 {}});
}

}  // namespace quantdesk
