# Apple Developer Program — organization enrollment checklist (Btrade LLC)

Enroll as an **organization** (not an individual) so the app is published under the company.
Apple verifies the legal entity against **Dun & Bradstreet**, so the details below must match
your D&B record and your Florida registration **exactly**. Start only once the D&B profile
edits you just submitted have been processed.

## Exact details to have ready (match everything to Sunbiz + D&B)
| Field | Value |
|---|---|
| Legal entity name | **BTRADE LLC** |
| Entity type | Limited Liability Company (Florida) |
| D-U-N-S number | **10-114-2825** |
| Legal address | 4322 SW 84th Ter, Davie, FL 33328, USA |
| Work email (Apple ID) | ofir@5secbeauty.com (use a company-domain email if you have one) |
| Website | https://liveopshub.com |
| Authority to bind | You must be a person who can legally sign for the LLC, or be authorized by one |

> ⚠️ Before enrolling, confirm the D&B profile now shows the **Davie** address and a **US
> phone** (it was showing a Fort Lauderdale address and a 416/Toronto number). Apple's
> verification call/email uses D&B data; a mismatch is the #1 cause of delays.

## Steps
1. **Apple ID** — use (or create) an Apple ID on the company email, with two-factor
   authentication enabled. Don't use a personal Apple ID you use for purchases.
2. Go to developer.apple.com → **Enroll** → choose **Company / Organization**.
3. Enter the legal entity name, D-U-N-S **10-114-2825**, address and website above.
4. Confirm you have authority to bind the organization.
5. Pay the **US $99/year** membership fee.
6. **Verification** — Apple may email or phone the number on the D&B record to confirm you
   represent Btrade LLC. Answer promptly; this is where it stalls if D&B data is stale.
7. Approval typically takes a few days (can be longer if verification is needed).

## After approval — what unlocks
- Create the app record in **App Store Connect** (bundle ID `com.btrade.liveopshub`).
- Signing: in Xcode, set the Team to the Btrade LLC org, bundle ID `com.btrade.liveopshub`,
  add Push Notifications capability (see `mobile/README.md`).
- Build the Capacitor app → TestFlight → submit for review.

## App Store review readiness (already handled in code, listed so you can check them off)
- [x] **In-app account deletion** (Guideline 5.1.1(v)) — live on `/me`; mobile opens it.
- [x] **Not a thin web wrapper** (Guideline 4.2) — native barcode scan + push + offline in `mobile/`.
- [x] **Privacy policy URL** — https://liveopshub.com/privacy
- [ ] **App Privacy questionnaire** in App Store Connect — declare data types + subprocessors
      (use `wms-tiktok-appstore-compliance.md`).
- [ ] App icon 1024×1024, no alpha/transparency, square (use the LoH mark).
- [ ] Screenshots per device class (6.7"/6.5" iPhone, 12.9" iPad).
- [ ] Description, keywords, support URL (https://liveopshub.com).

## Your action right now
1. Wait for the D&B edits to process; confirm address + phone are correct.
2. Then enroll in Apple Developer (org) with the table above.
3. Tell me when the membership is approved and I'll walk you through creating the App Store
   Connect record and the first TestFlight build.
