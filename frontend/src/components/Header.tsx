const FORMAT = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Los_Angeles',
  weekday: 'short',
  month: 'short',
  day: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZoneName: 'short',
})

export function formatTime(iso: string): string {
  return FORMAT.format(new Date(iso))
}

export default function Header({ fetchedAt, stale }: { fetchedAt?: string; stale: boolean }) {
  return (
    <header>
      <div className="eyebrow">Fantasy Basketball · League Stats Dashboard</div>
      <div className="header-main">
        <div className="header-img header-img-left">
          <img src="/header-left.jpg" alt="" />
        </div>
        <div className="header-text">
          <h1>
            Mutombo's
            <br />
            Heavenly Data
          </h1>
          {fetchedAt && <div className="timestamp">Last updated: {formatTime(fetchedAt)}</div>}
        </div>
        <div className="header-img header-img-right">
          <img src="/header-right.jpg" alt="" />
        </div>
      </div>
      {stale && fetchedAt && (
        <div className="notice" role="status">
          Showing data as of {formatTime(fetchedAt)} (Yahoo unavailable)
        </div>
      )}
    </header>
  )
}
