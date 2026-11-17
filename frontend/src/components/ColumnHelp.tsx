import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type Props = {
  /** The column heading, shown as-is. */
  label: string
  /** What the column means. */
  children: ReactNode
}

/** A column heading that opens a short explanation when tapped. The card is portaled into
 * document.body so the table's sideways scroll and the section's fade-in transform can't clip it. */
export default function ColumnHelp({ label, children }: Props) {
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const closeBtn = useRef<HTMLButtonElement>(null)
  const id = useId()

  const close = () => {
    setOpen(false)
    trigger.current?.focus()
  }

  useEffect(() => {
    if (!open) return
    closeBtn.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
        trigger.current?.focus()
      } else if (e.key === 'Tab') {
        // Modal: Close is the card's only focusable element, so focus stays on it.
        e.preventDefault()
        closeBtn.current?.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  return (
    <>
      <button
        ref={trigger}
        type="button"
        className="col-help-btn"
        aria-label={`What is ${label}?`}
        aria-haspopup="dialog"
        onClick={() => setOpen(true)}
      >
        {label}
      </button>
      {open &&
        createPortal(
          <div className="col-help-backdrop" onClick={close}>
            <div
              role="dialog"
              aria-modal="true"
              aria-labelledby={id}
              className="col-help-card"
              onClick={(e) => e.stopPropagation()}
            >
              <h3 id={id}>{label}</h3>
              <p>{children}</p>
              <button ref={closeBtn} type="button" className="col-help-close" onClick={close}>
                Close
              </button>
            </div>
          </div>,
          document.body,
        )}
    </>
  )
}
