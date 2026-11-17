import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type Props = {
  /** The column heading, shown as-is; also the button's (and so the column's) accessible name. */
  label: string
  /** What the column means. */
  children: ReactNode
}

/** A column heading that opens a short explanation when tapped. The card is portaled into
 * document.body so the table's sideways scroll and the section's fade-in transform can't clip it.
 * React events from the portal still bubble through the table, so keep click handlers off its
 * ancestors (or check the target). */
export default function ColumnHelp({ label, children }: Props) {
  const [open, setOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const closeBtn = useRef<HTMLButtonElement>(null)
  // Only a press that starts on the backdrop closes the card, so a text drag that ends outside doesn't.
  const pressedBackdrop = useRef(false)
  const id = useId()

  const close = useCallback(() => {
    setOpen(false)
    trigger.current?.focus()
  }, [])

  useEffect(() => {
    if (!open) return
    closeBtn.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close()
      else if (e.key === 'Tab') {
        // Modal: Close is the card's only focusable element, so focus stays on it.
        e.preventDefault()
        closeBtn.current?.focus()
      }
    }
    // Back/Forward switches tab by hiding this one, not unmounting it; don't leave the card behind.
    const onNavigate = () => setOpen(false)
    document.addEventListener('keydown', onKey)
    window.addEventListener('popstate', onNavigate)
    window.addEventListener('hashchange', onNavigate)
    return () => {
      document.removeEventListener('keydown', onKey)
      window.removeEventListener('popstate', onNavigate)
      window.removeEventListener('hashchange', onNavigate)
    }
  }, [open, close])

  return (
    <>
      <button ref={trigger} type="button" className="col-help-btn" aria-haspopup="dialog" onClick={() => setOpen(true)}>
        {label}
      </button>
      {open &&
        createPortal(
          <div
            className="col-help-backdrop"
            onPointerDown={(e) => (pressedBackdrop.current = e.target === e.currentTarget)}
            onClick={(e) => {
              if (e.target === e.currentTarget && pressedBackdrop.current) close()
            }}
          >
            <div role="dialog" aria-modal="true" aria-labelledby={id} className="col-help-card">
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
