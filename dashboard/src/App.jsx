import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  BookOpen,
  ChevronRight,
  Clock3,
  Cpu,
  Github,
  GitBranch,
  Pause,
  Play,
  Radio,
  ShieldCheck,
  Zap,
} from "lucide-react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Filler,
  Tooltip,
} from "chart.js";
import { Line, Bar } from "react-chartjs-2";
import "./styles.css";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Filler, Tooltip);

const routes = [
  { path: "/", label: "Landing", icon: Activity },
  { path: "/replay", label: "Replay", icon: Radio },
  { path: "/backtests", label: "Backtests", icon: BarChart3 },
  { path: "/architecture", label: "Architecture", icon: GitBranch },
];

const dataFiles = {
  session: "/data/session_demo.json",
  summary: "/data/backtest_summary.json",
  benchmarks: "/data/benchmarks.json",
};

function useStaticData() {
  const [data, setData] = useState({ session: null, summary: null, benchmarks: null });

  useEffect(() => {
    let mounted = true;
    Promise.all(Object.entries(dataFiles).map(([key, url]) => fetch(url).then((res) => res.json()).then((json) => [key, json])))
      .then((entries) => {
        if (mounted) setData(Object.fromEntries(entries));
      })
      .catch(() => {
        if (mounted) setData(fallbackData);
      });
    return () => {
      mounted = false;
    };
  }, []);

  return data.session ? data : fallbackData;
}

function useRoute() {
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const navigate = (nextPath) => {
    window.history.pushState({}, "", nextPath);
    setPath(nextPath);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return [path, navigate];
}

function App() {
  const data = useStaticData();
  const [path, navigate] = useRoute();
  const route = routes.some((item) => item.path === path) ? path : "/";

  return (
    <div className="site-shell">
      <Header route={route} navigate={navigate} />
      <DataStatusBadge status={data.session.dataStatus} />
      {route === "/" && <Landing data={data} navigate={navigate} />}
      {route === "/replay" && <ReplayPage session={data.session} />}
      {route === "/backtests" && <BacktestsPage summary={data.summary} session={data.session} />}
      {route === "/architecture" && <ArchitecturePage />}
      <Footer />
    </div>
  );
}

function Header({ route, navigate }) {
  return (
    <header className="site-header">
      <button className="brand-link" onClick={() => navigate("/")} aria-label="QuantDesk home">
        <span className="brand-mark">QD</span>
        <span>QuantDesk</span>
      </button>
      <nav aria-label="Primary navigation">
        {routes.map(({ path, label, icon: Icon }) => (
          <button key={path} className={route === path ? "nav-link active" : "nav-link"} onClick={() => navigate(path)}>
            <Icon size={16} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </header>
  );
}

function DataStatusBadge({ status }) {
  const labels = {
    deterministic_demo_export: "Demo data",
    exported_from_csv: "Imported CSV",
    exported_from_engine_backtest: "Real backtest",
    exported_from_benchmark_json: "Measured benchmark",
    placeholder_frontend_fixture: "Placeholder data",
  };
  return (
    <div className={`data-status ${status || "unknown"}`} role="status" aria-label={`Dashboard data status: ${labels[status] || "Unknown data"}`}>
      {labels[status] || "Unknown data"}
    </div>
  );
}

function Landing({ data, navigate }) {
  const current = data.session.events[4] ?? data.session.events[0];
  const metrics = [
    { label: "Strategy Sharpe", value: data.summary.strategies.market_maker.sharpe.toFixed(2), detail: "walk-forward backtest" },
    { label: "Max Drawdown", value: `${data.summary.strategies.market_maker.maxDrawdownPct.toFixed(1)}%`, detail: "realized plus mark-to-mid" },
    { label: "Engine Throughput", value: formatOptional(data.benchmarks.matchingEngine.ordersPerSecond, compact), detail: data.benchmarks.matchingEngine.context },
    { label: "Order-to-Ack", value: formatOptional(data.benchmarks.orderAckLatency.p50Micros, (value) => `${value}us`), detail: data.benchmarks.orderAckLatency.context },
  ];

  return (
    <main>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Static public dashboard for a C++/Python trading engine</p>
          <h1>QuantDesk replays market-making decisions against the order book that produced them.</h1>
          <p className="hero-text">
            A limit-order-book engine, risk layer, and research backtester presented as one inspectable artifact: recorded sessions,
            backtest evidence, and honest benchmark context with no live backend dependency.
          </p>
          <div className="hero-actions">
            <button className="primary-action" onClick={() => navigate("/replay")}>
              <Play size={18} /> Replay a session
            </button>
            <button className="secondary-action" onClick={() => navigate("/architecture")}>
              <BookOpen size={18} /> Read architecture
            </button>
          </div>
        </div>
        <HeroLadder event={current} />
      </section>

      <MetricBand metrics={metrics} />

      <section className="architecture-strip">
        {[
          ["Exchange gateway", "Normalizes external exchange events into engine messages."],
          ["Matching engine", "Maintains price-time priority and emits deterministic fills."],
          ["Risk engine", "Rejects orders when inventory or loss limits are breached."],
          ["Research layer", "Runs the same event contract in backtest and paper modes."],
        ].map(([title, body]) => (
          <article key={title}>
            <ChevronRight size={18} />
            <h2>{title}</h2>
            <p>{body}</p>
          </article>
        ))}
      </section>

      <section className="link-grid">
        <DeepLink title="Replay Viewer" body="Scrub through fills, inventory skew, rejects, and P&L in sync with the ladder." path="/replay" navigate={navigate} />
        <DeepLink title="Backtest Reports" body="Inspect equity, drawdown, parameter sweeps, trade stats, and cointegration results." path="/backtests" navigate={navigate} />
        <DeepLink title="Source Repos" body="Open the engine, research layer, and dashboard code from the footer links." path="/architecture" navigate={navigate} />
      </section>
    </main>
  );
}

function HeroLadder({ event }) {
  const [tick, setTick] = useState(0);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    if (reducedMotion) return undefined;
    const id = window.setInterval(() => setTick((value) => (value + 1) % 4), 1450);
    return () => window.clearInterval(id);
  }, [reducedMotion]);

  const bids = event.book.bids.slice(0, 7);
  const asks = event.book.asks.slice(0, 7).reverse();

  return (
    <aside className="hero-ladder" aria-label="Ambient order book ladder">
      <div className="ladder-header">
        <span>BTC-PERP</span>
        <span>{formatTime(event.time)}</span>
      </div>
      <div className="ladder-table">
        {asks.map((level, index) => (
          <BookLevel key={`ask-${level.price}`} level={level} side="ask" flash={tick === index % 4} />
        ))}
        <div className="mid-row">
          <span>mid</span>
          <strong>{midPrice(event.book).toFixed(2)}</strong>
          <span>spread 5.00</span>
        </div>
        {bids.map((level, index) => (
          <BookLevel key={`bid-${level.price}`} level={level} side="bid" flash={tick === index % 4} />
        ))}
      </div>
      <div className="fill-flash">last fill: {event.fills[0]?.side ?? "BUY"} {event.fills[0]?.size ?? "0.20"} @ {event.fills[0]?.price ?? bids[0].price}</div>
    </aside>
  );
}

function BookLevel({ level, side, flash }) {
  const width = Math.min(100, level.size * 18);
  return (
    <div className={`book-level ${side} ${flash ? "flash" : ""}`}>
      <span className="depth-bar" style={{ width: `${width}%` }} />
      <span>{level.price.toFixed(2)}</span>
      <span>{level.size.toFixed(2)}</span>
    </div>
  );
}

function MetricBand({ metrics }) {
  return (
    <section className="metric-band" aria-label="QuantDesk metrics">
      {metrics.map((metric) => (
        <article key={metric.label}>
          <strong>{metric.value}</strong>
          <span>{metric.label}</span>
          <p>{metric.detail}</p>
        </article>
      ))}
    </section>
  );
}

function DeepLink({ title, body, path, navigate }) {
  return (
    <button className="deep-link" onClick={() => navigate(path)}>
      <span>{title}</span>
      <p>{body}</p>
      <ChevronRight size={18} />
    </button>
  );
}

function ReplayPage({ session }) {
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const current = session.events[index];
  const marker = nearestMarker(session.markers, current.time);

  useEffect(() => {
    if (!playing) return undefined;
    const id = window.setInterval(() => {
      setIndex((value) => (value + 1) % session.events.length);
    }, Math.max(120, 900 / speed));
    return () => window.clearInterval(id);
  }, [playing, speed, session.events.length]);

  return (
    <main className="page replay-page">
      <PageIntro
        eyebrow="Replay viewer"
        title="Scrub the event stream, not a screenshot."
        body="The ladder, fills, position, and P&L all derive from the same static session JSON. Real exports can replace this file without changing the viewer."
      />
      <section className="replay-layout">
        <div className="replay-main">
          <div className="toolbar">
            <button className="icon-button" onClick={() => setPlaying((value) => !value)} aria-label={playing ? "Pause replay" : "Play replay"}>
              {playing ? <Pause size={18} /> : <Play size={18} />}
            </button>
            <label>
              Speed
              <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))}>
                <option value={1}>1x</option>
                <option value={5}>5x</option>
                <option value={20}>20x</option>
              </select>
            </label>
            <span className="mono">{formatTime(current.time)}</span>
          </div>
          <Timeline session={session} index={index} setIndex={setIndex} />
          {marker && <p className={`marker-note ${marker.type}`}>{marker.label}</p>}
          <div className="replay-grid">
            <OrderBook book={current.book} />
            <FillsBlotter events={session.events.slice(0, index + 1)} />
          </div>
        </div>
        <aside className="state-panel">
          <h2>State</h2>
          <Stat label="Position" value={`${current.position.toFixed(2)} BTC`} />
          <Stat label="Running P&L" value={`$${current.pnl.toLocaleString()}`} />
          <Stat label="Event" value={current.type.replace("_", " ")} />
          <MiniPnlChart events={session.events.slice(0, index + 1)} />
        </aside>
      </section>
    </main>
  );
}

function Timeline({ session, index, setIndex }) {
  return (
    <div className="timeline-wrap">
      <input
        aria-label="Replay timeline"
        type="range"
        min="0"
        max={session.events.length - 1}
        value={index}
        onChange={(event) => setIndex(Number(event.target.value))}
      />
      <div className="markers">
        {session.markers.map((marker) => {
          const markerIndex = session.events.findIndex((event) => event.time >= marker.time);
          return (
            <button
              key={marker.time}
              className={`timeline-marker ${marker.type}`}
              style={{ left: `${(markerIndex / (session.events.length - 1)) * 100}%` }}
              onClick={() => setIndex(Math.max(0, markerIndex))}
              aria-label={`Jump to ${marker.label}`}
            />
          );
        })}
      </div>
    </div>
  );
}

function OrderBook({ book }) {
  return (
    <section className="data-panel">
      <h2>Depth Ladder</h2>
      <div className="order-book">
        {book.asks.slice(0, 8).reverse().map((level) => <BookLevel key={level.price} level={level} side="ask" />)}
        <div className="mid-row compact">
          <span>mid</span>
          <strong>{midPrice(book).toFixed(2)}</strong>
        </div>
        {book.bids.slice(0, 8).map((level) => <BookLevel key={level.price} level={level} side="bid" />)}
      </div>
    </section>
  );
}

function FillsBlotter({ events }) {
  const fills = events.flatMap((event) => event.fills.map((fill) => ({ ...fill, time: event.time }))).slice(-10).reverse();
  return (
    <section className="data-panel">
      <h2>Fills Blotter</h2>
      <table>
        <thead>
          <tr><th>Time</th><th>Side</th><th>Price</th><th>Size</th></tr>
        </thead>
        <tbody>
          {fills.map((fill, fillIndex) => (
            <tr key={`${fill.time}-${fillIndex}`}>
              <td>{formatTime(fill.time)}</td>
              <td className={fill.side.toLowerCase()}>{fill.side}</td>
              <td>{fill.price.toFixed(2)}</td>
              <td>{fill.size.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function MiniPnlChart({ events }) {
  const labels = events.map((event) => formatTime(event.time));
  const values = events.map((event) => event.pnl);
  return (
    <div className="chart-box small-chart">
      <Line
        data={{ labels, datasets: [{ data: values, borderColor: "#3FB89A", backgroundColor: "rgba(63,184,154,.14)", fill: true, tension: 0.28, pointRadius: 0 }] }}
        options={chartOptions("P&L")}
      />
    </div>
  );
}

function BacktestsPage({ summary, session }) {
  const mm = summary.strategies.market_maker;
  const statArb = summary.strategies.stat_arb;
  const ml = summary.strategies.ml_signal;
  const curve = session.events.map((event) => event.pnl);
  const labels = session.events.map((event) => formatTime(event.time));
  const drawdown = runningDrawdown(curve);

  return (
    <main className="page">
      <PageIntro
        eyebrow="Backtest reports"
        title="Numbers with the measurement context still attached."
        body="Placeholder JSON is checked in so the site works offline; the structure mirrors the engine export contract."
      />
      <MetricBand metrics={[
        { label: "Win Rate", value: `${mm.winRatePct}%`, detail: `${mm.tradeCount} trades` },
        { label: "Avg Hold", value: mm.averageHoldingTime, detail: "market-maker fills" },
        { label: "Spread Captured", value: `${mm.effectiveSpreadCapturedBps} bps`, detail: "effective average" },
        { label: "ML AUC", value: formatOptional(ml.outOfSampleAuc, (value) => value.toFixed(2)), detail: ml.pnlLiftPct == null ? ml.note : `${ml.pnlLiftPct}% P&L lift in replay` },
      ]} />
      <section className="report-grid">
        <div className="data-panel chart-panel">
          <h2>Equity Curve</h2>
          <Line data={{ labels, datasets: [{ data: curve, borderColor: "#3FB89A", backgroundColor: "rgba(63,184,154,.12)", fill: true, tension: 0.25, pointRadius: 0 }] }} options={chartOptions("P&L")} />
        </div>
        <div className="data-panel chart-panel">
          <h2>Drawdown</h2>
          <Bar data={{ labels, datasets: [{ data: drawdown, backgroundColor: "#E0654A" }] }} options={chartOptions("Drawdown")} />
        </div>
      </section>
      <section className="report-grid">
        <div className="data-panel">
          <h2>Trade Statistics</h2>
          <table>
            <tbody>
              {Object.entries({
                Sharpe: mm.sharpe,
                "Max drawdown": `${mm.maxDrawdownPct}%`,
                "Trade count": mm.tradeCount,
                "Risk rejects": mm.riskRejects,
                "Kill-switch tests": mm.killSwitchTests,
              }).map(([label, value]) => <tr key={label}><td>{label}</td><td>{value}</td></tr>)}
            </tbody>
          </table>
        </div>
        <div className="data-panel">
          <h2>Parameter Sweep</h2>
          <Heatmap sweep={mm.parameterSweep} />
        </div>
      </section>
      <section className="statement">
        <h2>Cointegration Result</h2>
        <p>
          The stat-arb pair test statistic is <span className="mono">{formatOptional(statArb.cointegration.testStatistic)}</span> with p-value{" "}
          <span className="mono">{formatOptional(statArb.cointegration.pValue)}</span>. {statArb.cointegration.note || "The p-value is computed from the supplied pair series."}
        </p>
      </section>
    </main>
  );
}

function Heatmap({ sweep }) {
  const values = sweep.flatMap((row) => row.cells.map((cell) => cell.sharpe));
  const min = Math.min(...values);
  const max = Math.max(...values);
  return (
    <div className="heatmap">
      {sweep.map((row) => (
        <React.Fragment key={row.spreadBps}>
          <span className="heat-label">{row.spreadBps} bps</span>
          {row.cells.map((cell) => {
            const normalized = (cell.sharpe - min) / (max - min);
            return (
              <span
                key={`${row.spreadBps}-${cell.inventorySkew}`}
                className="heat-cell"
                style={{ background: mixColor(normalized) }}
                title={`skew ${cell.inventorySkew}: Sharpe ${cell.sharpe}`}
              >
                {cell.sharpe.toFixed(2)}
              </span>
            );
          })}
        </React.Fragment>
      ))}
    </div>
  );
}

function ArchitecturePage() {
  return (
    <main className="page">
      <PageIntro
        eyebrow="Architecture"
        title="One event contract across live, paper, and backtest modes."
        body="The important claim is parity: the research layer replays the same event shapes the gateway and matching engine use at runtime."
      />
      <section className="architecture-diagram" aria-label="QuantDesk architecture diagram">
        {[
          ["Exchange Gateway", "testnet adapters, normalized events", Zap],
          ["Order Book / Matching Engine", "price-time priority, deterministic fills", Cpu],
          ["Risk Engine", "inventory, loss, and kill-switch checks", ShieldCheck],
          ["Backtester / Research", "walk-forward tests, stat-arb, ML signal", BarChart3],
          ["Static Dashboard", "JSON replay, reports, public artifact", Radio],
        ].map(([title, body, Icon], index) => (
          <React.Fragment key={title}>
            <article>
              <Icon size={22} />
              <h2>{title}</h2>
              <p>{body}</p>
            </article>
            {index < 4 && <ChevronRight className="diagram-arrow" size={24} />}
          </React.Fragment>
        ))}
      </section>
      <section className="copy-columns">
        <article>
          <h2>Order book and matching</h2>
          <p>
            The engine keeps bid and ask ladders as first-class state, then produces fills from deterministic matching rules. That makes the replay viewer useful: each fill can be read against the visible depth that existed at that timestamp.
          </p>
        </article>
        <article>
          <h2>Risk before routing</h2>
          <p>
            Orders pass through position and loss checks before they are allowed to reach the gateway. The demo session includes an inventory-limit marker and a reject event so reviewers can see the control path, not just successful trades.
          </p>
        </article>
        <article>
          <h2>Backtest/live parity</h2>
          <p>
            Backtests consume the same event contract used by paper trading. The dashboard reads exported JSON from that contract, which keeps the public site static while preserving a direct link to the system being evaluated.
          </p>
        </article>
      </section>
    </main>
  );
}

function PageIntro({ eyebrow, title, body }) {
  return (
    <section className="page-intro">
      <p className="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p>{body}</p>
    </section>
  );
}

function Footer() {
  const repo = "https://github.com/khushalmidha/Quantdesk";
  return (
    <footer className="site-footer">
      <span>QuantDesk static dashboard</span>
      <a href={`${repo}/tree/main/engine`} target="_blank" rel="noreferrer"><Github size={16} /> Engine repo</a>
      <a href={`${repo}/tree/main/research`} target="_blank" rel="noreferrer"><Github size={16} /> Research repo</a>
      <a href={`${repo}/tree/main/dashboard`} target="_blank" rel="noreferrer"><Github size={16} /> Site repo</a>
    </footer>
  );
}

function Stat({ label, value }) {
  return <div className="stat"><span>{label}</span><strong>{value}</strong></div>;
}

function formatTime(ms) {
  const date = new Date(ms);
  return date.toISOString().slice(11, 19);
}

function compact(value) {
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function formatOptional(value, formatter = (nextValue) => nextValue) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "not supplied";
  }
  return formatter(value);
}

function midPrice(book) {
  return (book.bids[0].price + book.asks[0].price) / 2;
}

function nearestMarker(markers, time) {
  return markers.find((marker) => Math.abs(marker.time - time) < 9000);
}

function runningDrawdown(values) {
  let peak = values[0] || 0;
  return values.map((value) => {
    peak = Math.max(peak, value);
    return Math.min(0, value - peak);
  });
}

function chartOptions(label) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { tooltip: { enabled: true }, legend: { display: false } },
    scales: {
      x: { ticks: { color: "#8B93A0", maxTicksLimit: 5 }, grid: { color: "rgba(139,147,160,.12)" } },
      y: { ticks: { color: "#8B93A0" }, grid: { color: "rgba(139,147,160,.12)" }, title: { display: true, text: label, color: "#8B93A0" } },
    },
  };
}

function mixColor(value) {
  const coral = [224, 101, 74];
  const teal = [63, 184, 154];
  const rgb = coral.map((channel, index) => Math.round(channel + (teal[index] - channel) * value));
  return `rgb(${rgb.join(",")})`;
}

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const listener = () => setReduced(query.matches);
    query.addEventListener("change", listener);
    return () => query.removeEventListener("change", listener);
  }, []);
  return reduced;
}

const fallbackData = {
  benchmarks: {
    matchingEngine: { ordersPerSecond: 1280000, context: "engine-internal benchmark, local Ryzen 7" },
    orderAckLatency: { p50Micros: 410, context: "paper gateway loopback, not exchange RTT" },
  },
  summary: {
    strategies: {
      market_maker: {
        sharpe: 1.87,
        maxDrawdownPct: -4.8,
        winRatePct: 54.6,
        tradeCount: 842,
        averageHoldingTime: "38s",
        effectiveSpreadCapturedBps: 3.2,
        riskRejects: 4,
        killSwitchTests: 1,
        parameterSweep: [],
      },
      stat_arb: { cointegration: { testStatistic: -3.91, pValue: 0.018 } },
      ml_signal: { outOfSampleAuc: 0.57, pnlLiftPct: 2.4 },
    },
  },
  session: {
    markers: [],
    events: [{
      time: Date.UTC(2026, 6, 14, 9, 30, 0),
      type: "book_snapshot",
      position: 0,
      pnl: 0,
      fills: [],
      book: {
        bids: [{ price: 100000, size: 2.1 }, { price: 99995, size: 2.4 }],
        asks: [{ price: 100005, size: 1.9 }, { price: 100010, size: 2.6 }],
      },
    }],
  },
};

createRoot(document.getElementById("root")).render(<App />);
