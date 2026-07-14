#include "quantdesk/exchange_gateway.hpp"

namespace quantdesk {

ExchangeGateway::ExchangeGateway(EventBus& event_bus, RiskEngine& risk_engine)
    : event_bus_(event_bus), risk_engine_(risk_engine) {}

void ExchangeGateway::subscribe(const std::string& instrument) {
  event_bus_.publish(EngineEvent{EventType::OrderAck, 0, 0, instrument,
                                 Side::Buy, 0, 0, "SUBSCRIBED"});
}

bool ExchangeGateway::send_order(const Order& order, std::string& reason) {
  if (!risk_engine_.approve(order, reason)) {
    event_bus_.publish(EngineEvent{EventType::Reject, order.id, 0,
                                   order.instrument, order.side, order.price,
                                   order.quantity, reason});
    return false;
  }
  return true;
}

}  // namespace quantdesk
