"""Avellaneda-Stoikov market-making model used to skew bid and ask quotes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AvellanedaStoikov:
    """Inventory-aware quote model parameterized by risk aversion and fill intensity."""

    gamma: float
    kappa: float
    quote_size: float

    def reservation_price(
        self, mid: float, inventory: float, sigma: float, time_remaining: float
    ) -> float:
        """Return the inventory-skewed reservation price."""
        return mid - inventory * self.gamma * sigma * sigma * time_remaining

    def optimal_spread(self, sigma: float, time_remaining: float) -> float:
        """Return the model spread around the reservation price."""
        inventory_term = self.gamma * sigma * sigma * time_remaining
        arrival_term = (2.0 / self.gamma) * self._log1p_gamma_over_kappa()
        return inventory_term + arrival_term

    def quotes(
        self, mid: float, inventory: float, sigma: float, time_remaining: float
    ) -> tuple[float, float]:
        """Return bid and ask quotes."""
        reservation = self.reservation_price(mid, inventory, sigma, time_remaining)
        half_spread = self.optimal_spread(sigma, time_remaining) / 2.0
        return reservation - half_spread, reservation + half_spread

    def _log1p_gamma_over_kappa(self) -> float:
        import math

        return math.log1p(self.gamma / self.kappa)
