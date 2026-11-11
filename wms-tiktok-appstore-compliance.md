# Live Ops Hub — TikTok Shop App Store: עמידה בדרישות + נכסי listing

מבוסס על קריטריוני ה-App Review הרשמיים של TikTok ועל אודיט הקוד של המערכת (prod `ee5af6d`). סטטוס לכל דרישה: ✅ עומד · 🟡 חלקי · ❌ חסר (פעולה נדרשת).

## 1. צ'ק-ליסט עמידה בדרישות

| # | דרישה (TikTok) | סטטוס | מה יש לנו / מה חסר |
|---|---|---|---|
| 1 | **אפליקציה ציבורית** (Custom לא מופיעה בחנות) | ❌ | האפליקציה כרגע **Custom**. צריך ליצור/לשדרג ל-public app ב-App & Service. |
| 2 | **Data Security & Privacy Review** (US Data Security Questionnaire) | ❌ | טרם מולא. צריך לענות על השאלון + לצרף רשימת subprocessors (ראה §4). |
| 3 | **Privacy Policy + Terms of Service חיים באתר**, קישורים גלויים (בלי לפתוח תפריט), קישורים פעילים | ❌ | האתר (`site/`) עדיין בלי עמודי Privacy/ToS. הכנתי טיוטות (§5) — צריך לפרסם ולהצמיד קישורים בפוטר. |
| 4 | **Least-privilege scopes** — כל scope עם הצדקה עסקית, הסרת מה שלא בשימוש | 🟡 | אנחנו עושים **קריאה בלבד** (6 endpoints). צריך לוודא שה-scopes המבוקשים = רק shop/order/analytics/product read + webhook, בלי fulfillment-write או scopes מיותרים. הצדקות ב-§3. |
| 5 | **Data retention + deletion after deauthorization/disconnection** | 🟡 | webhook topic 6 (deauth) כבר **מסמן את החנות inactive**, אבל אין עדיין **מחיקת נתונים** בפועל. צריך תהליך מחיקה (ראה פעולה P1). |
| 6 | **מולטי-טננטיות + בידוד נתונים בין sellers** | ✅ | כל seller מבודד: טוקנים/חנויות/DB נפרדים per-org (`tiktok_shops`, per-org SQLite). עבר אודיט tenant-isolation (Cycle-4). |
| 7 | **אבטחת webhook** (אימות חתימה) | ✅ | `_tt_webhook_verify` (HMAC-SHA256); בקשה לא-חתומה לא יכולה לשנות state (401). |
| 8 | **OAuth תקין** (refresh, cipher) | ✅ | `_tt_valid_token` (רענון אוטומטי), `_tt_ensure_cipher`, חתימת HMAC על כל קריאה. |
| 9 | **הגנת נתונים / DR** | ✅ | Backup V2 — גיבויים מוצפנים ל-R2 ייעודי, manifest+checksums+integrity, restore מבודד. |
| 10 | **Sandbox testing + evidence** (Development Shop + buyer test) | ❌ | צריך להריץ את זרימות ה-API בסביבת Sandbox ולתעד request IDs / webhook event IDs. |
| 11 | **App Review video** — הדגמת כל product/scope בפעולה | ❌ | צריך להקליט וידאו שמדגים כל scope. אני יכול לכתוב את התסריט. |
| 12 | **Listing content** — שם, לוגו, תיאור, צילומי מסך, קטגוריה | 🟡 | שם ✅, לוגו ✅ (LoH), קטגוריה ✅ (Shop management). תיאור + צילומי מסך — טיוטה ב-§2. |
| 13 | **Functionality — לא לשימוש אישי/פרטי** | ✅ | כלי תפעול לסוחרים (order sync, packing, fulfillment ops) — שימוש עסקי מובהק. |

**סיכום:** הליבה הטכנית חזקה (בידוד, אבטחה, OAuth, גיבויים — כולם ✅). הפערים הם בעיקר **פרוצדורליים/משפטיים**: הפיכה ל-public, privacy policy באתר, data security questionnaire, מחיקת-נתונים-על-deauth, ו-sandbox+video לביקורת.

## 2. תיאור אפליקציה (טיוטה ל-listing)
> **Live Ops Hub** is an operations platform for TikTok Shop LIVE sellers. It syncs orders from your shop in near-real-time, groups them by LIVE session, and drives the full warehouse workflow — barcode-verified picking, packing, weight checks, and shipping-label tracking — so teams fulfill LIVE orders accurately and fast. Built for high-volume LIVE selling, with per-seller data isolation and automated backups.

**Key features (ל-listing):** near-real-time order sync · LIVE session grouping · barcode picking/packing · shipment health + consolidation · multi-station workflow · per-seller data isolation.

## 3. הצדקת scopes (least-privilege — קריאה בלבד)
| Scope | למה נחוץ | שימוש בקוד |
|---|---|---|
| Seller shop info | זיהוי החנות + shop_cipher לקריאות | `/authorization/202309/shops` |
| Order (read) | משיכת הזמנות לליקוט/אריזה | `/order/202309/orders`, `/order/202309/orders/search` |
| Product (read) | סנכרון קטלוג/SKU והתאמה למלאי | `/product/202309/products/search` (Cycle-8) |
| LIVE analytics (read) | קיבוץ הזמנות לפי session | `/analytics/202509/shop_lives/performance` |
| Webhook | עדכוני הזמנות near-real-time | `/api/tiktok/webhook` (topic 1,6) |

**חשוב:** איננו מבקשים scope של **fulfillment-write** ולא כותבים ל-TikTok — הסר כל scope שלא ברשימה לפני הגשה (מונע עיכוב/דחייה).

## 4. רשימת Subprocessors (לשאלון Data Security)
| ספק | מטרה | נתונים |
|---|---|---|
| Railway | אירוח האפליקציה | כל נתוני ההזמנה/המשלוח |
| Cloudflare R2 | גיבויים + אחסון מדיה | DB snapshots, מדיה |
| Anthropic | פענוח כתובות (address parsing) | כתובות משלוח (לפי הצורך) |
| ShipStation | רכישת מדבקות משלוח | כתובת+פריטי משלוח |
| USPS | מעקב משלוחים | מספרי מעקב |
| Email provider (Resend/Google Apps Script) | התראות | אימיילים תפעוליים |

כל אלה צריכים להיות מוצהרים בשאלון.

## 5. Privacy Policy + ToS — אלמנטים חובה (טיוטה לפרסום באתר)
Privacy Policy חייבת לכסות: אילו נתונים נאספים (הזמנות, כתובות, פרטי קונה), מטרת השימוש (fulfillment), **רשימת subprocessors** (§4), **retention schedule**, **תהליך מחיקה אחרי deauthorization/disconnection**, ותהליך **data-subject requests**. ToS: תנאי שימוש בסיסיים. שניהם עם **קישורים גלויים בפוטר** של האתר ופעילים.

## 6. פערים מדורגים — פעולות
- **P0 — הפוך את האפליקציה ל-public** (App & Service → create/submit public app).
- **P0 — פרסם Privacy Policy + ToS באתר** עם קישורים גלויים (אני מכין את הטקסט המלא).
- **P1 — יישם מחיקת-נתונים על deauthorization** (topic 6 → מחיקה/אנונימיזציה מתוזמנת, לא רק inactive).
- **P1 — מלא את ה-US Data Security Questionnaire** (עם §4).
- **P2 — Sandbox testing + Review video** (אני כותב את התסריט; ההרצה/הקלטה אצלך).
- **P2 — ודא scopes least-privilege** (הסר מיותרים לפני הגשה).

**הערכת זמן:** הביקורת עצמה מדווחת ~3+ שבועות ב-US. הפערים הפרוצדורליים הם שבוע-שבועיים עבודה בעיקר על privacy/security/מחיקה.
