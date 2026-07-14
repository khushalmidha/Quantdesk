#pragma once

#include <string>

#include "quantdesk/event_bus.hpp"
#include "quantdesk/risk_engine.hpp"

namespace quantdesk {

/**
 * Deribit gateway facade. The concrete websocket client is wired in M2.
 */
class ExchangeGateway {
 public:
  /**
   * Creates a gateway that must pass outbound orders through risk checks.
   */
  ExchangeGateway(EventBus& event_bus, RiskEngine& risk_engine);

  /**
   * Subscribes to normalized book and trade feeds for an instrument.
   */
  void subscribe(const std::string& instrument);

  /**
   * Sends an order after risk approval. Returns false on risk reject.
   */
  bool send_order(const Order& order, std::string& reason);

 private:
  EventBus& event_bus_;
  RiskEngine& risk_engine_;
};

}  // namespace quantdesk
