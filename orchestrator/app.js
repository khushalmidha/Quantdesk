const express = require("express");
const helmet = require("helmet");
const cors = require("cors");

const strategyRouter = require("./Routers/strategyRouter");
const riskRouter = require("./Routers/riskRouter");

const app = express();
app.use(helmet());
app.use(cors());
app.use(express.json());

app.get("/health", (_req, res) => res.json({ status: "ok" }));
app.use("/api/strategy", strategyRouter);
app.use("/api/risk", riskRouter);

module.exports = app;
