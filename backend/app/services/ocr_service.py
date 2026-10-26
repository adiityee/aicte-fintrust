from datetime import date, datetime, timezone
from decimal import Decimal
import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import pikepdf
import pymupdf
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.fdr import FDR, FDRStatus
from app.models.provenance import Provenance, ProvenanceSourceType
from app.schemas.ocr import (
    DiscrepancyFieldComparison,
    DiscrepancyReportResponse,
    DuplicateCheckResult,
    ExtractedFieldItem,
    OCRExtractionResponse,
    TamperIndicatorItem,
)
from app.services.audit_service import AuditService

KNOWN_BANKS = [
    ("State Bank of India", ["SBI", "STATE BANK OF INDIA"]),
    ("Punjab National Bank", ["PNB", "PUNJAB NATIONAL BANK"]),
    ("HDFC Bank", ["HDFC", "HDFC BANK"]),
    ("ICICI Bank", ["ICICI", "ICICI BANK"]),
    ("Canara Bank", ["CANARA", "CANARA BANK"]),
    ("Bank of Baroda", ["BOB", "BANK OF BARODA"]),
    ("Axis Bank", ["AXIS", "AXIS BANK"]),
    ("Union Bank of India", ["UBI", "UNION BANK OF INDIA", "UNION BANK"]),
    ("Indian Bank", ["INDIAN BANK"]),
    ("Bank of India", ["BOI", "BANK OF INDIA"]),
    ("Central Bank of India", ["CENTRAL BANK OF INDIA"]),
    ("Kotak Mahindra Bank", ["KOTAK", "KOTAK MAHINDRA BANK"]),
]

SUSPICIOUS_SOFTWARE = [
    "canva",
    "photoshop",
    "gimp",
    "ilovepdf",
    "sejda",
    "pdfescape",
    "inkscape",
    "smallpdf",
    "pdf2go",
    "foxit phantom",
]


class OCRService:
    """
    Dual-Pass Verification & Forensics Engine
    Pass 1: Text layer extraction with regex anchors and confidence scoring.
    Tamper Detection: Multiple %%EOF revisions, metadata inspection, font anomalies.
    Duplicate Detection: SHA-256 duplicate checking & cross-institution reuse.
    Pass 2: Side-by-side discrepancy validation against submitted form data.
    """

    @staticmethod
    def parse_amount(raw_str: str) -> Optional[Decimal]:
        """Normalize currency and Indian numbering format (e.g. '10,00,000.00' -> Decimal('1000000.00'))."""
        if not raw_str:
            return None
        clean = re.sub(r"[^\d\.]", "", raw_str.strip())
        if not clean:
            return None
        try:
            return Decimal(clean)
        except Exception:
            return None

    @staticmethod
    def parse_date(date_str: str) -> Optional[date]:
        """Parse varied Indian date formats (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD)."""
        if not date_str:
            return None
        clean = date_str.strip()
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y"):
            try:
                return datetime.strptime(clean, fmt).date()
            except ValueError:
                continue
        return None

    @classmethod
    def extract_from_pdf(cls, pdf_bytes: bytes) -> Tuple[Dict[str, ExtractedFieldItem], int, int]:
        """
        Pass 1: Extract full text layer from PDF using PyMuPDF and detect key FDR fields.
        Returns (extracted_fields_dict, text_length, page_count).
        """
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)
        full_text_pages = [page.get_text() for page in doc]
        full_text = "\n".join(full_text_pages)
        text_length = len(full_text.strip())

        extracted: Dict[str, ExtractedFieldItem] = {}

        # 1. FDR Number
        fdr_match = re.search(
            r"(?:(?:FDR|FD|RECEIPT|FIXED\s+DEPOSIT|ACCOUNT|A\/C)\s*(?:NO\.?|NUMBER|#|REF)\s*[:\-\.]?|(?:FDR|FD)\s*[:\-\.])\s*([A-Za-z0-9\/\-]{5,30})",
            full_text,
            re.IGNORECASE,
        )
        if not fdr_match:
            fdr_match = re.search(
                r"\b(?:FDR|FD|RECEIPT)[\s\-:]+([A-Za-z0-9\/\-]{6,25})\b",
                full_text,
                re.IGNORECASE,
            )

        fdr_val = None
        if fdr_match:
            candidate = fdr_match.group(1).strip()
            if candidate.upper() not in {"RECEIPT", "DEPOSIT", "SECURITY", "CERTIFICATE", "NUMBER"}:
                fdr_val = candidate

        if fdr_val:
            extracted["fdr_number"] = ExtractedFieldItem(
                field_name="fdr_number",
                extracted_value=fdr_val,
                confidence_score=0.96,
                source_snippet=fdr_match.group(0),
                needs_human_review=False,
            )
        else:
            extracted["fdr_number"] = ExtractedFieldItem(
                field_name="fdr_number",
                extracted_value=None,
                confidence_score=0.0,
                source_snippet=None,
                needs_human_review=True,
            )

        # 2. Bank Name
        matched_bank = None
        matched_snippet = None
        for canonical, aliases in KNOWN_BANKS:
            for alias in aliases:
                idx = full_text.upper().find(alias)
                if idx != -1:
                    matched_bank = canonical
                    start = max(0, idx - 20)
                    end = min(len(full_text), idx + len(alias) + 20)
                    matched_snippet = full_text[start:end].strip()
                    break
            if matched_bank:
                break

        if matched_bank:
            extracted["bank_name"] = ExtractedFieldItem(
                field_name="bank_name",
                extracted_value=matched_bank,
                confidence_score=0.96,
                source_snippet=matched_snippet,
                needs_human_review=False,
            )
        else:
            # Generic anchor search
            bank_gen = re.search(r"Bank\s*(?:Name)?\s*[:\-]\s*([A-Za-z\s]{4,35})", full_text, re.IGNORECASE)
            if bank_gen:
                extracted["bank_name"] = ExtractedFieldItem(
                    field_name="bank_name",
                    extracted_value=bank_gen.group(1).strip(),
                    confidence_score=0.82,
                    source_snippet=bank_gen.group(0),
                    needs_human_review=True,
                )
            else:
                extracted["bank_name"] = ExtractedFieldItem(
                    field_name="bank_name",
                    extracted_value=None,
                    confidence_score=0.0,
                    source_snippet=None,
                    needs_human_review=True,
                )

        # 3. IFSC Code
        ifsc_match = re.search(r"\b([A-Z]{4}0[A-Z0-9]{6})\b", full_text)
        if ifsc_match:
            is_anchored = "IFSC" in full_text.upper()
            score = 0.98 if is_anchored else 0.90
            extracted["ifsc_code"] = ExtractedFieldItem(
                field_name="ifsc_code",
                extracted_value=ifsc_match.group(1),
                confidence_score=score,
                source_snippet=ifsc_match.group(0),
                needs_human_review=score < 0.85,
            )
        else:
            extracted["ifsc_code"] = ExtractedFieldItem(
                field_name="ifsc_code",
                extracted_value=None,
                confidence_score=0.0,
                source_snippet=None,
                needs_human_review=True,
            )

        # 4. Principal Amount
        amt_match = re.search(
            r"(?:Principal\s*Amount|Deposit\s*Amount|Deposit\s*Value|Sum\s*of\s*Rupees|Amount\s*(?:\(Rs\.?\))?)\s*[:\-]?\s*(?:Rs\.?|INR|₹)?\s*([0-9]{1,2}(?:,[0-9]{2})*,[0-9]{3}(?:\.[0-9]{2})?|[0-9]{4,10}(?:\.[0-9]{2})?)",
            full_text,
            re.IGNORECASE,
        )
        if amt_match:
            raw_amt = amt_match.group(1)
            parsed_amt = cls.parse_amount(raw_amt)
            extracted["principal_amount"] = ExtractedFieldItem(
                field_name="principal_amount",
                extracted_value=str(parsed_amt) if parsed_amt is not None else raw_amt,
                confidence_score=0.96,
                source_snippet=amt_match.group(0),
                needs_human_review=False,
            )
        else:
            # Fallback to currency pattern
            curr_match = re.search(r"(?:₹|Rs\.?|INR)\s*([0-9]{1,2}(?:,[0-9]{2})*,[0-9]{3}(?:\.[0-9]{2})?|[0-9]{4,10})", full_text)
            if curr_match:
                raw_amt = curr_match.group(1)
                parsed_amt = cls.parse_amount(raw_amt)
                extracted["principal_amount"] = ExtractedFieldItem(
                    field_name="principal_amount",
                    extracted_value=str(parsed_amt) if parsed_amt is not None else raw_amt,
                    confidence_score=0.82,
                    source_snippet=curr_match.group(0),
                    needs_human_review=True,
                )
            else:
                extracted["principal_amount"] = ExtractedFieldItem(
                    field_name="principal_amount",
                    extracted_value=None,
                    confidence_score=0.0,
                    source_snippet=None,
                    needs_human_review=True,
                )

        # 5. Interest Rate
        rate_match = re.search(
            r"(?:Interest\s*Rate|Rate\s*of\s*Interest|ROI|Rate)\s*[:\-]?\s*([0-9]{1,2}(?:\.[0-9]{1,2})?)\s*(?:%|\s*percent)",
            full_text,
            re.IGNORECASE,
        )
        if rate_match:
            extracted["interest_rate"] = ExtractedFieldItem(
                field_name="interest_rate",
                extracted_value=rate_match.group(1),
                confidence_score=0.95,
                source_snippet=rate_match.group(0),
                needs_human_review=False,
            )
        else:
            rate_gen = re.search(r"([0-9]{1,2}\.[0-9]{1,2})\s*%\s*(?:p\.?a\.?)?", full_text, re.IGNORECASE)
            if rate_gen:
                extracted["interest_rate"] = ExtractedFieldItem(
                    field_name="interest_rate",
                    extracted_value=rate_gen.group(1),
                    confidence_score=0.84,
                    source_snippet=rate_gen.group(0),
                    needs_human_review=True,
                )
            else:
                extracted["interest_rate"] = ExtractedFieldItem(
                    field_name="interest_rate",
                    extracted_value=None,
                    confidence_score=0.0,
                    source_snippet=None,
                    needs_human_review=True,
                )

        # 6. Issue Date
        issue_match = re.search(
            r"(?:Issue\s*Date|Date\s*of\s*Issue|Deposit\s*Date|Date\s*of\s*Deposit|Booking\s*Date|Effective\s*Date)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4}|\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})",
            full_text,
            re.IGNORECASE,
        )
        if issue_match:
            raw_d = issue_match.group(1)
            parsed_d = cls.parse_date(raw_d)
            extracted["issue_date"] = ExtractedFieldItem(
                field_name="issue_date",
                extracted_value=str(parsed_d) if parsed_d else raw_d,
                confidence_score=0.95,
                source_snippet=issue_match.group(0),
                needs_human_review=False,
            )
        else:
            extracted["issue_date"] = ExtractedFieldItem(
                field_name="issue_date",
                extracted_value=None,
                confidence_score=0.0,
                source_snippet=None,
                needs_human_review=True,
            )

        # 7. Maturity Date
        mat_match = re.search(
            r"(?:Maturity\s*Date|Date\s*of\s*Maturity|Due\s*Date|Valid\s*upto|Expiry\s*Date|Matures\s*on)\s*[:\-]?\s*(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{4}|\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})",
            full_text,
            re.IGNORECASE,
        )
        if mat_match:
            raw_d = mat_match.group(1)
            parsed_d = cls.parse_date(raw_d)
            extracted["maturity_date"] = ExtractedFieldItem(
                field_name="maturity_date",
                extracted_value=str(parsed_d) if parsed_d else raw_d,
                confidence_score=0.95,
                source_snippet=mat_match.group(0),
                needs_human_review=False,
            )
        else:
            extracted["maturity_date"] = ExtractedFieldItem(
                field_name="maturity_date",
                extracted_value=None,
                confidence_score=0.0,
                source_snippet=None,
                needs_human_review=True,
            )

        # 8. Lien Holder
        lien_clause = re.search(
            r"(?:Lien\s*(?:marked\s*)?(?:in\s*favour\s*of|in\s*favor\s*of|to|favouring|favoring)|Security\s*Deposit\s*for|Lien\s*Holder|Lien)\s*[:\-]?\s*([A-Za-z\s\.\(\)]{4,60})",
            full_text,
            re.IGNORECASE,
        )
        if lien_clause:
            holder_text = lien_clause.group(1).strip()
            is_aicte = "AICTE" in holder_text.upper() or "ALL INDIA COUNCIL" in holder_text.upper()
            extracted["lien_holder"] = ExtractedFieldItem(
                field_name="lien_holder",
                extracted_value="AICTE" if is_aicte else holder_text,
                confidence_score=0.98 if is_aicte else 0.85,
                source_snippet=lien_clause.group(0),
                needs_human_review=not is_aicte,
            )
        elif "AICTE" in full_text.upper() or "ALL INDIA COUNCIL FOR TECHNICAL EDUCATION" in full_text.upper():
            extracted["lien_holder"] = ExtractedFieldItem(
                field_name="lien_holder",
                extracted_value="AICTE",
                confidence_score=0.88,
                source_snippet="AICTE mentioned in body text",
                needs_human_review=False,
            )
        else:
            extracted["lien_holder"] = ExtractedFieldItem(
                field_name="lien_holder",
                extracted_value=None,
                confidence_score=0.0,
                source_snippet=None,
                needs_human_review=True,
            )

        return extracted, text_length, page_count

    @classmethod
    def detect_tamper_indicators(
        cls,
        pdf_bytes: bytes,
        issue_date: Optional[date] = None,
    ) -> List[TamperIndicatorItem]:
        """
        Forensics Tamper Indicators (Flag Only - Never 'Fraud'):
        1. Count %%EOF markers for multiple incremental revisions using pikepdf / byte inspection.
        2. Detect editing/graphic software in PDF Producer/Creator metadata.
        3. Check if modification date is significantly after creation date or issue date.
        4. Detect font anomalies or mixed fonts across numeric blocks.
        """
        indicators: List[TamperIndicatorItem] = []

        # 1. Multiple PDF Incremental Revisions (%%EOF count)
        eof_count = pdf_bytes.count(b"%%EOF")
        if eof_count > 1:
            indicators.append(
                TamperIndicatorItem(
                    indicator_code="MULTIPLE_INCREMENTAL_REVISIONS",
                    description=(
                        f"PDF contains {eof_count} incremental revisions (%%EOF markers). "
                        "The document was re-saved or appended to after initial generation."
                    ),
                    severity="HIGH",
                    details={"eof_count": eof_count},
                )
            )

        # 2. Metadata Inspection using pikepdf
        try:
            with pikepdf.open(io.BytesIO(pdf_bytes)) as pdf:
                docinfo = pdf.docinfo
                producer = str(docinfo.get("/Producer", "")).lower()
                creator = str(docinfo.get("/Creator", "")).lower()
                mod_date_raw = str(docinfo.get("/ModDate", ""))
                creation_date_raw = str(docinfo.get("/CreationDate", ""))

                # Check for suspicious editing software
                for tool in SUSPICIOUS_SOFTWARE:
                    if tool in producer or tool in creator:
                        indicators.append(
                            TamperIndicatorItem(
                                indicator_code="SUSPICIOUS_CREATOR_METADATA",
                                description=(
                                    f"Document metadata indicates non-banking editing/design software: "
                                    f"'{producer or creator}'."
                                ),
                                severity="HIGH",
                                details={"producer": producer, "creator": creator, "tool": tool},
                            )
                        )
                        break

                # Check modification date vs creation date
                # Format is typically D:YYYYMMDDHHmmSS...
                if mod_date_raw and creation_date_raw:
                    mod_d_match = re.search(r"D:(\d{4})(\d{2})(\d{2})", mod_date_raw)
                    cre_d_match = re.search(r"D:(\d{4})(\d{2})(\d{2})", creation_date_raw)
                    if mod_d_match and cre_d_match:
                        mod_dt = date(int(mod_d_match.group(1)), int(mod_d_match.group(2)), int(mod_d_match.group(3)))
                        cre_dt = date(int(cre_d_match.group(1)), int(cre_d_match.group(2)), int(cre_d_match.group(3)))
                        # If modified > 2 days after creation
                        if (mod_dt - cre_dt).days > 2:
                            indicators.append(
                                TamperIndicatorItem(
                                    indicator_code="MODIFIED_POST_CREATION",
                                    description=(
                                        f"PDF modified date ({mod_dt}) is significantly later than creation date ({cre_dt})."
                                    ),
                                    severity="MEDIUM",
                                    details={"creation_date": str(cre_dt), "modified_date": str(mod_dt)},
                                )
                            )
                        # If modified after issue date
                        if issue_date and mod_dt > issue_date:
                            indicators.append(
                                TamperIndicatorItem(
                                    indicator_code="MODIFIED_POST_ISSUANCE",
                                    description=(
                                        f"PDF modification timestamp ({mod_dt}) is later than FDR issue date ({issue_date})."
                                    ),
                                    severity="MEDIUM",
                                    details={"issue_date": str(issue_date), "modified_date": str(mod_dt)},
                                )
                            )
        except Exception:
            # If pikepdf fails to parse metadata (e.g. malformed trailer), flag corruption
            indicators.append(
                TamperIndicatorItem(
                    indicator_code="MALFORMED_METADATA_STRUCTURE",
                    description="PDF metadata/trailer contains syntax anomalies or encryption errors.",
                    severity="LOW",
                )
            )

        # 3. Font Inconsistencies on Numeric/Amount Text using PyMuPDF
        try:
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            fonts_seen = set()
            numeric_fonts = set()
            for page in doc:
                blocks = page.get_text("dict").get("blocks", [])
                for b in blocks:
                    for line in b.get("lines", []):
                        for span in line.get("spans", []):
                            font = span.get("font", "")
                            text = span.get("text", "")
                            fonts_seen.add(font)
                            if re.search(r"[0-9]{4,}", text) or "₹" in text or "Rs" in text:
                                numeric_fonts.add(font)

            # If numeric amounts use an unusual font distinct from regular document fonts
            if len(fonts_seen) > 3 and len(numeric_fonts - {"Helvetica", "Times-Roman", "Courier"}) > 1:
                indicators.append(
                    TamperIndicatorItem(
                        indicator_code="FONT_INCONSISTENCY",
                        description="Multiple distinct fonts detected across numeric/amount regions, indicating potential patch/overlay.",
                        severity="MEDIUM",
                        details={"fonts_seen": list(fonts_seen), "numeric_fonts": list(numeric_fonts)},
                    )
                )
        except Exception:
            pass

        return indicators

    @classmethod
    async def check_duplicates(
        cls,
        session: AsyncSession,
        fdr_id: int,
        file_hash: str,
        fdr_number: Optional[str],
        bank_name: Optional[str],
        institution_id: int,
    ) -> DuplicateCheckResult:
        """
        Duplicate Detection:
        1. Checks for identical SHA-256 file hash in other FDRs.
        2. Checks for normalized FDR number + bank cross-institution reuse.
        """
        result = DuplicateCheckResult()

        # 1. Exact SHA-256 duplicate
        if file_hash:
            hash_stmt = select(FDR).where(FDR.document_hash == file_hash, FDR.id != fdr_id)
            hash_res = await session.execute(hash_stmt)
            dup_fdr = hash_res.scalars().first()
            if dup_fdr:
                result.is_duplicate_hash = True
                result.duplicate_fdr_id = dup_fdr.id
                result.message = f"Identical file upload detected (SHA-256 matches FDR #{dup_fdr.id})."

        # 2. FDR Number & Bank cross-institution reuse
        if fdr_number and bank_name:
            norm_num = re.sub(r"[^A-Za-z0-9]", "", fdr_number).upper()
            # Query all other FDRs
            stmt = select(FDR).where(FDR.id != fdr_id, FDR.institution_id != institution_id)
            res = await session.execute(stmt)
            other_fdrs = res.scalars().all()
            for other in other_fdrs:
                if other.fdr_number and other.bank_name:
                    other_norm = re.sub(r"[^A-Za-z0-9]", "", other.fdr_number).upper()
                    if norm_num == other_norm and other.bank_name.lower() in bank_name.lower():
                        result.is_cross_institution_reuse = True
                        result.reused_fdr_id = other.id
                        result.reused_institution_id = other.institution_id
                        msg = f"Cross-institution instrument reuse: FDR {fdr_number} ({bank_name}) was already deposited by Institution #{other.institution_id}."
                        result.message = f"{result.message} | {msg}" if result.message else msg
                        break

        return result

    @classmethod
    def compare_discrepancies(
        cls,
        fdr: FDR,
        extracted_fields: Dict[str, ExtractedFieldItem],
        tamper_indicators: List[TamperIndicatorItem],
        duplicate_check: DuplicateCheckResult,
    ) -> DiscrepancyReportResponse:
        """
        Pass 2: Side-by-side discrepancy validation between submitted form data
        and OCR-extracted document values.
        """
        fields: Dict[str, DiscrepancyFieldComparison] = {}
        discrepancy_count = 0
        critical_count = 0

        # Field 1: Principal Amount
        ext_amt = extracted_fields.get("principal_amount")
        sub_amt_str = str(fdr.principal_amount) if fdr.principal_amount is not None else None
        ext_amt_val = ext_amt.extracted_value if ext_amt else None
        amt_mismatch = False
        if sub_amt_str and ext_amt_val:
            parsed_sub = cls.parse_amount(sub_amt_str)
            parsed_ext = cls.parse_amount(ext_amt_val)
            if parsed_sub != parsed_ext:
                amt_mismatch = True

        if amt_mismatch:
            discrepancy_count += 1
            critical_count += 1
            fields["principal_amount"] = DiscrepancyFieldComparison(
                field_name="principal_amount",
                submitted_value=sub_amt_str,
                extracted_value=ext_amt_val,
                is_mismatch=True,
                severity="CRITICAL",
                confidence_score=ext_amt.confidence_score if ext_amt else 0.0,
                provenance_tier="OCR_EXTRACTED",
                badge_color="red",
                highlight_snippet=ext_amt.source_snippet if ext_amt else None,
            )
        else:
            fields["principal_amount"] = DiscrepancyFieldComparison(
                field_name="principal_amount",
                submitted_value=sub_amt_str,
                extracted_value=ext_amt_val,
                is_mismatch=False,
                severity="MATCH",
                confidence_score=ext_amt.confidence_score if ext_amt else 1.0,
                provenance_tier="OCR_EXTRACTED" if ext_amt_val else "INSTITUTION_ENTERED",
                badge_color="green" if ext_amt_val else "grey",
                highlight_snippet=ext_amt.source_snippet if ext_amt else None,
            )

        # Field 2: FDR Number
        ext_num = extracted_fields.get("fdr_number")
        sub_num = fdr.fdr_number
        ext_num_val = ext_num.extracted_value if ext_num else None
        num_mismatch = False
        if sub_num and ext_num_val:
            norm_sub = re.sub(r"[^A-Za-z0-9]", "", sub_num).upper()
            norm_ext = re.sub(r"[^A-Za-z0-9]", "", ext_num_val).upper()
            if norm_sub != norm_ext:
                num_mismatch = True

        if num_mismatch:
            discrepancy_count += 1
            critical_count += 1
            fields["fdr_number"] = DiscrepancyFieldComparison(
                field_name="fdr_number",
                submitted_value=sub_num,
                extracted_value=ext_num_val,
                is_mismatch=True,
                severity="CRITICAL",
                confidence_score=ext_num.confidence_score if ext_num else 0.0,
                provenance_tier="OCR_EXTRACTED",
                badge_color="red",
                highlight_snippet=ext_num.source_snippet if ext_num else None,
            )
        else:
            fields["fdr_number"] = DiscrepancyFieldComparison(
                field_name="fdr_number",
                submitted_value=sub_num,
                extracted_value=ext_num_val,
                is_mismatch=False,
                severity="MATCH",
                confidence_score=ext_num.confidence_score if ext_num else 1.0,
                provenance_tier="OCR_EXTRACTED" if ext_num_val else "INSTITUTION_ENTERED",
                badge_color="green" if ext_num_val else "grey",
                highlight_snippet=ext_num.source_snippet if ext_num else None,
            )

        # Field 3: Bank Name
        ext_bank = extracted_fields.get("bank_name")
        sub_bank = fdr.bank_name
        ext_bank_val = ext_bank.extracted_value if ext_bank else None
        bank_mismatch = False
        if sub_bank and ext_bank_val:
            norm_sub_b = re.sub(r"[^A-Za-z]", "", sub_bank).lower()
            norm_ext_b = re.sub(r"[^A-Za-z]", "", ext_bank_val).lower()
            if norm_sub_b not in norm_ext_b and norm_ext_b not in norm_sub_b:
                bank_mismatch = True

        if bank_mismatch:
            discrepancy_count += 1
            fields["bank_name"] = DiscrepancyFieldComparison(
                field_name="bank_name",
                submitted_value=sub_bank,
                extracted_value=ext_bank_val,
                is_mismatch=True,
                severity="WARNING",
                confidence_score=ext_bank.confidence_score if ext_bank else 0.0,
                provenance_tier="OCR_EXTRACTED",
                badge_color="red",
                highlight_snippet=ext_bank.source_snippet if ext_bank else None,
            )
        else:
            fields["bank_name"] = DiscrepancyFieldComparison(
                field_name="bank_name",
                submitted_value=sub_bank,
                extracted_value=ext_bank_val,
                is_mismatch=False,
                severity="MATCH",
                confidence_score=ext_bank.confidence_score if ext_bank else 1.0,
                provenance_tier="OCR_EXTRACTED" if ext_bank_val else "INSTITUTION_ENTERED",
                badge_color="green" if ext_bank_val else "grey",
                highlight_snippet=ext_bank.source_snippet if ext_bank else None,
            )

        # Field 4: IFSC Code
        ext_ifsc = extracted_fields.get("ifsc_code")
        sub_ifsc = fdr.ifsc_code
        ext_ifsc_val = ext_ifsc.extracted_value if ext_ifsc else None
        ifsc_mismatch = False
        if sub_ifsc and ext_ifsc_val:
            if sub_ifsc.strip().upper() != ext_ifsc_val.strip().upper():
                ifsc_mismatch = True

        if ifsc_mismatch:
            discrepancy_count += 1
            fields["ifsc_code"] = DiscrepancyFieldComparison(
                field_name="ifsc_code",
                submitted_value=sub_ifsc,
                extracted_value=ext_ifsc_val,
                is_mismatch=True,
                severity="WARNING",
                confidence_score=ext_ifsc.confidence_score if ext_ifsc else 0.0,
                provenance_tier="OCR_EXTRACTED",
                badge_color="red",
                highlight_snippet=ext_ifsc.source_snippet if ext_ifsc else None,
            )
        else:
            fields["ifsc_code"] = DiscrepancyFieldComparison(
                field_name="ifsc_code",
                submitted_value=sub_ifsc,
                extracted_value=ext_ifsc_val,
                is_mismatch=False,
                severity="MATCH",
                confidence_score=ext_ifsc.confidence_score if ext_ifsc else 1.0,
                provenance_tier="OCR_EXTRACTED" if ext_ifsc_val else "INSTITUTION_ENTERED",
                badge_color="green" if ext_ifsc_val else "grey",
                highlight_snippet=ext_ifsc.source_snippet if ext_ifsc else None,
            )

        # Field 5: Maturity Date
        ext_mat = extracted_fields.get("maturity_date")
        sub_mat = str(fdr.maturity_date) if fdr.maturity_date else None
        ext_mat_val = ext_mat.extracted_value if ext_mat else None
        mat_mismatch = False
        if sub_mat and ext_mat_val:
            parsed_sub_m = cls.parse_date(sub_mat)
            parsed_ext_m = cls.parse_date(ext_mat_val)
            if parsed_sub_m and parsed_ext_m and parsed_sub_m != parsed_ext_m:
                mat_mismatch = True

        if mat_mismatch:
            discrepancy_count += 1
            critical_count += 1
            fields["maturity_date"] = DiscrepancyFieldComparison(
                field_name="maturity_date",
                submitted_value=sub_mat,
                extracted_value=ext_mat_val,
                is_mismatch=True,
                severity="CRITICAL",
                confidence_score=ext_mat.confidence_score if ext_mat else 0.0,
                provenance_tier="OCR_EXTRACTED",
                badge_color="red",
                highlight_snippet=ext_mat.source_snippet if ext_mat else None,
            )
        else:
            fields["maturity_date"] = DiscrepancyFieldComparison(
                field_name="maturity_date",
                submitted_value=sub_mat,
                extracted_value=ext_mat_val,
                is_mismatch=False,
                severity="MATCH",
                confidence_score=ext_mat.confidence_score if ext_mat else 1.0,
                provenance_tier="OCR_EXTRACTED" if ext_mat_val else "INSTITUTION_ENTERED",
                badge_color="green" if ext_mat_val else "grey",
                highlight_snippet=ext_mat.source_snippet if ext_mat else None,
            )

        # Field 6: Lien Holder
        ext_lien = extracted_fields.get("lien_holder")
        sub_lien = fdr.lien_holder
        ext_lien_val = ext_lien.extracted_value if ext_lien else None
        lien_mismatch = False
        if sub_lien and ext_lien_val:
            if "AICTE" in sub_lien.upper() and "AICTE" not in ext_lien_val.upper() and "ALL INDIA" not in ext_lien_val.upper():
                lien_mismatch = True

        if lien_mismatch:
            discrepancy_count += 1
            critical_count += 1
            fields["lien_holder"] = DiscrepancyFieldComparison(
                field_name="lien_holder",
                submitted_value=sub_lien,
                extracted_value=ext_lien_val,
                is_mismatch=True,
                severity="CRITICAL",
                confidence_score=ext_lien.confidence_score if ext_lien else 0.0,
                provenance_tier="OCR_EXTRACTED",
                badge_color="red",
                highlight_snippet=ext_lien.source_snippet if ext_lien else None,
            )
        else:
            fields["lien_holder"] = DiscrepancyFieldComparison(
                field_name="lien_holder",
                submitted_value=sub_lien,
                extracted_value=ext_lien_val,
                is_mismatch=False,
                severity="MATCH",
                confidence_score=ext_lien.confidence_score if ext_lien else 1.0,
                provenance_tier="OCR_EXTRACTED" if ext_lien_val else "INSTITUTION_ENTERED",
                badge_color="green" if ext_lien_val else "grey",
                highlight_snippet=ext_lien.source_snippet if ext_lien else None,
            )

        has_discrepancies = discrepancy_count > 0 or len(tamper_indicators) > 0 or duplicate_check.is_duplicate_hash or duplicate_check.is_cross_institution_reuse

        if critical_count > 0 or duplicate_check.is_cross_institution_reuse:
            action = "Scrutiny Officer Review Required: Critical discrepancy detected between document and declaration."
        elif tamper_indicators:
            action = "Scrutiny Officer Review Required: Forensic tamper indicators present on uploaded PDF."
        elif discrepancy_count > 0:
            action = "Scrutiny Officer Review Required: Non-critical mismatch flagged for verification."
        else:
            action = "All fields match PDF text layer. Eligible to advance to bank verification."

        return DiscrepancyReportResponse(
            fdr_id=fdr.id,
            has_discrepancies=has_discrepancies,
            discrepancy_count=discrepancy_count,
            critical_count=critical_count,
            fields=fields,
            tamper_indicators=tamper_indicators,
            duplicate_warning=duplicate_check.message,
            recommended_action=action,
        )

    @classmethod
    async def sync_provenance_records(
        cls,
        session: AsyncSession,
        fdr_id: int,
        extracted_fields: Dict[str, ExtractedFieldItem],
    ) -> List[Provenance]:
        """
        Synchronizes extracted fields into field_provenance database records.
        Updates source_type to OCR_EXTRACTED with confidence scores.
        """
        stmt = select(Provenance).where(Provenance.fdr_id == fdr_id)
        res = await session.execute(stmt)
        existing_records = {p.field_name: p for p in res.scalars().all()}

        synced: List[Provenance] = []
        for field_name, item in extracted_fields.items():
            if not item.extracted_value:
                continue

            if field_name in existing_records:
                prov = existing_records[field_name]
                # If not already verified by officer or bank, update with OCR extraction
                if prov.source_type not in (ProvenanceSourceType.OFFICER_VERIFIED, ProvenanceSourceType.BANK_CONFIRMED):
                    prov.extracted_value = item.extracted_value
                    prov.source_type = ProvenanceSourceType.OCR_EXTRACTED
                    prov.confidence_score = item.confidence_score
                    prov.updated_at = datetime.now(timezone.utc)
                    session.add(prov)
                    synced.append(prov)
            else:
                new_prov = Provenance(
                    fdr_id=fdr_id,
                    field_name=field_name,
                    source_type=ProvenanceSourceType.OCR_EXTRACTED,
                    confidence_score=item.confidence_score,
                    extracted_value=item.extracted_value,
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(new_prov)
                synced.append(new_prov)

        await session.flush()
        return synced

    @classmethod
    async def process_fdr_document(
        cls,
        session: AsyncSession,
        fdr: FDR,
        pdf_bytes: bytes,
    ) -> Tuple[OCRExtractionResponse, DiscrepancyReportResponse]:
        """
        Executes full Pass 1 Extraction + Tamper Analysis + Duplicate Detection + Pass 2 Side-by-Side Comparison.
        Updates FDR row with forensic indicators and syncs provenance records.
        """
        # Pass 1: Extraction
        extracted_fields, text_len, page_count = cls.extract_from_pdf(pdf_bytes)

        # Check human review requirement
        needs_human_review = any(item.needs_human_review for item in extracted_fields.values())

        # Forensics: Tamper Indicators
        tamper_indicators = cls.detect_tamper_indicators(pdf_bytes, fdr.issue_date)

        # Forensics: Duplicate Detection
        dup_check = await cls.check_duplicates(
            session=session,
            fdr_id=fdr.id,
            file_hash=fdr.document_hash or "",
            fdr_number=fdr.fdr_number,
            bank_name=fdr.bank_name,
            institution_id=fdr.institution_id,
        )

        # Sync provenance in DB
        await cls.sync_provenance_records(session, fdr.id, extracted_fields)

        # Pass 2: Side-by-side discrepancy validation
        discrepancy_report = cls.compare_discrepancies(fdr, extracted_fields, tamper_indicators, dup_check)

        # Update FDR attributes
        fdr.ocr_status = "NEEDS_HUMAN_REVIEW" if (needs_human_review or discrepancy_report.has_discrepancies) else "PROCESSED"
        if tamper_indicators:
            fdr.tamper_indicators = json.dumps([t.model_dump() for t in tamper_indicators])
        else:
            fdr.tamper_indicators = None
        session.add(fdr)
        await session.flush()

        extraction_response = OCRExtractionResponse(
            fdr_id=fdr.id,
            extracted_fields=extracted_fields,
            tamper_indicators=tamper_indicators,
            duplicate_check=dup_check,
            needs_human_review=needs_human_review,
            text_length=text_len,
            page_count=page_count,
            ocr_status=fdr.ocr_status,
        )

        return extraction_response, discrepancy_report

    @classmethod
    async def verify_field(
        cls,
        session: AsyncSession,
        fdr: FDR,
        field_name: str,
        accepted_value: str,
        officer_id: str,
        remarks: Optional[str] = None,
    ) -> Tuple[Provenance, AuditLog]:
        """
        Officer field verification (Tier 3 in Provenance):
        Upgrades field provenance to OFFICER_VERIFIED and optionally updates FDR attribute.
        Logs immutable chained audit record.
        """
        stmt = select(Provenance).where(Provenance.fdr_id == fdr.id, Provenance.field_name == field_name)
        res = await session.execute(stmt)
        prov = res.scalar_one_or_none()

        if prov:
            prov.extracted_value = accepted_value
            prov.source_type = ProvenanceSourceType.OFFICER_VERIFIED
            prov.confidence_score = 1.0
            prov.updated_at = datetime.now(timezone.utc)
            session.add(prov)
        else:
            prov = Provenance(
                fdr_id=fdr.id,
                field_name=field_name,
                source_type=ProvenanceSourceType.OFFICER_VERIFIED,
                confidence_score=1.0,
                extracted_value=accepted_value,
                updated_at=datetime.now(timezone.utc),
            )
            session.add(prov)

        # If field corresponds to FDR column, update it
        if hasattr(fdr, field_name):
            if field_name == "principal_amount":
                setattr(fdr, field_name, cls.parse_amount(accepted_value))
            elif field_name in ("issue_date", "maturity_date"):
                setattr(fdr, field_name, cls.parse_date(accepted_value))
            else:
                setattr(fdr, field_name, accepted_value)
            session.add(fdr)

        await session.flush()

        # Immutable Chained Audit Log
        audit_entry = await AuditService.record_event(
            session=session,
            action="FDR_FIELD_VERIFIED",
            payload={
                "fdr_id": fdr.id,
                "field_name": field_name,
                "verified_value": accepted_value,
                "officer_id": officer_id,
                "remarks": remarks,
            },
            user_id=officer_id,
            details=f"Officer {officer_id} verified field '{field_name}' as '{accepted_value}'",
        )

        return prov, audit_entry
