# QuantDesk

QuantDesk is a portfolio-grade crypto derivatives trading system built around a single deterministic C++ matching path. Live, paper, and backtest flows are intended to route through the same order book and matching engine so fills are reproducible and strategy behavior is easier to audit.

## Architecture

```text
Deribit testnet / historical data
          |
          v
Exchange gateway / backtest replay
          |
          v
Risk engine -> Matching engine -> Event bus -> Python research
                                      |
                                      v
                              Orchestrator API
                                      |
                                      v
                                  Dashboard
```

## Current Milestone

M0 and the core of M1 are in place:

- Repository skeleton for `engine`, `research`, `orchestrator`, and `dashboard`.
- CMake C++17 engine target.
- Price-time priority order book with `LIMIT`, `MARKET`, `IOC`, `FOK`, and `GTC` handling.
- Deterministic `MatchingEngine::submit(Order)` shared entry point.
- Event bus publishing order acks, fills, cancels, and rejects.
- GoogleTest suite covering price-time priority, partial fills, self-cross prevention, cancel-after-partial-fill, IOC, and FOK behavior.
- Google Benchmark harness for engine-internal submit throughput.
- Docker Compose and GitHub Actions CI skeleton.
- Static public dashboard in `dashboard/` with landing, replay, backtest, and architecture pages.

## Public Dashboard

The dashboard is a Vite React static site. It reads checked-in JSON exports from `dashboard/public/data/` and does not require the orchestrator, database, exchange gateway, or any environment variables to render.

```bash
cd dashboard
npm install
npm run dev
npm run build
```

Current dashboard data is marked as `placeholder_frontend_fixture` until real engine/research exports replace it. The dashboard footer links point to the relevant folders in `https://github.com/khushalmidha/Quantdesk`.

### Updating Dashboard Data

The dashboard reads a stable JSON contract, but raw data can come from CSV files, exchange downloads, or engine logs. Use the exporter as the adapter layer:

```bash
python research/export_dashboard_data.py --mode demo --out dashboard/public/data
```

For normalized trade/tick CSV files with `timestamp`, `price`, `quantity`, and `side` columns:

```bash
python research/export_dashboard_data.py --mode csv --input path/to/trades.csv --out dashboard/public/data
```

After exporting:

```bash
npm --prefix dashboard run build
git add research/export_dashboard_data.py dashboard/public/data README.md
git commit -m "Update dashboard data export"
git push
```

Vercel will redeploy automatically after the push.

## Build

```bash
cmake -S . -B build -DQUANTDESK_BUILD_BENCHMARKS=OFF
cmake --build build --config Release
ctest --test-dir build --output-on-failure
```

On this workstation, `g++` is available but `cmake` was not found on `PATH`, so local CMake verification was not completed in this pass.

## Benchmark

After CMake is available:

```bash
cmake -S . -B build -DQUANTDESK_BUILD_TESTS=OFF -DQUANTDESK_BUILD_BENCHMARKS=ON
cmake --build build --config Release
./build/engine/matching_engine_benchmark
```

Latency claims must be reported honestly:

| Measurement | Scope | Status |
| --- | --- | --- |
| Engine-internal matching throughput | In-process order submission only | Benchmark harness added; number not yet measured locally |
| Network round trip | Public internet to Deribit testnet | Not measured; expected to be dominated by tens of ms network latency |

## Safety Notes

QuantDesk is designed for Deribit testnet and historical-data research only. Do not connect real funds. API keys, MongoDB URIs, and JWT secrets belong in local `.env` files and must not be committed. ML and stat-arb output should be treated as backtest research, never a live performance guarantee.
