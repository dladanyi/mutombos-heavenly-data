import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import ColumnHelp from './ColumnHelp'
import { SEASON_HELP, WEEK_HELP } from './columnHelpText'

const setup = () => {
  const user = userEvent.setup()
  render(
    <table>
      <thead>
        <tr>
          <th>
            <ColumnHelp label="Luck">Explains luck.</ColumnHelp>
          </th>
        </tr>
      </thead>
    </table>,
  )
  return { user, trigger: screen.getByRole('button', { name: 'Luck' }) }
}

describe('ColumnHelp', () => {
  it('shows only the label until tapped', () => {
    setup()
    expect(screen.getByRole('columnheader')).toHaveTextContent(/^Luck$/)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('opens a card outside the table and focuses Close', async () => {
    const { user, trigger } = setup()
    await user.click(trigger)
    const dialog = screen.getByRole('dialog', { name: 'Luck' })
    expect(dialog).toHaveTextContent('Explains luck.')
    expect(screen.getByRole('table')).not.toContainElement(dialog)
    expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus()
  })

  it('closes on Close, Esc and the backdrop, returning focus', async () => {
    const { user, trigger } = setup()
    const ways = [
      () => user.click(screen.getByRole('button', { name: 'Close' })),
      () => user.keyboard('{Escape}'),
      () => user.click(document.querySelector('.col-help-backdrop')!),
    ]
    for (const close of ways) {
      await user.click(trigger)
      expect(screen.getByRole('dialog')).toBeInTheDocument()
      await close()
      expect(screen.queryByRole('dialog')).toBeNull()
      expect(trigger).toHaveFocus()
    }
  })

  it('is modal: Tab and Shift+Tab keep focus on Close', async () => {
    const { user, trigger } = setup()
    await user.click(trigger)
    expect(screen.getByRole('dialog')).toHaveAttribute('aria-modal', 'true')
    const close = screen.getByRole('button', { name: 'Close' })
    await user.tab()
    expect(close).toHaveFocus()
    await user.tab({ shift: true })
    expect(close).toHaveFocus()
  })

  it('keeps the visible label as the button and column header name', () => {
    const { trigger } = setup()
    expect(trigger).toHaveAccessibleName('Luck')
    expect(trigger).toHaveAttribute('aria-haspopup', 'dialog')
  })

  it('closes when the page navigates (Back to another tab)', async () => {
    const { user, trigger } = setup()
    await user.click(trigger)
    fireEvent.popState(window)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('stays open when a drag starts in the card and ends on the backdrop', async () => {
    const { trigger, user } = setup()
    await user.click(trigger)
    const backdrop = document.querySelector('.col-help-backdrop')!
    fireEvent.pointerDown(screen.getByText('Explains luck.'))
    fireEvent.pointerUp(backdrop)
    fireEvent.click(backdrop)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('stays open when the card itself is tapped', async () => {
    const { user, trigger } = setup()
    await user.click(trigger)
    await user.click(screen.getByRole('dialog'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('has copy for every All-Play heading', () => {
    expect(Object.keys(WEEK_HELP)).toEqual(['Avg Cats', 'All-Play', 'Win %'])
    expect(Object.keys(SEASON_HELP)).toEqual(['All-Play', 'Win %', 'Avg Cats', 'Record', 'Luck'])
    // @ts-expect-error a misspelt heading is a type error, not an empty card
    expect(SEASON_HELP.Luk).toBeUndefined()
  })
})
