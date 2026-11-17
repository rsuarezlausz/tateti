import type { AgentSpec, MetricsSummary, UsageTotals } from "../types";

interface Props {
  metrics: MetricsSummary | null;
  agents: AgentSpec[];
}

export function formatCost(cost: number | null): string {
  return cost === null ? "n/d" : `$${cost.toFixed(6)}`;
}

export function formatLatency(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${Math.round(ms)} ms`;
}

const EMPTY: UsageTotals = {
  calls: 0,
  failed_calls: 0,
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0,
  total_latency_ms: 0,
  avg_latency_ms: 0,
  total_cost: null,
};

function Cells({ t }: { t: UsageTotals }) {
  return (
    <>
      <td className="whitespace-nowrap px-1.5 py-1.5 text-right">
        {t.calls}
        {t.failed_calls > 0 && (
          <span className="text-rose-600" title="Llamadas inválidas o con jugada ilegal">
            {" "}
            ({t.failed_calls} ✗)
          </span>
        )}
      </td>
      <td className="whitespace-nowrap px-1.5 py-1.5 text-right" title={`${t.prompt_tokens} prompt + ${t.completion_tokens} respuesta`}>
        {t.total_tokens}
      </td>
      <td className="whitespace-nowrap px-1.5 py-1.5 text-right">{formatLatency(t.avg_latency_ms)}</td>
      <td className="whitespace-nowrap px-1.5 py-1.5 text-right">{formatLatency(t.total_latency_ms)}</td>
      <td className="whitespace-nowrap px-1.5 py-1.5 text-right">{formatCost(t.total_cost)}</td>
    </>
  );
}

export function MetricsPanel({ metrics, agents }: Props) {
  const byAgent = new Map(metrics?.agents.map((m) => [m.agent_id, m]));
  return (
    <div aria-label="Métricas de la partida" className="overflow-x-auto rounded-lg bg-slate-50 p-2 lg:min-h-[34rem]">
      {!metrics || metrics.total.calls === 0 ? (
        <p className="py-6 text-center text-sm text-slate-500">
          Aún no hay llamadas al LLM. Las métricas aparecerán en vivo durante la negociación.
        </p>
      ) : null}
      <table className="mt-2 w-full text-xs">
        <thead>
          <tr className="border-b border-slate-300 text-xs uppercase text-slate-500">
            <th className="px-1.5 py-1.5 text-left">Agente</th>
            <th className="px-1.5 py-1.5 text-right">Llamadas</th>
            <th className="px-1.5 py-1.5 text-right">Tokens</th>
            <th className="px-1.5 py-1.5 text-right">Lat. prom.</th>
            <th className="px-1.5 py-1.5 text-right">Lat. total</th>
            <th className="px-1.5 py-1.5 text-right">Costo</th>
          </tr>
        </thead>
        <tbody>
          {agents.map((a) => (
            <tr key={a.id} className="border-b border-slate-200" data-testid={`metrics-${a.id}`}>
              <td className="px-1.5 py-1.5 font-semibold" style={{ color: a.color }}>
                <span aria-hidden>{a.avatar}</span> {a.name}
              </td>
              <Cells t={byAgent.get(a.id) ?? EMPTY} />
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="font-bold" data-testid="metrics-total">
            <td className="px-1.5 py-1.5 text-left">Total partida</td>
            <Cells t={metrics?.total ?? EMPTY} />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

