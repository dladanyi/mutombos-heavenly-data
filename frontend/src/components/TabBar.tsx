export type Tab = 'rankings' | 'stars' | 'allplay'

const TABS: { id: Tab; label: string }[] = [
  { id: 'rankings', label: 'Rankings' },
  { id: 'stars', label: 'Star Power' },
  { id: 'allplay', label: 'All-Play' },
]

export default function TabBar({ tab, onChange }: { tab: Tab; onChange: (tab: Tab) => void }) {
  return (
    <div className="tab-bar" role="tablist">
      {TABS.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={tab === t.id}
          className={tab === t.id ? 'tab active' : 'tab'}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}
