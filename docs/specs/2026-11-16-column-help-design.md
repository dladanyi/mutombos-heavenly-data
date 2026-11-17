# Column help on the All-Play tab (short design)

## Intent

All-Play numbers are new to the league. Tapping a column heading should say what it means, so
nobody has to ask.

## Scope

- Week table (`AllPlayTable`): **Avg Cats**, **All-Play**, **Win %**.
- Season table (`AllPlaySeasonTable`): **All-Play**, **Win %**, **Avg Cats**, **Record**, **Luck**.
- Non-goals: other tabs, the head-to-head grid, the `#`/Team/Matchup/Result headings.

## Approaches

1. **Native HTML `popover`** (`popovertarget`): free light-dismiss and Esc, top layer. But jsdom
   (our test runner) implements neither `popover` nor `<dialog>.showModal`, so the open/close
   behaviour could not be tested.
2. **`title` attribute tooltips**: no tap support on phones, which is where the site is mostly used.
3. **Chosen: a small React component** holding its own open state, rendering the card through a
   portal into `document.body`. Testable in jsdom and not clipped by the table's sideways scroll
   or by the `.section` fade-in animation (its leftover `transform` would trap a `position: fixed`
   card inside the section).

## Design

- `ColumnHelp({ label, children })` renders a `<button>` inside the `<th>`: the label with a
  dotted underline and a small ⓘ. The button fills the cell, so the whole cell is the tap target.
  Its accessible name is the label itself (with `aria-haspopup="dialog"`), so screen readers
  still announce the column as "Luck", not as a question.
- Tapping opens a card (`role="dialog"`, labelled by the label) with the label as a heading, the
  explanation, and a Close button. The card is fixed and centred near the top of the viewport over a
  transparent full-screen backdrop.
- Closes on: the Close button, a tap on the backdrop (only when the press started there, so a
  text drag that ends outside doesn't close it), Esc, or Back/Forward (tabs are hidden, not
  unmounted, so the card would otherwise stay over the other tab). Tab keeps focus on Close. Focus moves to Close on open and
  back to the heading button on close. Only one card can be open, because the backdrop covers the
  other headings.

## Copy

Week:

- **Avg Cats**: Categories this team would win, on average, against each other team this week, out of 9. Ties count half.
- **All-Play**: This team's record if it had played every other team this week (wins–losses–ties). Winning more categories than the other team counts as a win.
- **Win %**: Share of those all-play games won, with ties counting half.

Season:

- **All-Play**: Weekly all-play records added up over every completed week.
- **Win %**: Share of all-play games won this season, with ties counting half. The table is ranked by this.
- **Avg Cats**: The weekly Avg Cats averaged over the completed weeks.
- **Record**: The team's real category record (wins–losses–ties) from its actual matchups in those weeks. A week without a matchup, like a bye, counts for All-Play but not here.
- **Luck**: Real categories won minus Avg Cats, averaged per week. Above zero means the team met weaker opponents than the league average; below zero means tougher ones.

## Left to the builder

Exact spacing and colours, kept within the existing tokens (`--surface2`, `--border`,
`--accent`, `--muted`).
