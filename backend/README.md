# AICTE FinTrust - Core Backend Engine

> **SIH Problem Statement SIH26265 · Security Deposit & Fixed Deposit Receipt (FDR) Management Portal**

The **AICTE FinTrust Backend** is an enterprise-grade FastAPI service engineered around three signature architectural guarantees:
1. **Field-Level Provenance & Dual-Pass Verification**: Tracks the verifiable source tier (`INSTITUTION_ENTERED` $\to$ `OCR_EXTRACTED` $\to$ `OFFICER_VERIFIED` $\to$ `BANK_CONFIRMED`) with `PyMuPDF` text layer extraction, `pikepdf` forensic tamper detection (multiple `%%EOF` incremental revisions, creator/producer metadata anomalies), and side-by-side discrepancy flagging (e.g., ₹10,00,000 vs ₹1,00,000).
2. **Cryptographic SHA-256 Hash-Chained Audit Ledger**: Every mutation calculates $H_n = \text{SHA256}(H_{n-1} + \text{action} + \text{payload\_hash} + \text{user\_id} + \text{timestamp})$ with real-time integrity verification that detects database tampering.
3. **Parallel Clearance Gates & Digital NOC Verification**: Concurrent clearance tasks (`PGRC`, `VIGILANCE`, `APPROVAL_BUREAU`, `LEGAL`, `FINANCE`) enforcing release locks until all prerequisites pass, followed by Ed25519 digital signature signing (mock DSC) and ReportLab QR-embedded NOC PDF generation.

---

## 🛠️ Tech Stack & Infrastructure

- **Framework**: FastAPI (Python 3.11+) with Pydantic v2
- **ORM & Database**: SQLAlchemy 2.0 Async Engine with `asyncpg` on **PostgreSQL 16**
- **Object Storage**: MinIO with AES-256 Server-Side Encryption (SSE-S3)
- **Cache & Jobs**: Redis 7
- **Forensics & OCR**: `pymupdf` (text layer), `pikepdf` (`%%EOF` inspection & metadata forensics)
- **Cryptographic Signing**: `cryptography` (Ed25519)
- **PDF Generation**: ReportLab & `qrcode[pil]`
- **Test Suite**: Pytest with `pytest-asyncio`

---

## 🚀 Quickstart Guide

### 1. Start Infrastructure Services
Start PostgreSQL, MinIO, and Redis in detached mode:
```bash
docker compose up -d
```

### 2. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 3. Seed the Database
Populate the 3 sample AICTE institutions, 12 FDRs covering all lifecycle states (`DRAFT`, `ACTIVE`, `MATURED`, `RELEASE_REQUESTED`), 5 parallel clearance tasks (with gate-lock), active reminder alerts, and the unbroken SHA-256 audit chain:

```bash
cd backend
python -m scripts.seed_database
```

#### Offline / Local SQLite Mode
If developing offline without Docker containers running, run with the `--sqlite` flag:
```bash
python -m scripts.seed_database --sqlite
```

#### Clean & Reseed
To purge existing records and perform a clean re-seed:
```bash
python -m scripts.seed_database --clean
```

### 4. Run the API Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- Interactive Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- Alternative ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health Check: [http://localhost:8000/api/health](http://localhost:8000/api/health)

### 5. Run the Test Suite
Execute the 43 comprehensive unit and integration tests:
```bash
pytest -v
```

---

## 🏢 Sample Seeded Dataset

| Institution Name | AICTE Permanent ID | State | Sample Instruments Seeded | Clearance Gate Lock Status |
| :--- | :--- | :--- | :--- | :--- |
| **Government College of Engineering** | `1-1002345` | Maharashtra | `SBI-DRAFT-2026-001` (Draft)<br>`SBI-ACT-2023-1001` (Active)<br>`SBI-MAT-2021-2001` (Matures in 15d)<br>`SBI-REL-2021-3001` (Release Requested) | **Gate Locked**: 4 Approved, `VIGILANCE` Pending |
| **Vasantdada Institute of Technology** | `1-1004567` | Delhi | `PNB-DRAFT-2026-002` (Draft)<br>`PNB-ACT-2022-1002` (Active)<br>`PNB-MAT-2021-2002` (Matures in 15d)<br>`PNB-REL-2021-3002` (Release Requested) | **Gate Locked**: 4 Approved, `LEGAL` Pending |
| **National Institute of Advanced Studies** | `1-1008910` | Karnataka | `HDFC-DRAFT-2026-003` (Draft)<br>`CAN-ACT-2023-1003` (Active)<br>`HDFC-MAT-2021-2003` (Matured/Escalated)<br>`CAN-REL-2021-3003` (Release Requested) | **Gate Locked**: 4 Approved, `FINANCE` Pending |

---

## 📡 API Endpoint Overview

| Module | Method | Path | Description |
| :--- | :--- | :--- | :--- |
| **FDR** | `POST` | `/api/v1/fdr/draft` | Create or update draft FDR instrument |
| **FDR** | `POST` | `/api/v1/fdr/{id}/submit` | Submit draft into scrutiny pipeline (transitions to `SUBMITTED`) |
| **FDR** | `GET` | `/api/v1/fdr/{id}` | Get full FDR details, provenance badges, and clearance states |
| **FDR** | `GET` | `/api/v1/fdr/institution/{inst_id}` | Retrieve all FDRs deposited by an institution |
| **FDR** | `POST` | `/api/v1/fdr/{id}/upload-document` | Upload PDF to MinIO with server-side AES-256 encryption |
| **FDR** | `GET` | `/api/v1/fdr/{id}/document-url` | Generate temporary presigned download URL ($\le 300\text{s}$) |
| **FDR** | `POST` | `/api/v1/fdr/{id}/validate-ocr` | Run Dual-Pass extraction & side-by-side discrepancy check |
| **OCR** | `POST` | `/api/v1/ocr/{id}/process` | Pass 1 Extraction, tamper forensics, and duplicate detection |
| **OCR** | `GET` | `/api/v1/ocr/{id}/discrepancies` | Pass 2 Side-by-side mismatch comparison with color badges |
| **OCR** | `POST` | `/api/v1/ocr/{id}/verify-field` | Officer verification endpoint upgrading provenance |
| **Clearance** | `POST` | `/api/v1/clearance/{fdr_id}/request-release` | Initialize 5 parallel clearance tasks (`PGRC`, `VIGILANCE`, etc.) |
| **Clearance** | `PUT` | `/api/v1/clearance/{task_id}/action` | Officer signs off or rejects a cell clearance |
| **Clearance** | `POST` | `/api/v1/clearance/{fdr_id}/approve-release` | Competent Authority approves release & generates Ed25519 QR NOC |
| **Verify** | `GET` | `/api/v1/verify/{fdr_id}` | Public endpoint verifying Ed25519 digital signature & NOC download |
| **Reminders** | `GET` | `/api/v1/reminders/active` | Get active reminders & supervisor escalations |
| **Reminders** | `POST` | `/api/v1/reminders/{id}/acknowledge` | Acknowledge reminder alert to halt escalation |
| **Audit** | `GET` | `/api/v1/audit/trail` | View paginated audit ledger events |
| **Audit** | `GET` | `/api/v1/audit/verify` | Walk the SHA-256 hash chain and report broken links |
| **Health** | `GET` | `/api/health` | Service and infrastructure health check |
