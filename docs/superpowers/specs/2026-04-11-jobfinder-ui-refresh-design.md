# JobFinder UI Refresh Design

Date: 2026-04-11

## Goal

Refresh the desktop UI to feel closer to a native Apple productivity tool while preserving the current JobFinder workflow. At the same time, fix two reliability issues discovered during code review:

- skipped-job rows are written to Excel with the wrong column alignment
- ChatGPT conversation lookup is brittle and the debug-launch flow does not clear leftover draft input

## Scope

In scope:

- restructure the `tkinter` UI from notebook tabs into a left-navigation, right-content layout
- restyle controls with a calm macOS-inspired visual language
- keep the current configuration fields and button actions
- clear the ChatGPT draft input when launching Debug Chrome
- harden ChatGPT conversation targeting
- fix the skipped-job Excel row bug

Out of scope:

- changing frameworks
- rewriting the automation flow
- changing the JSON prompt/output schema
- redesigning PDF templates

## Chosen Approach

Use a moderate refactor inside the existing `tkinter + ttk` stack.

Why this approach:

- it gives a meaningful visual upgrade without destabilizing the app
- it preserves existing business logic and config handling
- it keeps the codebase understandable for future maintenance

Alternatives considered:

1. Light reskin only
   Lowest risk, but would still look like a tabbed utility rather than an Apple-style app.
2. Full dashboard rewrite
   Best visual payoff, but too much layout churn for a tool that already works.

## UI Design

### Structure

Replace the notebook with:

- a fixed left sidebar for section switching
- a right content area with:
  - a title/status header
  - grouped cards for fields
  - a primary action row
  - an integrated log card

Sections:

- Basic Setup
- Advanced
- Personal Info
- Run Log

### Visual Language

Use a restrained Apple-inspired system:

- light gray app background
- white cards with subtle borders
- larger corner radii
- increased spacing and taller controls
- strong but calm typography hierarchy
- primary dark action button with softer secondary buttons

### Interaction

Preserve current flow:

- Save Config
- Launch Debug Chrome
- Start Run
- Edit `skill.md`

The layout changes, but the tasks and meanings stay the same.

## Chrome / ChatGPT Behavior

When Debug Chrome launches:

1. open Seek with the configured debug profile
2. open ChatGPT in the same debug profile
3. attempt to locate the ChatGPT prompt editor
4. clear any existing draft text in the prompt input
5. log success or silent failure without blocking the user

Important boundary:

- only clear the current unsent prompt draft
- do not delete message history or start a new chat automatically

## Reliability Fixes

### Skipped Job Excel Row

`append_skipped_job_to_excel()` currently writes a row with the wrong column count, which shifts values into incorrect columns. Replace the handwritten row with a schema-aligned row so the workbook stays consistent.

### ChatGPT Conversation Lookup

Current XPath selection interpolates the raw conversation title directly. Replace it with a safer locator strategy that handles quotes and avoids malformed XPath expressions.

## Error Handling

- UI refresh must not break save/load behavior
- ChatGPT draft clearing should retry briefly, then log and continue
- Launching Chrome must still succeed even if ChatGPT is slow to load
- Threaded run behavior should remain unchanged

## Validation

Validate at minimum:

- app opens successfully
- sidebar navigation switches sections correctly
- saving config still writes expected values
- Launch Debug Chrome still opens the profile
- ChatGPT draft input is cleared when possible
- Start Run still launches worker thread
- skipped jobs append to Excel with correct column alignment

## Files Expected To Change

- `jobfinder_ui.py`
- `jobfinder_web.py`
- `jobfinder_core.py`
- optionally `README.md` for brief usage notes if behavior needs documenting

## Risks

- `tkinter` styling is less flexible than native macOS controls, so the result will be Apple-inspired rather than pixel-identical
- ChatGPT DOM can change over time, so prompt-clearing logic should be defensive and selector-light

## Success Criteria

- the app feels cleaner, larger, and more macOS-like
- the workflow remains familiar to the current user
- launching Debug Chrome no longer leaves stale ChatGPT draft text behind
- skipped-job workbook rows remain structurally correct
