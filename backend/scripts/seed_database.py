"""
AICTE FinTrust - Comprehensive Database Seeding Script
Populates sample AICTE institutions, FDR instruments across distinct lifecycle states,
field provenance tags, parallel clearance tasks, active reminder alerts, and an
unbroken cryptographic SHA-256 hash-chained audit trail.

Usage:
    python -m scripts.seed_database
    python -m scripts.seed_database --sqlite
    python -m scripts.seed_database --clean
"""

import argparse
import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import os
import sys
from typing import Optional

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import Base, engine as default_engine
from app.models.audit import AuditLog
from app.models.clearance import Clearance, ClearanceCell, ClearanceStatus
from app.models.fdr import FDR, FDRStatus
from app.models.institution import Institution
from app.models.provenance import Provenance, ProvenanceSourceType
from app.models.reminder import ReminderAlert, ReminderStatus, ReminderType
from app.services.audit_service import AuditService


async def clean_database(session: AsyncSession) -> None:
    """Removes all previously seeded data while maintaining foreign key integrity."""
    print("[CLEAN] Cleaning existing data from database tables...")
    await session.execute(delete(Clearance))
    await session.execute(delete(Provenance))
    await session.execute(delete(ReminderAlert))
    await session.execute(delete(AuditLog))
    await session.execute(delete(FDR))
    await session.execute(delete(Institution))
    await session.commit()
    print("[CLEAN] Existing records purged cleanly.")


async def seed_data(session: AsyncSession) -> None:
    """Executes full database population with institutions, FDRs, clearances, and audit logs."""
    today = date.today()

    print("\n[STEP 1] Seeding AICTE Approved Institutions...")
    institutions_spec = [
        {
            "aicte_permanent_id": "1-1002345",
            "name": "Government College of Engineering",
            "state": "Maharashtra",
            "email": "principal@gcoek.ac.in",
        },
        {
            "aicte_permanent_id": "1-1004567",
            "name": "Vasantdada Institute of Technology",
            "state": "Delhi",
            "email": "director@vitdelhi.ac.in",
        },
        {
            "aicte_permanent_id": "1-1008910",
            "name": "National Institute of Advanced Studies",
            "state": "Karnataka",
            "email": "dean@nias.ac.in",
        },
    ]

    institutions = []
    for spec in institutions_spec:
        # Check if already exists
        stmt = select(Institution).where(Institution.aicte_permanent_id == spec["aicte_permanent_id"])
        res = await session.execute(stmt)
        inst = res.scalar_one_or_none()
        if not inst:
            inst = Institution(
                aicte_permanent_id=spec["aicte_permanent_id"],
                name=spec["name"],
                state=spec["state"],
                email=spec["email"],
            )
            session.add(inst)
            await session.flush()

            # Record Chained Audit Entry
            await AuditService.record_event(
                session=session,
                action="INSTITUTION_REGISTERED",
                payload={
                    "institution_id": inst.id,
                    "aicte_permanent_id": inst.aicte_permanent_id,
                    "name": inst.name,
                    "state": inst.state,
                },
                user_id="SYSTEM_ADMIN",
                details=f"AICTE permanent institution '{inst.name}' registered.",
            )
        institutions.append(inst)
        print(f"   [+] Institution #{inst.id}: {inst.name} ({inst.aicte_permanent_id}) - {inst.state}")

    print("\n[STEP 2] Seeding Fixed Deposit Receipts (FDRs) across lifecycle states...")

    # Data matrix: 4 FDR archetypes per institution
    # Archetype A: DRAFT (Provenance: INSTITUTION_ENTERED)
    # Archetype B: ACTIVE (5-year tenure, Provenance: BANK_CONFIRMED)
    # Archetype C: MATURED / Maturity Window (Due in 15 days, Active Reminder Alerts)
    # Archetype D: RELEASE_REQUESTED (5 parallel clearances: 4 APPROVED, 1 PENDING to gate-lock)

    fdr_templates = [
        # Institution 1: Government College of Engineering
        (
            institutions[0],
            FDRStatus.DRAFT,
            "SBI-DRAFT-2026-001",
            "State Bank of India",
            "SBIN0001234",
            Decimal("1500000.00"),
            Decimal("7.10"),
            today - timedelta(days=10),
            today + timedelta(days=1815),
            "INSTITUTION_ENTERED",
            None,
        ),
        (
            institutions[0],
            FDRStatus.ACTIVE,
            "SBI-ACT-2023-1001",
            "State Bank of India",
            "SBIN0001234",
            Decimal("3500000.00"),
            Decimal("7.25"),
            today - timedelta(days=730),  # Issued 2 years ago
            today + timedelta(days=1095), # Matures in 3 years (5-year total tenure)
            "BANK_CONFIRMED",
            None,
        ),
        (
            institutions[0],
            FDRStatus.ACTIVE,
            "SBI-MAT-2021-2001",
            "State Bank of India",
            "SBIN0001234",
            Decimal("2500000.00"),
            Decimal("6.85"),
            today - timedelta(days=1810), # Issued 5 years ago
            today + timedelta(days=15),   # Due in 15 days!
            "BANK_CONFIRMED",
            "MATURITY_WINDOW_15D",
        ),
        (
            institutions[0],
            FDRStatus.RELEASE_REQUESTED,
            "SBI-REL-2021-3001",
            "State Bank of India",
            "SBIN0001234",
            Decimal("5000000.00"),
            Decimal("7.50"),
            today - timedelta(days=1825), # 5 years ago
            today - timedelta(days=5),    # Matured 5 days ago
            "BANK_CONFIRMED",
            "RELEASE_GATE_VIGILANCE_LOCKED",
        ),

        # Institution 2: Vasantdada Institute of Technology
        (
            institutions[1],
            FDRStatus.DRAFT,
            "PNB-DRAFT-2026-002",
            "Punjab National Bank",
            "PUNB0123400",
            Decimal("2000000.00"),
            Decimal("7.05"),
            today - timedelta(days=5),
            today + timedelta(days=1820),
            "INSTITUTION_ENTERED",
            None,
        ),
        (
            institutions[1],
            FDRStatus.ACTIVE,
            "PNB-ACT-2022-1002",
            "Punjab National Bank",
            "PUNB0123400",
            Decimal("4000000.00"),
            Decimal("7.20"),
            today - timedelta(days=1095), # Issued 3 years ago
            today + timedelta(days=730),  # Matures in 2 years
            "BANK_CONFIRMED",
            None,
        ),
        (
            institutions[1],
            FDRStatus.ACTIVE,
            "PNB-MAT-2021-2002",
            "Punjab National Bank",
            "PUNB0123400",
            Decimal("3000000.00"),
            Decimal("6.90"),
            today - timedelta(days=1810),
            today + timedelta(days=15),   # Due in 15 days!
            "BANK_CONFIRMED",
            "MATURITY_WINDOW_15D",
        ),
        (
            institutions[1],
            FDRStatus.RELEASE_REQUESTED,
            "PNB-REL-2021-3002",
            "Punjab National Bank",
            "PUNB0123400",
            Decimal("4500000.00"),
            Decimal("7.40"),
            today - timedelta(days=1830),
            today - timedelta(days=10),
            "BANK_CONFIRMED",
            "RELEASE_GATE_LEGAL_LOCKED",
        ),

        # Institution 3: National Institute of Advanced Studies
        (
            institutions[2],
            FDRStatus.DRAFT,
            "HDFC-DRAFT-2026-003",
            "HDFC Bank",
            "HDFC0001234",
            Decimal("2500000.00"),
            Decimal("7.20"),
            today - timedelta(days=2),
            today + timedelta(days=1823),
            "INSTITUTION_ENTERED",
            None,
        ),
        (
            institutions[2],
            FDRStatus.ACTIVE,
            "CAN-ACT-2023-1003",
            "Canara Bank",
            "CNRB0001234",
            Decimal("5000000.00"),
            Decimal("7.30"),
            today - timedelta(days=365),  # Issued 1 year ago
            today + timedelta(days=1460), # Matures in 4 years
            "BANK_CONFIRMED",
            None,
        ),
        (
            institutions[2],
            FDRStatus.MATURED,
            "HDFC-MAT-2021-2003",
            "HDFC Bank",
            "HDFC0001234",
            Decimal("3500000.00"),
            Decimal("6.95"),
            today - timedelta(days=1835),
            today - timedelta(days=5),    # Matured 5 days ago
            "BANK_CONFIRMED",
            "OVERDUE_MATURED",
        ),
        (
            institutions[2],
            FDRStatus.RELEASE_REQUESTED,
            "CAN-REL-2021-3003",
            "Canara Bank",
            "CNRB0001234",
            Decimal("6000000.00"),
            Decimal("7.55"),
            today - timedelta(days=1840),
            today - timedelta(days=15),
            "BANK_CONFIRMED",
            "RELEASE_GATE_FINANCE_LOCKED",
        ),
    ]

    total_fdrs_seeded = 0
    total_clearances_seeded = 0
    total_reminders_seeded = 0

    for (
        inst,
        status,
        fdr_num,
        bank,
        ifsc,
        amount,
        rate,
        issue_d,
        mat_d,
        prov_source,
        special_mode,
    ) in fdr_templates:
        # Check existing FDR
        stmt = select(FDR).where(FDR.fdr_number == fdr_num)
        res = await session.execute(stmt)
        fdr = res.scalar_one_or_none()
        if not fdr:
            fdr = FDR(
                institution_id=inst.id,
                fdr_number=fdr_num,
                bank_name=bank,
                ifsc_code=ifsc,
                principal_amount=amount,
                interest_rate=rate,
                issue_date=issue_d,
                maturity_date=mat_d,
                lien_holder="AICTE",
                status=status,
            )
            session.add(fdr)
            await session.flush()
            total_fdrs_seeded += 1

            # Log Chained Audit Record for FDR Creation
            await AuditService.record_event(
                session=session,
                action="FDR_INITIALIZED",
                payload={
                    "fdr_id": fdr.id,
                    "institution_id": inst.id,
                    "fdr_number": fdr.fdr_number,
                    "bank_name": fdr.bank_name,
                    "principal_amount": str(fdr.principal_amount),
                    "status": fdr.status.value,
                },
                user_id=f"INSTITUTION_{inst.id}",
                details=f"FDR instrument {fdr.fdr_number} deposited in state {fdr.status.value}.",
            )

            # Seed Field Provenance Records
            source_enum = (
                ProvenanceSourceType.BANK_CONFIRMED
                if prov_source == "BANK_CONFIRMED"
                else ProvenanceSourceType.INSTITUTION_ENTERED
            )

            fields_to_track = [
                ("fdr_number", fdr.fdr_number),
                ("bank_name", fdr.bank_name),
                ("ifsc_code", fdr.ifsc_code),
                ("principal_amount", str(fdr.principal_amount)),
                ("interest_rate", str(fdr.interest_rate)),
                ("issue_date", str(fdr.issue_date)),
                ("maturity_date", str(fdr.maturity_date)),
                ("lien_holder", fdr.lien_holder),
            ]

            for field_name, field_val in fields_to_track:
                prov = Provenance(
                    fdr_id=fdr.id,
                    field_name=field_name,
                    source_type=source_enum,
                    confidence_score=1.0,
                    extracted_value=str(field_val),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(prov)

            await session.flush()

            # Handle Special Modes
            # 1. Maturity Window Alert
            if special_mode == "MATURITY_WINDOW_15D":
                alert = ReminderAlert(
                    fdr_id=fdr.id,
                    institution_id=inst.id,
                    reminder_type=ReminderType.UPCOMING_MATURITY,
                    days_offset=15,
                    due_date=fdr.maturity_date,
                    status=ReminderStatus.PENDING,
                    message=f"FDR {fdr.fdr_number} ({fdr.bank_name}) matures in 15 days on {fdr.maturity_date}. Action required: submit renewal FDR.",
                    recipient=inst.email,
                    assigned_officer_id="REGIONAL_OFFICER_01",
                )
                session.add(alert)
                total_reminders_seeded += 1
                await session.flush()

                await AuditService.record_event(
                    session=session,
                    action="MATURITY_ALERT_GENERATED",
                    payload={"alert_id": alert.id, "fdr_id": fdr.id, "days_offset": 15},
                    user_id="REMINDER_ENGINE",
                    details=f"15-day upcoming maturity alert generated for FDR {fdr.fdr_number}.",
                )

            elif special_mode == "OVERDUE_MATURED":
                alert = ReminderAlert(
                    fdr_id=fdr.id,
                    institution_id=inst.id,
                    reminder_type=ReminderType.OVERDUE_REPLACEMENT,
                    days_offset=1,
                    due_date=fdr.maturity_date,
                    status=ReminderStatus.ESCALATED,
                    message=f"CRITICAL: FDR {fdr.fdr_number} is overdue past maturity ({fdr.maturity_date}). Escalated to Regional Director.",
                    recipient=inst.email,
                    assigned_officer_id="REGIONAL_OFFICER_HEAD",
                )
                session.add(alert)
                total_reminders_seeded += 1
                await session.flush()

                await AuditService.record_event(
                    session=session,
                    action="MATURITY_ALERT_ESCALATED",
                    payload={"alert_id": alert.id, "fdr_id": fdr.id, "status": "ESCALATED"},
                    user_id="REMINDER_ENGINE",
                    details=f"Overdue FDR {fdr.fdr_number} escalated to Regional Officer Head.",
                )

            # 2. Release Gate Clearances (4 APPROVED, 1 PENDING)
            if special_mode and special_mode.startswith("RELEASE_GATE_"):
                locked_cell = ClearanceCell.VIGILANCE
                if "LEGAL" in special_mode:
                    locked_cell = ClearanceCell.LEGAL
                elif "FINANCE" in special_mode:
                    locked_cell = ClearanceCell.FINANCE

                cells = [
                    ClearanceCell.PGRC,
                    ClearanceCell.VIGILANCE,
                    ClearanceCell.APPROVAL_BUREAU,
                    ClearanceCell.LEGAL,
                    ClearanceCell.FINANCE,
                ]

                for cell in cells:
                    is_locked = cell == locked_cell
                    cell_status = ClearanceStatus.PENDING if is_locked else ClearanceStatus.APPROVED
                    remarks = (
                        f"{cell.value} cell review underway. Pending nodal inquiry dispatch."
                        if is_locked
                        else f"{cell.value} cell verified and approved. Clearance granted."
                    )
                    officer = f"OFFICER_{cell.value}_01"

                    clearance = Clearance(
                        fdr_id=fdr.id,
                        cell_name=cell,
                        status=cell_status,
                        remarks=remarks,
                        officer_id=officer,
                    )
                    session.add(clearance)
                    total_clearances_seeded += 1

                await session.flush()

                # Audit clearance initialization
                await AuditService.record_event(
                    session=session,
                    action="CLEARANCE_TASKS_INITIALIZED",
                    payload={
                        "fdr_id": fdr.id,
                        "total_cells": 5,
                        "pending_cell": locked_cell.value,
                        "release_gate_status": "LOCKED",
                    },
                    user_id=f"INSTITUTION_{inst.id}",
                    details=f"Parallel clearance gate initialized for FDR {fdr.fdr_number} (Gate locked on {locked_cell.value}).",
                )

        badge_info = f"[{fdr.status.value}]"
        print(f"   [+] FDR #{fdr.id}: {fdr.fdr_number} - {fdr.bank_name} - Rs. {fdr.principal_amount:,.2f} {badge_info}")

    await session.commit()

    print("\n[STEP 3] Verifying Cryptographic Hash Chain Integrity...")
    audit_report = await AuditService.verify_chain_integrity(session)
    print(f"   [+] Total Audit Records: {audit_report['total_records']}")
    print(f"   [+] Chain Integrity Valid: {audit_report['is_valid']}")
    print(f"   [+] Broken Links: {len(audit_report['broken_links'])}")

    if audit_report["is_valid"]:
        print("\n[SUCCESS] Database seeding completed successfully! All audit hashes verified 100% green.\n")
    else:
        print("\n[WARNING] Cryptographic audit chain integrity check failed.\n")


async def main() -> None:
    parser = argparse.ArgumentParser(description="AICTE FinTrust Database Seeding Script")
    parser.add_argument("--db-url", type=str, default=None, help="Custom database connection URL")
    parser.add_argument("--sqlite", action="store_true", help="Seed in-memory or local SQLite database")
    parser.add_argument("--clean", action="store_true", help="Purge existing records before seeding")
    args = parser.parse_args()

    # Determine connection engine
    target_engine = default_engine
    if args.sqlite:
        db_file = os.path.join(BACKEND_DIR, "fintrust_seed.db").replace("\\", "/")
        sqlite_url = f"sqlite+aiosqlite:///{db_file}"
        print(f"[DB] Using SQLite database for seeding: {sqlite_url}")
        target_engine = create_async_engine(sqlite_url, echo=False)
    elif args.db_url:
        print(f"[DB] Using custom database URL: {args.db_url}")
        target_engine = create_async_engine(args.db_url, echo=False)
    else:
        print(f"[DB] Connecting to PostgreSQL database: {settings.DATABASE_URL}")

    # Initialize tables
    try:
        async with target_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as conn_exc:
        print(f"\n[ERROR] Failed to connect to database at {target_engine.url}: {conn_exc}", file=sys.stderr)
        if "postgresql" in str(target_engine.url):
            print(
                "\n[TIP] Ensure PostgreSQL is running via Docker Compose:\n"
                "       docker compose up -d\n"
                "       Or test offline with the SQLite flag:\n"
                "       python -m scripts.seed_database --sqlite\n",
                file=sys.stderr,
            )
        sys.exit(1)

    session_maker = async_sessionmaker(
        bind=target_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        try:
            if args.clean:
                await clean_database(session)
            await seed_data(session)
        except Exception as exc:
            await session.rollback()
            print(f"\n[ERROR] Error during database seeding: {exc}", file=sys.stderr)
            raise
        finally:
            await session.close()
            await target_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
