export type TabId = "chat" | "metrics";

const TABS: { id: TabId; label: string }[] = [
  { id: "chat", label: "Chat" },
  { id: "metrics", label: "Métricas" },
];

interface Props {
  active: TabId;
  onChange: (tab: TabId) => void;
}

export function SidePanelTabs({ active, onChange }: Props) {
  return (
    <div role="tablist" aria-label="Panel lateral" className="flex gap-1 border-b border-slate-300">
      {TABS.map((t) => (
        <button
          key={t.id}
          role="tab"
          type="button"
          id={`tab-${t.id}`}
          aria-selected={active === t.id}
          aria-controls="side-panel"
          onClick={() => onChange(t.id)}
          className={`rounded-t-md px-4 py-1.5 text-sm font-semibold ${
            active === t.id ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-200"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
