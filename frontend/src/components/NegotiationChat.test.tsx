import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NegotiationChat } from "./NegotiationChat";
import { decisionText } from "./DecisionBanner";
import type { AgentSpec, ChatItem } from "../types";

const agents: AgentSpec[] = [
  { id: "a", name: "Estratega", personality: "Piensa", skills: [], system_prompt: "", temperature: 0.4, color: "#2563eb", avatar: "🧠" },
];

const items: ChatItem[] = [
  { kind: "round", id: "1", round: 1 },
  { kind: "message", id: "2", round: 1, agentId: "a", message: "Tomo el centro", move: 14, coord: "C3", confidence: 0.8 },
  { kind: "error", id: "3", round: 1, agentId: "a", reason: "JSON inválido" },
  { kind: "decision", id: "4", decision: "consensus", move: 14, coord: "C3", round: 1 },
];

describe("NegotiationChat", () => {
  it("muestra burbuja con nombre, coordenada, confianza, ronda y banner de decisión", () => {
    render(<NegotiationChat items={items} agents={agents} thinkingAgentId={null} onHoverCell={vi.fn()} />);
    expect(screen.getByText("Estratega")).toBeInTheDocument();
    expect(screen.getByText("Propone C3")).toBeInTheDocument();
    expect(screen.getByText("Confianza 80%")).toBeInTheDocument();
    expect(screen.getByText(/Ronda 1/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("no cuenta como voto");
    expect(screen.getByRole("note")).toHaveTextContent("Consenso en la ronda 1");
  });

  it("muestra el indicador de escritura", () => {
    render(<NegotiationChat items={[]} agents={agents} thinkingAgentId="a" onHoverCell={vi.fn()} />);
    expect(screen.getByTestId("typing")).toHaveTextContent("Estratega está escribiendo…");
  });

  it("resalta en el tablero la celda de la burbuja al pasar el mouse", async () => {
    const onHover = vi.fn();
    render(<NegotiationChat items={items} agents={agents} thinkingAgentId={null} onHoverCell={onHover} />);
    const bubble = screen.getByTestId("agent-message");
    await userEvent.hover(bubble);
    expect(onHover).toHaveBeenLastCalledWith(14);
    await userEvent.unhover(bubble);
    expect(onHover).toHaveBeenLastCalledWith(null);
  });
});

describe("decisionText", () => {
  const base = { kind: "decision", id: "x", move: 1, coord: "B1" } as const;
  it("distingue sorteo real, mayoría y fallback", () => {
    expect(decisionText({ ...base, decision: "tiebreak", drawn: true, candidateCoords: ["A1", "B1"] })).toContain("sorteo");
    expect(decisionText({ ...base, decision: "tiebreak", drawn: false })).not.toContain("sorteo");
    expect(decisionText({ ...base, decision: "fallback", reason: "Nadie votó" })).toContain("Nadie votó");
  });
});
