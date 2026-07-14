const express = require("express");

const router = express.Router();

const limits = {
  maxOrderNotional: 100000,
  maxPosition: 100,
  maxAggregateNotional: 500000,
  priceCollarFraction: 0.05,
  dailyLossLimit: 10000,
};

let halted = false;

router.post("/kill-switch", (_req, res) => {
  halted = true;
  res.json({ halted });
});

router.get("/limits", (_req, res) => {
  res.json({ halted, limits });
});

module.exports = router;
