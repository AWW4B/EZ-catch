"use client";

import { useEffect, useRef, useState } from "react";
import {
  Activity, Brain, Terminal, Wifi, WifiOff, RefreshCw,
  ChevronDown, ChevronRight, Zap, Clock, Cpu, Network, Filter,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface LLMReasoningContext {
  prompt?: string;
  raw_response?: string;
  extracted_thinking?: string;
  target_llm?: string;
}

interface NetworkEvent {
  id: number;
  timestamp: string;
  event_type: "network_intercept";
  url: string;
  method: string;
  status_code?: number;
  duration_ms?: number;
  reasoning_context?: LLMReasoningContext;
  tool_calls?: Record<string, unknown>[];
  model?: string;
  prompt?: string;
  system_prompt?: string;
  reasoning?: string;
  response?: string;
}

interface TerminalEvent {
  id: number;
  timestamp: string;
  event_type: "terminal_action";
  command_executed: string;
  working_directory?: string;
  user?: string;
  parent_process?: string;
  pid?: number;
  exit_code?: number;
}

type AnyEvent = NetworkEvent | TerminalEvent;
type FilterType = "all" | "network" | "terminal";

// ─── Utilities ────────────────────────────────────────────────────────────────

function relativeTime(ts: string): string {
  const delta = Date.now() - new Date(ts).getTime();
  if (delta < 1000) return "just now";
  if (delta < 60000) return `${Math.floor(delta / 1000)}s ago`;
  if (delta < 3600000) return `${Math.floor(delta / 60000)}m ago`;
  return new Date(ts).toLocaleTimeString();
}

function isLive(ts: string, sessionStart: number): boolean {
  return new Date(ts).getTime() >= sessionStart;
}

function shortUrl(url: string): string {
  try {
    const u = new URL(url);
    return u.hostname + u.pathname;
  } catch {
    return url.length > 60 ? url.slice(0, 60) + "…" : url;
  }
}

// ─── Collapsible ──────────────────────────────────────────────────────────────

type ColVariant = "default" | "reasoning" | "response" | "prompt";

function Collapsible({ label, text, variant = "default" }: { label: string; text: string; variant?: ColVariant }) {
  const [open, setOpen] = useState(false);
  const styles: Record<ColVariant, { btn: string; pre: string }> = {
    default:   { btn: "text-slate-400 hover:text-slate-200",   pre: "bg-slate-900/60 border-slate-700 text-slate-300" },
    reasoning: { btn: "text-amber-400 hover:text-amber-300",   pre: "bg-amber-950/40 border-amber-800/60 text-amber-200" },
    response:  { btn: "text-sky-400 hover:text-sky-300",       pre: "bg-sky-950/40 border-sky-800/60 text-sky-100" },
    prompt:    { btn: "text-emerald-400 hover:text-emerald-300", pre: "bg-emerald-950/30 border-emerald-800/50 text-emerald-100" },
  };
  const s = styles[variant];
  return (
    <div className="mt-2">
      <button onClick={() => setOpen(v => !v)} className={`flex items-center gap-1.5 text-xs font-medium transition-colors ${s.btn}`}>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {label}
      </button>
      {open && (
        <pre className={`mt-1.5 p-3 rounded-md text-xs whitespace-pre-wrap break-all border max-h-56 overflow-y-auto leading-relaxed ${s.pre}`}>
          {text}
        </pre>
      )}
    </div>
  );
}

// ─── NetworkCard ──────────────────────────────────────────────────────────────

function NetworkCard({ event }: { event: NetworkEvent }) {
  const rc = event.reasoning_context;
  const model     = event.model     || rc?.target_llm;
  const prompt    = event.prompt    || rc?.prompt;
  const reasoning = event.reasoning || rc?.extracted_thinking;
  const response  = event.response  || rc?.raw_response;
  const hasTools  = !!event.tool_calls?.length;
  const hasData   = prompt || reasoning || response || hasTools;

  return (
    <div className="rounded-xl border border-slate-700/80 bg-gradient-to-br from-slate-800/70 to-slate-900/70 p-4 hover:border-emerald-700/70 transition-all duration-200 shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className={`shrink-0 px-2 py-0.5 rounded text-xs font-mono font-bold tracking-wide ${
            event.method === "POST"
              ? "bg-emerald-900/80 text-emerald-300 border border-emerald-700/50"
              : "bg-slate-700/80 text-slate-300 border border-slate-600/50"
          }`}>{event.method}</span>
          <span className="text-xs text-slate-400 font-mono truncate" title={event.url}>{shortUrl(event.url)}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {event.status_code && (
            <span className={`text-xs font-mono font-bold ${event.status_code < 300 ? "text-emerald-400" : "text-red-400"}`}>
              {event.status_code}
            </span>
          )}
          {event.duration_ms != null && (
            <span className="flex items-center gap-0.5 text-xs text-slate-500 font-mono">
              <Clock size={10} />
              {event.duration_ms < 1000 ? `${Math.round(event.duration_ms)}ms` : `${(event.duration_ms / 1000).toFixed(1)}s`}
            </span>
          )}
          <span className="text-xs text-slate-600">{relativeTime(event.timestamp)}</span>
        </div>
      </div>

      {model && (
        <div className="mt-2.5 flex items-center gap-1.5">
          <Brain size={12} className="text-violet-400 shrink-0" />
          <span className="text-xs text-violet-300 font-mono font-semibold">{model}</span>
          <span className="ml-1 px-1.5 py-px rounded-full text-[10px] bg-violet-900/50 border border-violet-700/40 text-violet-400">LLM</span>
        </div>
      )}

      {hasData ? (
        <div className="mt-2 space-y-0.5">
          {prompt    && <Collapsible label={`User prompt (${prompt.length} chars)`}      text={prompt}    variant="prompt" />}
          {reasoning && <Collapsible label={`AI reasoning (${reasoning.length} chars)`}  text={reasoning} variant="reasoning" />}
          {response  && <Collapsible label={`AI response (${response.length} chars)`}    text={response}  variant="response" />}
          {hasTools  && <Collapsible label={`${event.tool_calls!.length} tool call(s)`}  text={JSON.stringify(event.tool_calls, null, 2)} />}
        </div>
      ) : (
        <p className="mt-2 text-xs text-slate-600 italic">No LLM context captured</p>
      )}
    </div>
  );
}

// ─── TerminalCard ─────────────────────────────────────────────────────────────

function TerminalCard({ event, sessionStart }: { event: TerminalEvent; sessionStart: number }) {
  const live = isLive(event.timestamp, sessionStart);
  return (
    <div className="rounded-xl border border-slate-700/60 bg-gradient-to-br from-zinc-900/90 to-slate-900/80 p-3.5 hover:border-cyan-700/60 transition-all duration-200 font-mono shadow-md">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 min-w-0 flex-1">
          <span className="text-emerald-400 shrink-0 mt-0.5 font-bold select-none">$</span>
          <span className="text-sm text-slate-100 break-all leading-relaxed">{event.command_executed}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0 mt-0.5">
          {live && (
            <span className="flex items-center gap-1 px-1.5 py-px rounded-full text-[10px] font-sans font-semibold bg-emerald-900/60 border border-emerald-600/50 text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              LIVE
            </span>
          )}
          <span className="text-xs text-slate-600">{relativeTime(event.timestamp)}</span>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        {event.pid            && <span className="flex items-center gap-1"><Cpu size={10} className="text-slate-600" /><span className="text-slate-600">pid:</span><span className="text-cyan-600/80">{event.pid}</span></span>}
        {event.user           && <span><span className="text-slate-600">user:</span> <span className="text-cyan-500/80">{event.user}</span></span>}
        {event.parent_process && <span><span className="text-slate-600">parent:</span> <span className="text-cyan-500/80">{event.parent_process}</span></span>}
        {event.working_directory && <span className="flex items-center gap-1 min-w-0"><span className="text-slate-600 shrink-0">cwd:</span> <span className="text-cyan-600/70 truncate">{event.working_directory}</span></span>}
        {event.exit_code !== undefined && event.exit_code !== null && (
          <span><span className="text-slate-600">exit:</span> <span className={event.exit_code === 0 ? "text-emerald-500/80" : "text-red-500/80"}>{event.exit_code}</span></span>
        )}
      </div>
    </div>
  );
}

// ─── StatusPill ───────────────────────────────────────────────────────────────

function StatusPill({ connected }: { connected: boolean }) {
  return (
    <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
      connected ? "bg-emerald-950/80 border-emerald-700/60 text-emerald-400" : "bg-red-950/80 border-red-800/60 text-red-400"
    }`}>
      {connected ? <Wifi size={11} /> : <WifiOff size={11} />}
      {connected ? "Connected" : "Unreachable"}
    </div>
  );
}

// ─── FilterBar ────────────────────────────────────────────────────────────────

function FilterBar({ active, onChange, counts }: {
  active: FilterType;
  onChange: (f: FilterType) => void;
  counts: { all: number; network: number; terminal: number };
}) {
  const opts: { key: FilterType; label: string; count: number; color: string }[] = [
    { key: "all",      label: "All",      count: counts.all,      color: "text-white" },
    { key: "network",  label: "Network",  count: counts.network,  color: "text-emerald-400" },
    { key: "terminal", label: "Terminal", count: counts.terminal, color: "text-cyan-400" },
  ];
  return (
    <div className="flex items-center gap-1 bg-slate-900/60 border border-slate-700/50 rounded-lg p-1">
      <Filter size={11} className="text-slate-600 ml-1 mr-0.5" />
      {opts.map(o => (
        <button
          key={o.key}
          id={`filter-${o.key}`}
          onClick={() => onChange(o.key)}
          className={`px-3 py-1 rounded-md text-xs font-medium transition-all duration-150 ${
            active === o.key ? "bg-slate-700 text-white shadow-sm" : "text-slate-500 hover:text-slate-300"
          }`}
        >
          {o.label}<span className={`ml-1.5 font-mono font-bold ${o.color}`}>{o.count}</span>
        </button>
      ))}
    </div>
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [events, setEvents]       = useState<AnyEvent[]>([]);
  const [loading, setLoading]     = useState(true);
  const [connected, setConnected] = useState(false);
  const [lastPoll, setLastPoll]   = useState<Date | null>(null);
  const [spinning, setSpinning]   = useState(false);
  const [filter, setFilter]       = useState<FilterType>("all");
  const sessionStart              = useRef(Date.now());

  const fetchEvents = async () => {
    setSpinning(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/logs", { signal: AbortSignal.timeout(4000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setEvents(await res.json());
      setConnected(true);
    } catch {
      setConnected(false);
    } finally {
      setLoading(false);
      setLastPoll(new Date());
      setTimeout(() => setSpinning(false), 400);
    }
  };

  useEffect(() => {
    fetchEvents();
    const id = setInterval(fetchEvents, 2000);
    return () => clearInterval(id);
  }, []);

  const networkEvents  = events.filter((e): e is NetworkEvent  => e.event_type === "network_intercept");
  const terminalEvents = events.filter((e): e is TerminalEvent => e.event_type === "terminal_action");
  const thinkingCount  = networkEvents.filter(e => e.reasoning || e.reasoning_context?.extracted_thinking).length;
  const modelSet       = new Set(networkEvents.map(e => e.model || e.reasoning_context?.target_llm).filter(Boolean));

  return (
    <div className="min-h-screen bg-zinc-950 text-slate-100">
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap'); body{font-family:'Inter',sans-serif;} code,pre,.font-mono{font-family:'JetBrains Mono',monospace;}`}</style>

      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-slate-800/80 bg-zinc-950/95 backdrop-blur-sm">
        <div className="mx-auto max-w-7xl px-6 py-3.5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-lg shadow-emerald-900/50">
                <Zap size={14} className="text-white" />
              </div>
              <span className="text-base font-bold tracking-tight text-white">EZ-catch</span>
            </div>
            <span className="hidden sm:inline text-xs text-slate-600 font-mono border border-slate-800 px-2 py-0.5 rounded">agent monitor</span>
          </div>
          <div className="flex items-center gap-3">
            <StatusPill connected={connected} />
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <RefreshCw size={11} className={spinning ? "animate-spin text-emerald-500" : ""} />
              <span>{lastPoll ? relativeTime(lastPoll.toISOString()) : "—"}</span>
            </div>
          </div>
        </div>
      </header>

      {/* Stats bar */}
      <div className="border-b border-slate-800/50 bg-zinc-900/30">
        <div className="mx-auto max-w-7xl px-6 py-3 flex gap-8 overflow-x-auto">
          {[
            { label: "Total Events",   value: events.length,         color: "text-white",       icon: <Activity size={13} /> },
            { label: "LLM Requests",   value: networkEvents.length,  color: "text-emerald-400", icon: <Network  size={13} /> },
            { label: "Terminal Cmds",  value: terminalEvents.length, color: "text-cyan-400",    icon: <Terminal size={13} /> },
            { label: "With Reasoning", value: thinkingCount,         color: "text-amber-400",   icon: <Brain    size={13} /> },
            { label: "Models Seen",    value: modelSet.size,         color: "text-violet-400",  icon: <Cpu      size={13} /> },
          ].map(s => (
            <div key={s.label} className="flex items-center gap-2.5 shrink-0">
              <span className={`${s.color} opacity-60`}>{s.icon}</span>
              <div className="flex flex-col">
                <span className={`text-lg font-bold font-mono leading-tight ${s.color}`}>{s.value}</span>
                <span className="text-[11px] text-slate-600 whitespace-nowrap">{s.label}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Filter bar */}
      <div className="mx-auto max-w-7xl px-6 pt-5 pb-1 flex items-center justify-between">
        <FilterBar active={filter} onChange={setFilter} counts={{ all: events.length, network: networkEvents.length, terminal: terminalEvents.length }} />
        <span className="text-xs text-slate-600 font-mono">{events.length} total events</span>
      </div>

      {/* Main grid */}
      <main className="mx-auto max-w-7xl px-6 py-5 grid grid-cols-1 lg:grid-cols-2 gap-6">

        {filter !== "terminal" && (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <Brain size={15} className="text-emerald-400" />
              <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">Network &amp; LLM</h2>
              <span className="ml-auto text-xs font-mono text-slate-600">{networkEvents.length} events</span>
            </div>
            <div className="flex flex-col gap-3">
              {loading && <div className="flex items-center gap-2 py-16 justify-center text-slate-600 text-sm"><Activity size={15} className="animate-pulse" />Waiting for backend…</div>}
              {!loading && !connected && (
                <div className="rounded-xl border border-red-900/60 bg-red-950/20 p-6 text-center text-sm text-red-400">
                  Cannot reach <code className="font-mono text-xs bg-red-900/40 px-1.5 py-0.5 rounded">localhost:8000</code>
                  <br /><span className="text-red-600 text-xs mt-1.5 block">Start the FastAPI backend first.</span>
                </div>
              )}
              {!loading && connected && networkEvents.length === 0 && (
                <div className="rounded-xl border border-slate-800 p-6 text-center text-sm text-slate-600">
                  No network events yet.<br /><span className="text-xs mt-1 block">Trigger an LLM request through the transparent proxy.</span>
                </div>
              )}
              {networkEvents.map(e => <NetworkCard key={e.id} event={e} />)}
            </div>
          </section>
        )}

        {filter !== "network" && (
          <section className={filter === "terminal" ? "lg:col-span-2" : ""}>
            <div className="flex items-center gap-2 mb-4">
              <Terminal size={15} className="text-cyan-400" />
              <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400">Terminal Executions</h2>
              <span className="ml-auto text-xs font-mono text-slate-600">{terminalEvents.length} events</span>
            </div>
            <div className="flex flex-col gap-2.5">
              {loading && <div className="flex items-center gap-2 py-16 justify-center text-slate-600 text-sm"><Activity size={15} className="animate-pulse" />Waiting for backend…</div>}
              {!loading && connected && terminalEvents.length === 0 && (
                <div className="rounded-xl border border-slate-800 p-6 text-center text-sm text-slate-600">
                  No terminal events yet.<br /><span className="text-xs mt-1 block">Ensure auditd is running and the agent has root access.</span>
                </div>
              )}
              {terminalEvents.map(e => <TerminalCard key={e.id} event={e} sessionStart={sessionStart.current} />)}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
