# Live Ops Hub — iPhone/iPad app: project kickoff

_State as of Nov 10 2026, end of day. Paste this into the Claude project as its instructions, and connect the repository `ofir-cell/packing-station`. The repository's own `CLAUDE.md` carries the standing rules; this page is the starting point._

## The goal

Ship **Live Ops Hub** to the App Store: the app warehouse teams of live sellers use to pick, pack and prove every order. First our own warehouse on TestFlight, then Apple's review, then outside sellers.

## Where we are

**Working today**
- The app is on TestFlight (builds 4 and 5) and installed on Ofir's iPhone.
- Every merge to `main` that touches the app uploads a new TestFlight build automatically.
- The app has three tabs: **Dashboard** (the website, signed in), **Pick** (a screen built for the phone), **Pack** (native: scan a label, record the packing video).
- Scanning supports a Bluetooth scanner, the camera, and typing. iPad is supported in every orientation.

**Built but not yet proven on a real device**
- Bluetooth scanner on Pick and on Pack (hands-free: scan → records → scan → saves → next box).
- Packing video upright on iPad in landscape.
- Everything beyond "the app installs and opens". The list is in `docs/mobile/device-tests/PROVEN.md`.

**Not built yet — what stands between us and Apple's approval**
1. A demo company and login for Apple's reviewer (needs Ofir's decision on 2FA, below).
2. A native Account screen: sign out, delete account, privacy policy.
3. More phone-built screens (Today, Track, table clean-out) so the app is clearly more than a website in a frame.
4. Store listing: screenshots, privacy answers, reviewer notes.

## Decisions waiting for Ofir

1. **Reviewer login without 2FA.** Apple's reviewer cannot receive a code. Proposal: skip 2FA only for one isolated demo company with fake data that cannot reach real companies or send anything outside. Yes / no?
2. **Colour inside the app.** Each company's own brand colour (how it works now, same as the website), or always the LiveOpsHub indigo from the approved mockups?

## How work on the app affects the live warehouse

| Kind of change | Touches the live site? |
|---|---|
| Native app code (`ios/`) | No. Reaches phones only, through TestFlight. |
| Phone screens (`mobile/`, `/m/...`) | The desktop screens are untouched, but it is the same server and the same real data: a merge redeploys the server, and an order picked in the app is picked for real. |
| Shared logic (`app.py`) | Yes. Avoided in app work; when needed it is a separate, clearly labelled change. |

Ofir merges everything. Server changes are best merged outside packing hours. Device testing uses the demo company once it exists.

## The team (agents in `.claude/agents/`)

| Agent | Job |
|---|---|
| **ios-designer** | Design system and the spec for each phone screen. |
| **mobile-engineer** | Builds the phone screens (`/m/...`). |
| **ios-engineer** _(new)_ | Builds the native parts: tabs, Pack, camera, scanner, Account. |
| **programmer** | Server changes, when a screen needs one. |
| **mobile-qa** | Tests every screen at iPhone and iPad sizes in a real browser. |
| **qa** | Server tests and the invariants that protect the warehouse. |
| **security-reviewer** _(new)_ | Sign-in, roles, company isolation, the demo account, privacy. |
| **release-manager** _(new)_ | TestFlight pipeline, release notes, store listing, submission checklist. |
| **device-test-lead** _(new)_ | 10-minute test scripts for real phones; turns what testers report into bugs. |
| **app-review** | Plays Apple's reviewer before every submission. |
| **architect**, **product-engineer**, **product-designer** | Bigger design questions and the non-mobile product. |

They do not share a conversation. They hand work over through one board, `docs/mobile/BOARD.md`, and every hand-over says what was done, the evidence, what is not verified, and the next step. Reviewers cannot be overruled by the engineer they reviewed; disagreements come to Ofir as a choice between two options.

Considered and left out for now, to keep the team small: a separate localisation agent (the designer owns English and Spanish copy), an analytics agent, and a customer-support agent. Worth adding when outside sellers start using the app.

## Next steps, in order

1. Ofir answers the two decisions above.
2. Native Account screen → security review → App Review check.
3. Demo company and reviewer login (after decision 1).
4. First on-device test script for the current build; Ofir runs it with a Bluetooth scanner on iPhone and iPad.
5. Phone screens: Today, Track, table clean-out.
6. Store listing and screenshots → App Review agent says APPROVE → Ofir submits.

## How to start a session

Say what you want in plain words, in Hebrew. For example:
- "תמשיך לפי הלוח" — continue with the next item on the board.
- "בדקתי על האייפון, הסורק לא עובד ב-Pack" — a device report; it becomes a bug for the right engineer.
- "תכין את הגרסה להגשה לאפל" — runs the submission checklist and the App Review check.
