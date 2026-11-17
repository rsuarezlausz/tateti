import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { MetricsPanel, formatCost, formatLatency } from "./MetricsPanel";
import { SidePanelTabs, type TabId } from "./SidePanelTabs";
import type { AgentSpec, MetricsSummary, UsageTotals } from "../types";

const agents: AgentSpec[] = [
  { id: "a", name: "Estratega", personality: "", skills: [], system_prompt: "", temperature: 0.4, color: "#2563eb", avatar: "🧠" },
  { id: "b", name: "Defensivo", personality: "", skills: [], system_prompt: "", temperature: 0.4, color: "#16a34a", avatar: "🛡️" },
];

const totals = (o: Partial<UsageTotals>): UsageTotals => ({
  calls: 0, failed_calls: 0, prompt_tokens: 0, completion_tokens: 0, total_tokens: 0,
  total_latency_ms: 0, avg_latency_ms: 0, total_cost: null, ...o,
});

const metrics: MetricsSummary = {
  agents: [
    { agent_id: "a", ...totals({ calls: 2, failed_calls: 1, total_tokens: 30, avg_latency_ms: 120, total_latency_ms: 240, total_cost: 0.0004 }) },
  ],
  total: totals({ calls: 2, failed_calls: 1, total_tokens: 30, avg_latency_ms: 120, total_latency_ms: 240, total_cost: 0.0004 }),
};

describe("MetricsPanel", () => {
  it("muestra una fila por agente del equipo y el total de la partida", () => {
    render(<MetricsPanel metrics={metrics} agents={agents} />);
    const a = within(screen.getByTestId("metrics-a"));
    expect(a.getByText("30")).toBeInTheDocument();
    expect(a.getByText("120 ms")).toBeInTheDocument();
    expect(a.getByText("$0.000400")).toBeInTheDocument();
    expect(a.getByText(/1 ✗/)).toBeInTheDocument();
    // agente sin llamadas: ceros y costo n/d
    expect(within(screen.getByTestId("metrics-b")).getByText("n/d")).toBeInTheDocument();
    expect(within(screen.getByTestId("metrics-total")).getByText("Total partida")).toBeInTheDocument();
  });

  it("sin métricas muestra un aviso y totales en cero", () => {
    render(<MetricsPanel metrics={null} agents={agents} />);
    expect(screen.getByText(/Aún no hay llamadas/)).toBeInTheDocument();
    expect(screen.getByTestId("metrics-total")).toBeInTheDocument();
  });

  it("formatea costo nulo sin inventarlo y latencias largas en segundos", () => {
    expect(formatCost(null)).toBe("n/d");
    expect(formatCost(0.5)).toBe("$0.500000");
    expect(formatLatency(1500)).toBe("1.50 s");
    expect(formatLatency(80.4)).toBe("80 ms");
  });
});

describe("SidePanelTabs", () => {
  function Harness() {
    const [tab, setTab] = useState<TabId>("chat");
    return (
      <>
        <SidePanelTabs active={tab} onChange={setTab} />
        <p>activa: {tab}</p>
      </>
    );
  }

  it("alterna entre Chat y Métricas", async () => {
    render(<Harness />);
    expect(screen.getByRole("tab", { name: "Chat" })).toHaveAttribute("aria-selected", "true");
    await userEvent.click(screen.getByRole("tab", { name: "Métricas" }));
    expect(screen.getByText("activa: metrics")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Métricas" })).toHaveAttribute("aria-selected", "true");
  });
});
