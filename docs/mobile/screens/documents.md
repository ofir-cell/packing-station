> **Not in 1.0 — waits for 1.1; back button and entry point to be re-specified then.** Blueprint §3.2 lists this screen as "later" (after 1.1). Until it is taken up, nothing below is built; paths, `‹ More` back buttons, badges and "language is in More" in this file are out of date (APP_BLUEPRINT §3.2, §8.2).

# Documents — `/documents` · `DOCUMENTS_HTML`

**User:** employee reading policies and personal records, or signing onboarding paperwork.
**Purpose:** find and open a document; see what still needs a signature.

## What changes vs. today (`audit/…/pro/worker/documents.png`)
- The filter is a wrapped cluster of 5 small chips with count badges inside a grey box (25 small targets, 15 tiny texts) → **one horizontally scrolling chip row** (`.m-chips` > `.m-chip[aria-pressed]`: each chip a 44pt pill, 15px label, `.m-chip__count` in muted text): All · Policies · Personal · Onboarding · Other. The selected chip is filled `--brand` with white text.
- 📂 emoji title → large title "Documents", subtitle "Policies, your records and onboarding paperwork".
- Empty: `.m-empty` with a folder icon, "No documents yet", "Your manager will add them here. You'll get a notice in News."

## Layout at 390pt
1. Nav bar `‹ More`. Large title + subtitle. 2. Chip row. 3. **"Needs your signature"** section (if any): rows with a leading orange doc icon, title, sub "Due {date}", trailing `.m-pill--issue` "Sign". 4. Sections by category (when the All chip is selected) or a single list: rows with a leading file-type tile (PDF / IMG), title (2 lines), sub "{category} · Added {date}", trailing chevron. Tap → opens the file in a native Quick Look sheet in the app (`target=_blank` + WKWebView `decidePolicyFor` → `QLPreviewController`), or a new tab in browsers.

## States
Loading: 4 skeleton rows · Error banner + Retry · Signed confirmation: toast "Signed" + haptic `success`.
