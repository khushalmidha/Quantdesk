const express = require("express");

const router = express.Router();

let state = { running: false, strategy: null };

router.post("/start", (req, res) => {
  state = { running: true, strategy: req.body };
  res.json(state);
});

router.post("/stop", (_req, res) => {
  state = { running: false, strategy: state.strategy };
  res.json(state);
});

router.get("/status", (_req, res) => {
  res.json(state);
});

module.exports = router;
