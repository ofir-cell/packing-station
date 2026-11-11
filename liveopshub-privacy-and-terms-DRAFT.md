# Live Ops Hub — Privacy Policy & Terms of Service (DRAFT)

> **Draft for review.** Fill every `[[PLACEHOLDER]]`. This covers the elements TikTok Shop App Review and Apple App Store both require. Not legal advice — have counsel review before publishing.

**Inputs needed from you** (the `[[PLACEHOLDERS]]`):
`[[COMPANY_LEGAL_NAME]]` = Btrade LLC · `[[BUSINESS_ADDRESS]]` · `[[SUPPORT_EMAIL]]` · `[[PRIVACY_EMAIL]]` (can be same) · `[[PUBLIC_DOMAIN]]` (the Live Ops Hub site URL) · `[[RETENTION_DAYS]]` (how long you keep order data after a seller disconnects — suggest 30–90) · `[[EFFECTIVE_DATE]]`.

---

# Privacy Policy

**Effective date:** [[EFFECTIVE_DATE]]

Live Ops Hub ("the Service"), operated by [[COMPANY_LEGAL_NAME]] ("we", "us"), helps TikTok Shop sellers run order fulfillment and warehouse operations. This policy explains what we collect, why, who we share it with, how long we keep it, and your rights.

## 1. Data we collect
- **Shop & order data** from TikTok Shop (via authorized API): order IDs, line items/SKUs, order status, buyer name and shipping address, package and tracking identifiers, and LIVE-session performance data.
- **Account data** for Service users (your staff): name, email, role, login activity.
- **Operational data** we generate: picking/packing status, shipment weights, labels and tracking numbers.

We access TikTok Shop data **only in read mode** for the scopes you authorize; we do not write to your TikTok Shop.

## 2. How we use it
To sync and display orders, group them by LIVE session, drive picking/packing/shipping workflows, generate shipping labels, and provide backups and support. We do **not** sell personal data or use it for advertising.

## 3. Who we share it with (subprocessors)
We use these vendors solely to operate the Service:

| Subprocessor | Purpose | Data |
|---|---|---|
| Railway | Application hosting | Order & operational data |
| Cloudflare R2 | Encrypted backups, media storage | DB snapshots, media |
| ShipStation | Shipping-label purchase | Shipping address, parcel data |
| USPS | Tracking | Tracking numbers |
| Anthropic | Address parsing (as needed) | Shipping addresses |
| [[EMAIL_PROVIDER]] | Operational email | Email addresses |

We do not permit subprocessors to use the data for their own purposes.

## 4. Data retention
We retain shop and order data while your authorization is active. After you **disconnect or deauthorize** the app, we delete or anonymize your TikTok Shop data within **[[RETENTION_DAYS]] days**, except where longer retention is legally required. Backups age out on a fixed schedule.

## 5. Deletion after deauthorization
When you deauthorize Live Ops Hub (via TikTok Seller Center or in-app), we stop all data access immediately and begin deletion of your shop data per §4. You may also request immediate deletion (see §7).

## 6. Security
Per-seller data isolation, signature-verified webhooks, encrypted credentials and backups, access controls, and session revocation.

## 7. Your rights (data-subject & deletion requests)
You may request access, correction, or deletion of your data, or ask questions about this policy, at **[[PRIVACY_EMAIL]]**. We respond within the timeframe required by applicable law. Account holders can also delete their account in-app.

## 8. Data location
Data is processed and stored in the **United States**.

## 9. Changes
We will post changes here and update the effective date.

## 10. Contact
[[COMPANY_LEGAL_NAME]], [[BUSINESS_ADDRESS]] · [[PRIVACY_EMAIL]]

---

# Terms of Service

**Effective date:** [[EFFECTIVE_DATE]]

1. **The Service.** Live Ops Hub provides order-fulfillment and warehouse-operations tooling for TikTok Shop sellers.
2. **Authorization.** You authorize us to access your TikTok Shop data via the scopes you approve. You may revoke access at any time.
3. **Acceptable use.** Use the Service lawfully and only for shops you are authorized to manage.
4. **Your data.** You own your data. We process it per the Privacy Policy.
5. **Availability.** Provided "as is"; we aim for high availability but do not guarantee uninterrupted service.
6. **Liability.** To the maximum extent permitted by law, our liability is limited as set out here. [[COUNSEL_TO_REVIEW]]
7. **Termination.** Either party may terminate; on termination we delete data per the Privacy Policy.
8. **Contact.** [[SUPPORT_EMAIL]]

---

## Where this gets published (both stores require it)
- Host these as two pages on **[[PUBLIC_DOMAIN]]** (e.g. `/privacy` and `/terms`).
- Put **visible, active links in the site footer** (TikTok requires them reachable without opening a menu).
- Use the Privacy URL in the TikTok app listing **and** in Apple App Store Connect ("App Privacy").
