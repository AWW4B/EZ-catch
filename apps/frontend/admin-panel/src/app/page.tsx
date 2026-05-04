"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  Brain,
  Terminal,
  Wifi,
  WifiOff,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Zap,
} from "lucide-react";

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
  reasoning_context?: LLMReasoningContext;
  tool_calls?: Record<string, unknown>[];
}

interface TerminalEvent {
  id: number;
  timestamp: string;
  event_type: "terminal_action";
  command_executed: string;
  working_directory?: string;
  user?: string;
  parent_process?: string;
  exit_code?: number;
}

type AnyEvent = NetworkEvent | TerminalEvent;

function relativeTime(ts: string): string {
  const delta = Date.now() - new Date(ts).getTime();
  if (delta < 1000) return "just now";
  if (delta < 60000) return `${Math.floor(delta / 1000)}s ago`;
  if (delta < 3600000) return `${Math.floor(delta / 60000)}m ago`;
  return new Date(ts).toLocaleTimeString();
}

function ExpandableText({ label, text }: { label: string; text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {label}
      </button>
      {open && (
        <pre className="mt-1 p-2 bg-black/40 rounded text-xs text-slate-300 whitespace-pre-wrap break-all border border-slate-700 max-h-48 overflow-y-auto">
          {text}
        </pre>
      )}
    </div>
  );
}

function NetworkCard({ event }: { event: NetworkEvent }) {
  const rc = event.reasoning_context;
  const hasThinking = !!rc?.extracted_thinking;
  const hasTools = !!event.tool_calls?.length;

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/60 p-4 hover:border-emerald-700 transition-colors">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={`shrink-0 px-1.5 py-0.5 rounded text-xs font-mono font-bold ${
              event.method === "POST"
                ? "bg-emerald-900 text-emerald-300"
                : "bg-slate-700 text-slate-300"
            }`}
          >
            {event.method}
          </span>
          <span className="text-xs text-slate-300 font-mono truncate">
            {event.url}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {event.status_code && (
            <span
              className={`text-xs font-mono ${
                event.status_code < 300
                  ? "text-emerald-400"
                  : "text-red-400"
              }`}
            >
              {event.status_code}
            </span>
          )}
          <span className="text-xs text-slate-500">
            {relativeTime(event.timestamp)}
          </span>
        </div>
      </div>

      {rc?.target_llm && (
        <div className="mt-2 flex items-center gap-1.5">
          <Brain size={12} className="text-violet-400" />
          <span className="text-xs text-violet-400 font-mono">
            {rc.target_llm}
          </span>
        </div>
      )}

      {hasThinking && (
        <ExpandableText label="View extracted thinking" text={rc!.extracted_thinking!} />
      )}
      {rc?.prompt && (
        <ExpandableText label="View prompt" text={rc.prompt} />
      )}
      {hasTools && (
        <ExpandableText
          label={`${event.tool_calls!.length} tool call(s)`}
          text={JSON.stringify(event.tool_calls, null, 2)}
        />
      )}

      {!hasThinking && !hasTools && !rc?.prompt && (
        <p className="mt-2 text-xs text-slate-600 italic">
          No reasoning context captured
        </p>
      )}
    </div>
  );
}

function TerminalCard({ event }: { event: TerminalEvent }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/60 p-4 hover:border-cyan-700 transition-colors font-mono">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-emerald-400 shrink-0">$</span>
          <span className="text-sm text-slate-200 truncate">
            {event.command_executed}
          </span>
        </div>
        <span className="text-xs text-slate-500 shrink-0">
          {relativeTime(event.timestamp)}
        </span>
      </div>

      <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
        {event.working_directory && (
          <span title="cwd">
            <span className="text-slate-600">cwd:</span>{" "}
            <span className="text-cyan-600">{event.working_directory}</span>
          </span>
        )}
        {event.user && (
          <span>
            <span className="text-slate-600">user:</span>{" "}
            <span className="text-cyan-600">{event.user}</span>
          </span>
        )}
        {event.parent_process && (
          <span>
            <span className="text-slate-600">parent:</span>{" "}
            <span className="text-cyan-600">{event.parent_process}</span>
          </span>
        )}
        {event.exit_code !== undefined && event.exit_code !== null && (
          <span>
            <span className="text-slate-600">exit:</span>{" "}
            <span className={event.exit_code === 0 ? "text-emerald-500" : "text-red-500"}>
              {event.exit_code}
            </span>
          </span>
        )}
      </div>
    </div>
  );
}

function StatusPill({ connected }: { connected: boolean }) {
  return (
    <div
      className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border ${
        connected
          ? "bg-emerald-950 border-emerald-700 text-emerald-400"
          : "bg-red-950 border-red-800 text-red-400"
      }`}
    >
      {connected ? <Wifi size={12} /> : <WifiOff size={12} />}
      {connected ? "Backend connected" : "Backend unreachable"}
    </div>
  );
}

export default function Dashboard() {
  const [events, setEvents] = useState<AnyEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [lastPoll, setLastPoll] = useState<Date | null>(null);
  const [spinning, setSpinning] = useState(false);

  const fetchEvents = async () => {
    setSpinning(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/logs", {
        signal: AbortSignal.timeout(4000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: AnyEvent[] = await res.json();
      setEvents(data);
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

  const networkEvents = events.filter(
    (e): e is NetworkEvent => e.event_type === "network_intercept"
  );
  const terminalEvents = events.filter(
    (e): e is TerminalEvent => e.event_type === "terminal_action"
  );

  return (
    <div className="min-h-screen bg-zinc-950 text-slate-100">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-zinc-950/90 backdrop-blur">
        <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Zap size={20} className="text-emerald-400" />
              <span className="text-lg font-bold tracking-tight text-white">
                AgentMonitor
              </span>
            </div>
            <span className="hidden sm:inline text-xs text-slate-600 font-mono">
              bare-metal intercept
            </span>
          </div>

          <div className="flex items-center gap-4">
            <StatusPill connected={connected} />
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <RefreshCw
                size={12}
                className={spinning ? "animate-spin text-emerald-500" : ""}
              />
              {lastPoll ? `${relativeTime(lastPoll.toISOString())}` : "—"}
            </div>
          </div>
        </div>
      </header>

      {/* Stats bar */}
      <div className="border-b border-slate-800/60 bg-zinc-900/40">
        <div className="mx-auto max-w-7xl px-6 py-3 flex gap-6">
          {[
            { label: "Total Events", value: events.length, color: "text-white" },
            { label: "LLM Requests", value: networkEvents.length, color: "text-emerald-400" },
            { label: "Terminal Cmds", value: terminalEvents.length, color: "text-cyan-400" },
            {
              label: "With Reasoning",
              value: networkEvents.filter((e) => e.reasoning_context?.extracted_thinking).length,
              color: "text-violet-400",
            },
          ].map((s) => (
            <div key={s.label} className="flex flex-col">
              <span className={`text-xl font-bold font-mono ${s.color}`}>
                {s.value}
              </span>
              <span className="text-xs text-slate-600">{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Main grid */}
      <main className="mx-auto max-w-7xl px-6 py-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Network & Reasoning */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Brain size={16} className="text-emerald-400" />
            <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
              Network &amp; Reasoning
            </h2>
            <span className="ml-auto text-xs font-mono text-slate-600">
              {networkEvents.length} events
            </span>
          </div>

          <div className="flex flex-col gap-3">
            {loading && (
              <div className="flex items-center gap-2 py-12 justify-center text-slate-600 text-sm">
                <Activity size={16} className="animate-pulse" />
                Waiting for backend…
              </div>
            )}

            {!loading && !connected && (
              <div className="rounded-lg border border-red-900 bg-red-950/30 p-6 text-center text-sm text-red-400">
                Cannot reach{" "}
                <code className="font-mono text-xs">localhost:8000</code>.
                <br />
                <span className="text-red-600 text-xs mt-1 block">
                  Is the Docker backend running?
                </span>
              </div>
            )}

            {!loading && connected && networkEvents.length === 0 && (
              <div className="rounded-lg border border-slate-800 p-6 text-center text-sm text-slate-600">
                No network events yet.
                <br />
                <span className="text-xs mt-1 block">
                  Start mitmdump and trigger an LLM request.
                </span>
              </div>
            )}

            {networkEvents.map((e) => (
              <NetworkCard key={e.id} event={e} />
            ))}
          </div>
        </section>

        {/* Terminal Executions */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <Terminal size={16} className="text-cyan-400" />
            <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-400">
              Terminal Executions
            </h2>
            <span className="ml-auto text-xs font-mono text-slate-600">
              {terminalEvents.length} events
            </span>
          </div>

          <div className="flex flex-col gap-3">
            {loading && (
              <div className="flex items-center gap-2 py-12 justify-center text-slate-600 text-sm">
                <Activity size={16} className="animate-pulse" />
                Waiting for backend…
              </div>
            )}

            {!loading && connected && terminalEvents.length === 0 && (
              <div className="rounded-lg border border-slate-800 p-6 text-center text-sm text-slate-600">
                No terminal events yet.
                <br />
                <span className="text-xs mt-1 block">
                  Ensure auditd is running and the OS monitor has root access.
                </span>
              </div>
            )}

            {terminalEvents.map((e) => (
              <TerminalCard key={e.id} event={e} />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
