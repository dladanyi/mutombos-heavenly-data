# Column Help Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tapping an All-Play column heading opens a small card explaining what it means.

**Architecture:** One `ColumnHelp` component (its own open state, card portaled into
`document.body`). The two All-Play tables wrap their headings in it, using text taken from a
single copy module.

**Tech Stack:** React 19 + TypeScript, vitest + Testing Library (jsdom), plain CSS.

**Spec:** `docs/specs/2026-11-16-column-help-design.md`

## Global Constraints

- The copy comes verbatim from the spec's Copy section.
- Use the existing CSS tokens only. The card stays within a 390 px viewport with a 16 px gutter.
- `getAllByRole('columnheader')` text must still read exactly the plain labels: the ⓘ is
  `aria-hidden` and has no text content (it comes from CSS `::after`).
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- A heading that sits inside the horizontally scrolling `.table-wrap`, inside an animated
  `.section`: the card must not be clipped. A portal to `document.body` covers this (test: the
  dialog is not inside the table).
- Esc while a card is open closes it and returns focus to the heading button.
- A tap outside the card (on the backdrop) closes it, and a tap inside does not.
- Sorting by heading doesn't exist, so the button must not look like a sort control. It uses a
  dotted underline, not arrows.
- The existing header-text assertions in `AllPlayTable.test.tsx` and `AllPlaySection.test.tsx`
  keep passing unchanged.

---

### Task 1: `ColumnHelp` component and copy

**Files:**
- Create: `frontend/src/components/ColumnHelp.tsx`, `frontend/src/components/columnHelpText.ts`
- Modify: `frontend/src/styles.css` (new `col-help-*` rules)
- Test: `frontend/src/components/ColumnHelp.test.tsx`

**Interfaces:**
- Produces: `default function ColumnHelp({ label, children }: { label: string; children: ReactNode })`.
- Produces: `WEEK_HELP` and `SEASON_HELP` in `columnHelpText.ts`, typed
  `Record<string, string>`, keyed by heading label. `WEEK_HELP` has `Avg Cats`, `All-Play` and
  `Win %`; `SEASON_HELP` has `All-Play`, `Win %`, `Avg Cats`, `Record` and `Luck`.

- [ ] **Step 1: Write the failing tests** in `ColumnHelp.test.tsx`. Render
  `<table><thead><tr><th><ColumnHelp label="Luck">Explains luck.</ColumnHelp></th></tr></thead></table>`
  with `userEvent`.
  - `it('shows only the label until tapped')`: the columnheader's text is `Luck`, the button is named
    `What is Luck?`, and `queryByRole('dialog')` is null.
  - `it('opens a card outside the table and focuses Close')`: after clicking the button,
    `getByRole('dialog', { name: 'Luck' })` contains `Explains luck.`, is not inside the `table`
    element, and `Close` has focus.
  - `it('closes on Close, Esc and the backdrop, returning focus')`: for each of the three ways
    (`Close` click; `keyboard('{Escape}')`; click on `.col-help-backdrop`), open the card, close it,
    expect no dialog and the heading button focused.
  - `it('stays open when the card itself is tapped')`: click the dialog and it is still present.
  - `it('has copy for every All-Play heading')`: `Object.keys(WEEK_HELP)` equals
    `['Avg Cats', 'All-Play', 'Win %']`, and `Object.keys(SEASON_HELP)` equals
    `['All-Play', 'Win %', 'Avg Cats', 'Record', 'Luck']`.

- [ ] **Step 2: Run them and watch them fail**
  Run: `cd frontend && npx vitest run src/components/ColumnHelp.test.tsx`
  Expected: FAIL because the modules can't be resolved.

- [ ] **Step 3: Implement.**
  - The button gets `className="col-help-btn"`, `aria-label={\`What is ${label}?\`}` and
    `aria-haspopup="dialog"`, and renders `{label}`. The ⓘ is drawn by `.col-help-btn::after`.
  - When open, `createPortal` renders `<div className="col-help-backdrop" onClick={close}>`
    containing `<div role="dialog" aria-labelledby={id} className="col-help-card" onClick={stop}>`
    with `<h3 id={id}>`, `<p>` and a `<button>Close</button>`. The `id` comes from `useId()`.
  - A keydown listener on `document` handles Escape while open.
  - A ref holds the trigger, and focus goes back to it on close.
  - The copy file holds the spec's strings verbatim.
  - CSS:
    - The button inherits the font, colour and alignment, with no background, a dotted underline
      and `cursor: help`. `::after` is a small `ⓘ` at 0.85em.
    - The backdrop is `position: fixed; inset: 0; z-index: 50`.
    - The card is fixed and centred near the top: `top: 20%`, `left: 50%`,
      `translateX(-50%)`, `width: min(320px, calc(100vw - 32px))`. It uses `--surface2`, a
      `--border` border, an `--accent` top border, body-font text in the normal case, and
      `white-space: normal`.

- [ ] **Step 4: Run them and watch them pass**
  Run: `cd frontend && npx vitest run src/components/ColumnHelp.test.tsx`
  Expected: 5 passed.

- [ ] **Step 5: Commit** with `feat: ColumnHelp heading pop-up`.

### Task 2: Wire into both All-Play tables, docs

**Files:**
- Modify: `frontend/src/components/AllPlayTable.tsx`, `frontend/src/components/AllPlaySeasonTable.tsx`
- Test: `frontend/src/components/AllPlayTable.test.tsx` (it already renders both `AllPlayTable` and `AllPlaySeasonTable`)
- Docs: `docs/architecture.md` (the All-Play paragraph), `docs/decisions.md` (new dated entry)

**Interfaces:**
- Consumes: `ColumnHelp`, `WEEK_HELP` and `SEASON_HELP` from Task 1.

- [ ] **Step 1: Write the failing tests.**
  - `AllPlayTable`: `it('explains Avg Cats, All-Play and Win % when their headings are tapped')`.
    For each of the 3 labels, click the button named `What is <label>?`, expect a dialog named
    `<label>` containing `WEEK_HELP[label]`, then close it. Also check that no button is named
    `What is Matchup?`.
  - Season table: `it('explains every season heading except # and Team')`. Same loop over the 5
    `SEASON_HELP` keys, expecting `SEASON_HELP[label]`.

- [ ] **Step 2: Run them and watch them fail.**
  Run: `cd frontend && npx vitest run src/components/AllPlayTable.test.tsx`
  Expected: the new tests FAIL because no such button exists. Existing tests pass.

- [ ] **Step 3: Implement.** Replace each listed `<th>Label</th>` with
  `<th><ColumnHelp label="Label">{WEEK_HELP['Label']}</ColumnHelp></th>`, using `SEASON_HELP`
  in the season table.

- [ ] **Step 4: Run the whole frontend suite, typecheck and lint**
  Run: `cd frontend && npx vitest run && npx tsc -b --noEmit && npx oxlint`
  Expected: everything passes (73 + the new tests), with no type or lint errors.

- [ ] **Step 5: Docs, graph, commit.** Add a sentence on `ColumnHelp` to the All-Play paragraph in
  `architecture.md`. Add a short `2026-11-16: All-Play column help` entry to `decisions.md`:
  React component over native `popover` because jsdom can't test it; portal because of the
  `.section` transform. Then run `graphify update .` and commit with
  `feat: explain All-Play column headings on tap`.

### Task 3: Check it in the real app

- [ ] Run the dev servers and open `#allplay` in Playwright at 390 px and at desktop width.
  - Tap Avg Cats in the week table and Luck in the season table.
  - Check that the card is fully visible, Esc closes it, and the headings still line up.
  - Save screenshots to the session scratchpad, not the repo.
