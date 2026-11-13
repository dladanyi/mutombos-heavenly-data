type Props = {
  /** Shown between the arrows (e.g. "2025-26"); omitted when the section title already says it. */
  label?: string
  backLabel: string
  forwardLabel: string
  canBack: boolean
  canForward: boolean
  onBack: () => void
  onForward: () => void
}

/** ‹ › buttons for stepping a section back and forward (weeks, seasons). */
export default function ArrowNav({ label, backLabel, forwardLabel, canBack, canForward, onBack, onForward }: Props) {
  return (
    <div className="season-nav">
      <button className="refresh-btn season-arrow" aria-label={backLabel} disabled={!canBack} onClick={onBack}>
        ‹
      </button>
      {label && <span className="season-label">{label}</span>}
      <button className="refresh-btn season-arrow" aria-label={forwardLabel} disabled={!canForward} onClick={onForward}>
        ›
      </button>
    </div>
  )
}
