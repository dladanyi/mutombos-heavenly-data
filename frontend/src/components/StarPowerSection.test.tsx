import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { starPower } from '../test/data'
import StarPowerSection from './StarPowerSection'

function stub(body: unknown) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })))
}

describe('StarPowerSection', () => {
  it('says when its own data is from', async () => {
    stub(starPower({ fetched_at: '2026-11-20T18:30:00Z' }))
    render(<StarPowerSection />)
    expect(await screen.findByText(/^As of /)).toHaveTextContent('Nov 20')
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('warns when Yahoo was unavailable and the data is stale', async () => {
    stub(starPower({ stale: true }))
    render(<StarPowerSection />)
    expect(await screen.findByRole('status')).toHaveTextContent(/Yahoo unavailable/)
  })
})
