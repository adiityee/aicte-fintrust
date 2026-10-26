# **AICTE FinTrust: Final Merged Implementation Plan** 

SIH Problem Statement SIH26265 · Security Deposit / FDR Management Portal 

Here's the merged final plan. I took the PS description as the non-negotiable base, then picked from the three blueprints only what a real user (institution admin, scrutiny officer, clearance officer, director) would actually use, and dropped the rest. 

## **1. Decisions where** **<u>your blueprints disagreed</u>** 

|Spring Boot vs FastAPI|**FastAPI only**|OCR and forensics are Python anyway. One backend<br>means no cross-service glue for a student team.|
|---|---|---|
|MinIO vs Supabase|**Docker Compose: Postgres +**<br>**MinIO + Redis**|Runs offline, no real FDRs on third-party cloud, and<br>"on-prem, AES-256" fits a government pitch.|
|Real SFMS / MT760|**Simulated adapter behind a**<br>**real interface**|You can't get bank access. Say it honestly on the<br>slide.|
|"Forgery detection"|**"Tamper indicators", never**<br>**"fraud"**|A flag is a reason to look closer. Only the bank can<br>confirm authenticity.|
|"Near 0% fraud, 35<br>days<br>48 hours"<br>→|**Use your own measured**<br>**numbers**|Judges will ask for the baseline. Unsupported claims<br>cost you more than they gain.|
|WhatsApp API,<br>DigiLocker, mTLS,<br>blockchain, chatbot|**Cut**|Not in the PS, and each adds risk without helping the<br>user.|
|Clearance cells (Legal<br>vs Vigilance)|**Configurable list**(PGRC,<br>Vigilance, Approval Bureau, Legal,<br>Finance)|The handbooks differ. Config is safer than hardcoding.|



## **2. The core idea (your one-line pitch)** 

**FinTrust: an FDR portal where every data point has a provenance, every deadline has an owner, and no release happens until configurable clearances pass.** 

Three things make it different from a CRUD portal, and all three come straight from the PS text. 

### **Signature feature 1: Field provenance (the PS says this explicitly)** 

The PS says the system must "distinguish between information submitted by an institution and information independently confirmed by a bank." So every field on an FDR carries a source tag: 

- INSTITUTION_ENTERED → OCR_EXTRACTED (confidence 0.93) → OFFICER_VERIFIED → BANK_CONFIRMED (or SIMULATED_BANK in the demo) 

The UI shows a badge next to each field: grey for self-declared, amber for OCR, green for bank-confirmed. An officer can see at a glance what is actually proven. 

### **Signature feature 2: Dual-pass verification + bank confirmation loop** • **Pass 1, extraction:** 

PyMuPDF text layer first. If the PDF is scanned, fall back to PaddleOCR. Pull the FDR number, bank/IFSC, principal, rate, issue date, maturity date and lien-holder name using regex plus keyword anchors. Every field gets a confidence score, and anything under about 0.85 is forced into human review. 

- **Pass 2, side-by-side validation:** Compare OCR values against the form the institution filled in. Example: the form says 10,00,000 and the PDF says 1,00,000, so an amount-mismatch flag opens ₹ ₹ 

AICTE FinTrust · SIH26265 · Final Merged Implementation Plan Page 1 

with the source text highlighted. 

- **Tamper indicators** (flag only): multiple PDF incremental revisions (count %%EOF markers with pikepdf), a producer/creator mismatch, a modified date after the issue date, and mixed fonts on a numeric field. Skip error-level analysis and similar image tricks, because they give false positives and are hard to explain. 

- **Duplicate detection:** SHA-256 file hash, normalised FDR number plus bank uniqueness constraint, and crossinstitution reuse of the same FDR number. 

- **Bank confirmation adapter** with one interface and three backends: 

1. SimulatedBankAdapter, used in the demo and clearly labelled. 

2. SignedLinkAdapter: a single-use, HMAC-signed link with an expiry, sent to the branch's nodal email. The bank officer opens a minimal page, passes an OTP (mocked), and confirms four things: lien marked in favour of AICTE, no encashment without AICTE clearance, auto-renewal status, and balance. Status then becomes Bank Verified & Lien Affirmed. 

3. SFMS/AccountAggregatorAdapter: stubbed, with the interface documented as the production path. 

**Signature feature 3: Release gate with parallel clearances + QR NOC** • The rules engine builds a readiness checklist when a release request arrives: documents complete, clearance tasks created for each configured cell, and any pending verification. 

- Cells work in parallel from their own task queues. The institution sees "Waiting on: Vigilance (3 days)" instead of a vague "Pending". 

- The **Release** button stays disabled until prerequisites pass. The competent authority still makes the final call. Per the PS, this is "authorization by the competent authority", so the system never auto-releases. 

- On approval, generate a PDF NOC with a QR code. The QR opens a public /verify/{id} page that checks an Ed25519 signature (mock DSC) and shows the status live. 

## **<u>3. Everything else needed to cover the PS, mapped</u>** 

|1. Central repository|Institution registry + FDR repository|Search, filters, linked documents|
|---|---|---|
|2. Document management|MinIO, versioned, signed short-lived<br>URLs|Never overwrite a version|
|3. Verification +<br>discrepancy|Dual-pass pipeline + issue queue|Feature 2 above|
|4. Validity/maturity tracking|Date engine + reminders|Offsets configurable, default 90/60/30/15/7/1|
|5. Renewal/replacement|Lineage view|Old and new instrument linked, field-level diff,<br>current version marked|
|6. Release/refund workflow|Feature 3|Includes refund path|
|7. Alerts + escalation|Celery beat + Redis|Reminder, then unacknowledged detection,<br>then escalate to supervisor|
|8. Dashboard + reports|Next.js + Recharts|Active, expiring, matured, renewed, released,<br>pending. CSV/PDF export|
|9. Audit + access control|Hash-chained audit log + RBAC +|Details below|



||Postgres RLS||
|---|---|---|
|10. Integration + security|Adapter layer, AES-256 at rest, TLS|Bulk CSV import for legacy registers|



AICTE FinTrust · SIH26265 · Final Merged Implementation Plan Page 2 

### **Lifecycle state machine** 

- Draft → Submitted → Under Scrutiny ⇄ Query Raised (institution corrects) → → Bank Verification Pending Bank Verified (Active, locked) 

- → Maturity Window → Renewed/Replaced (new FDR linked) → Overdue → Escalated → Encashment Notice Drafted → Release Requested → Clearances → Released 

Build it as a transition table in Postgres plus a small Python guard function per transition. It's easy to demo and test, and you don't need a library. 

### **Alerts that are useful** 

Each alert states the action, the deadline, the owner and the consequence of ignoring it. Example: _"FDR SBI-xxxx matures in 30 days. Action: submit a renewal FDR. Owner: Registrar, ABC Trust. If missed: escalated to the Regional Officer on [date]."_ Alerts need an acknowledge button, and unacknowledged ones escalate. 

### **Default-encashment trigger (safe version)** 

If an FDR stays overdue past the configured window, the system **drafts** a demand notice PDF and sends it to an officer's approval queue. An officer approves and signs it. It never goes out on its own. 

### **Audit chain** 

H_n = SHA256(H_{n-1} || action || payload_hash || user_id || timestamp). Add an **"Verify chain integrity"** button on the audit page that walks the chain and shows green. In the demo, edit one row directly in the database and run it again to show it turn red. That moment sells the feature. 

### **Versioned rules engine** 

Rules live in a table with rule_id, source_ref (handbook clause), version, effective_from, condition_json and severity. Reference the release clause as **6.46 (2024–27 handbook)** , but confirm the wording in the actual handbook before putting it on a slide, since an older version numbers it 7.51. Don't hardcode deposit amounts. Keep them in config by institution category and handbook year. 

### **Usability touches (these separate good from decent)** 

- **Institution home = "What do I do next?"** One prioritised action list (fix flagged amount, upload renewal, respond to query), not a data table. 

- **Pre-submission checklist** and save-as-draft, so rejections drop. 

- **"Why is this pending?" panel** , generated deterministically from the rules engine's failed checks. No LLM needed, so it can't hallucinate. This replaces the chatbot idea. 

- **Officer review queue** sorted by risk and age, with a two-column view: document on the left, extracted fields 

- on the right, with accept/correct per field and keyboard shortcuts. • **Plain-language statuses** plus an English/Hindi toggle for static labels. 

- **Responsive layout** , because regional officers will check on phones. 

- **Bulk CSV import** with a downloadable error report for legacy registers. 

### **Reconciliation (add in phase 2)** 

Upload a bank credit statement CSV (simulated). The engine matches principal and interest credits to FDRs by reference and amount, and mismatches go to an exceptions queue. It's a small feature, but it covers the "manual reconciliation bottleneck" story. 

AICTE FinTrust · SIH26265 · Final Merged Implementation Plan Page 3 

## **<u>4. Final tech stack</u>** 

|Frontend|Next.js 14, TypeScript, Tailwind, shadcn/ui, TanStack Table, React Hook Form + Zod, Recharts|
|---|---|
|Backend|FastAPI, Pydantic v2, SQLAlchemy 2, Alembic|
|DB|PostgreSQL 16, with**Row-Level Security**keyed on institution_id via SET LOCAL per request, so isolation<br>is enforced in the database|
|Storage|MinIO, server-side AES-256 (SSE), presigned URLs under 5 minutes|
|Jobs|Celery + Redis, Celery beat for reminders, with idempotency keys so alerts never double-send|
|OCR/forensics|PyMuPDF, PaddleOCR (Tesseract fallback), OpenCV for signature/stamp region crop, pikepdf for<br>revision checks|
|Auth|JWT with refresh, argon2 hashes, TOTP 2FA for officer and admin roles|
|Signing|cryptography library, Ed25519 for NOC and notices|
|Email|Mailpit locally, SMTP in prod. SMS and WhatsApp mocked|
|Testing|Pytest (include permission tests), Playwright for the demo flow|
|Packaging|Docker Compose for everything, GitHub Actions CI|



## **5. Roles** 

Institution Admin · Scrutiny Officer · Clearance Officer (scoped per cell) · Regulation Bureau Supervisor / Competent Authority · System Admin/Auditor. Admin can manage users but cannot approve a release. Test that explicitly. 

## **6. Build order** 

**Phase 1 (must be solid before anything else):** auth + RBAC + RLS, institution registry, FDR submission with MinIO, state machine, date engine with alerts and escalation, release request with clearance tasks, dashboard, audit chain. 

**Phase 2 (the wow layer):** OCR + field provenance + mismatch UI, duplicate/tamper flags, bank signed-link loop, rules engine with versions, NOC with QR verify page, reconciliation. 

**Phase 3 (if time remains):** bulk import, analytics on stage-wise timings, Hindi labels, heatmap by bank/region. 

A split that works for four people: (1) frontend, (2) core backend and state machine, (3) OCR/forensics and synthetic data, (4) bank adapter, rules engine, notifications and testing. 

## **7. Build a test dataset early** 

Generate 30 or so synthetic FDR PDFs with reportlab in 3 or 4 bank layouts (SBI, PNB, HDFC style). Include a few scanned, a few tampered (edited amount, extra revision), and a few duplicates. This gives you **real accuracy numbers** for the PPT: field extraction accuracy, mismatches caught, tamper flags raised. That is far stronger than invented percentages. 

Metrics to measure and show: OCR field accuracy, time to review one FDR manually versus with side-by-side, share of deadlines alerted before they passed, and share of actions with an audit record (target 100%). 

## **8. Demo script (about 3 minutes)** 

1. The institution uploads an FDR. OCR fills the form and flags 1,00,000 vs 10,00,000. ₹ ₹ 

AICTE FinTrust · SIH26265 · Final Merged Implementation Plan Page 4 

2. The institution fixes it. The officer sees amber badges, sends the bank link, and the bank page confirms. The badge turns green: _Bank Verified & Lien Affirmed_ . 

3. Fast-forward the clock. A 30-day maturity alert fires, and left unacknowledged it escalates. 4. The institution files a release request. The Vigilance clearance is pending, so the Release button stays locked and the panel says why. 

5. Clearances complete. The authority approves, a QR NOC is generated, and scanning it opens the verify page. 

6. Tamper one audit row in the DB, click verify, and watch it fail. 

## **9. Slide and wording cautions** 

- Label everything simulated as simulated. The judges will respect that, and the PS itself says integration should be used "where technically feasible and formally authorized". 

- Use your keywords: Bank-Affirmed Lien Verification, Field-Level Provenance, Versioned Compliance Rules Engine, Release Readiness Gate, Hash-Chained Audit Ledger, RBAC + RLS, AES-256, DPDP Act 2023, TAT. 

- Don't use real FDRs anywhere, only synthetic data. 

I can turn this into the 6-slide PPT content, a database schema (tables for FDR, field provenance, clearance tasks, audit chain), or the API route list next. Which would you like first? 

AICTE FinTrust · SIH26265 · Final Merged Implementation Plan Page 5 

