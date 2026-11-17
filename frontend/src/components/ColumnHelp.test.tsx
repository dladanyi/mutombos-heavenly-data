import { render, screen } from '@testing-library/react'
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
  return { user, trigger: screen.getByRole('button', { name: 'What is Luck?' }) }
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

  it('stays open when the card itself is tapped', async () => {
    const { user, trigger } = setup()
    await user.click(trigger)
    await user.click(screen.getByRole('dialog'))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('has copy for every All-Play heading', () => {
    expect(Object.keys(WEEK_HELP)).toEqual(['Avg Cats', 'All-Play', 'Win %'])
    expect(Object.keys(SEASON_HELP)).toEqual(['All-Play', 'Win %', 'Avg Cats', 'Record', 'Luck'])
  })
})
