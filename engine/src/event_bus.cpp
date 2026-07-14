#include "quantdesk/event_bus.hpp"

namespace quantdesk {

void EventBus::subscribe(Handler handler) {
  std::lock_guard<std::mutex> lock(mutex_);
  handlers_.push_back(std::move(handler));
}

void EventBus::publish(const EngineEvent& event) const {
  std::vector<Handler> snapshot;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    snapshot = handlers_;
  }
  for (const auto& handler : snapshot) {
    handler(event);
  }
}

}  // namespace quantdesk
