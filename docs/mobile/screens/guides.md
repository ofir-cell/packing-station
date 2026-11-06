# Guides — `/guides` · `GUIDES_HTML`

**User:** a worker who is stuck or learning ("how do I pick on the iPad?").
**Purpose:** short how-to articles by topic.

## What changes vs. today (`audit/…/pro/worker/guides.png`)
- "📚 Guides  Ana Picker": the name next to the title is noise → large title "Guides", subtitle "How-tos for every station".
- 7 wrapped topic chips (27 small targets) → one scrolling chip row (same pattern as Documents): All · Getting started · Importing orders · Picking & scanning · Packing & recording · Shipping & tracking · Troubleshooting.
- The guide cards are fine; convert them to `.m-list` rows: title (17/600, 2 lines), sub = topic, trailing chevron. Add a leading topic icon tile.
- Add a **search** field (`.m-search`, "Search guides") under the title; it filters client-side.
- The pinned top row "Something's not working? Get help fast" becomes a `.m-card` at the top with an orange tint and a button "Get help" (→ Support for roles that have it; otherwise "Tell your manager" → creates an issue).

## Guide detail (pushed)
Inline title, Title 1 heading, body 17px with line-height 1.5, images full width, numbered steps as `.m-list` rows with step numbers in brand circles. Footer: "Was this helpful?" with 👍/👎 replaced by two `.m-btn--secondary` buttons ("Yes", "Not really").

## States
No results: "No guides match "{q}"". Loading skeleton.
