import { useState } from "react";
import type { StartingPlayer } from "./api/client";
import { AgentCountSelector } from "./components/AgentCountSelector";
import { Board } from "./components/Board";
import { GameStatus } from "./components/GameStatus";
import { MetricsPanel } from "./components/MetricsPanel";
import { NegotiationChat } from "./components/NegotiationChat";
import { SidePanelTabs, type TabId } from "./components/SidePanelTabs";
import { useGameStream } from "./hooks/useGameStream";

export default function App() {
  const { state, startGame, play, retry } = useGameStream();
  const [numAgents, setNumAgents] = useState(3);
  const [startingPlayer, setStartingPlayer] = useState<StartingPlayer>("human");
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const [tab, setTab] = useState<TabId>("chat");
  const hasGame = state.gameId !== null;
  const locked = state.busy || state.loading;

  return (
    <div className="mx-auto max-w-6xl p-4">
      <h1 className="mb-4 text-2xl font-extrabold">TicTacToe Agent Factory</h1>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,28rem)]">
        <section className="flex flex-col gap-4" aria-label="Partida">
          <AgentCountSelector
            value={numAgents}
            disabled={locked}
            onChange={setNumAgents}
            startingPlayer={startingPlayer}
            onStartingPlayerChange={setStartingPlayer}
            onNewGame={() => startGame(numAgents, startingPlayer)}
          />
          <GameStatus
            status={state.status}
            busy={state.busy}
            loading={state.loading}
            hasGame={hasGame}
          />
          {state.error && (
            <div role="alert" className="flex items-center justify-between gap-2 rounded-lg bg-rose-100 px-3 py-2 text-sm text-rose-900">
              <span>{state.error}</span>
              {!state.busy && !state.loading && (
                <button
                  type="button"
                  onClick={() => (hasGame ? retry() : startGame(numAgents, startingPlayer))}
                  className="shrink-0 rounded-md bg-rose-700 px-3 py-1 font-semibold text-white"
                >
                  Reintentar
                </button>
              )}
            </div>
          )}
          {hasGame && (
            <Board
              boardSize={state.boardSize}
              board={state.board}
              disabled={locked || state.status !== "in_progress" || state.turn === "machine"}
              lastMoves={state.lastMoves}
              winningLine={state.winningLine}
              highlightedCell={highlighted}
              onCellClick={play}
            />
          )}
        </section>
        <aside aria-label="Panel lateral" className="flex flex-col gap-2">
          <SidePanelTabs active={tab} onChange={setTab} />
          <div id="side-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
            {tab === "chat" ? (
              <NegotiationChat
                items={state.chat}
                agents={state.agents}
                thinkingAgentId={state.thinkingAgentId}
                onHoverCell={setHighlighted}
              />
            ) : (
              <MetricsPanel metrics={state.metrics} agents={state.agents} />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
