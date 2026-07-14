#pragma once

#include <functional>
#include <mutex>
#include <vector>

#include "quantdesk/types.hpp"

namespace quantdesk {

/**
 * In-process event fanout used by matching, risk, gateway, and backtest code.
 */
class EventBus {
 public:
  using Handler = std::function<void(const EngineEvent&)>;

  /**
   * Registers a callback that receives every later engine event.
   */
  void subscribe(Handler handler);

  /**
   * Publishes an event to all registered subscribers.
   */
  void publish(const EngineEvent& event) const;

 private:
  mutable std::mutex mutex_;
  std::vector<Handler> handlers_;
};

}  // namespace quantdesk
