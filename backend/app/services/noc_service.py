from datetime import datetime, timezone
import hashlib
import io
import json
import os
from typing import Any, Dict, Optional, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import qrcode
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fdr import FDR
from app.services.storage_service import storage_service

# Deterministic mock DSC key seed for AICTE Competent Authority
DSC_SEED = hashlib.sha256(b"AICTE_COMPETENT_AUTHORITY_DSC_MASTER_SECRET_2026").digest()
AUTHORITY_PRIVATE_KEY = ed25519.Ed25519PrivateKey.from_private_bytes(DSC_SEED)
AUTHORITY_PUBLIC_KEY = AUTHORITY_PRIVATE_KEY.public_key()
AUTHORITY_PUBLIC_BYTES = AUTHORITY_PUBLIC_KEY.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
PUBLIC_KEY_HEX = AUTHORITY_PUBLIC_BYTES.hex()

NOC_BUCKET = "noc-certificates"


def get_public_key_hex() -> str:
    """Returns the hex representation of the AICTE DSC public key."""
    return PUBLIC_KEY_HEX


def generate_release_payload(
    fdr: FDR,
    release_date_str: str,
    officer_id: str,
    base_url: str = "http://localhost:3000",
) -> Dict[str, Any]:
    """
    Constructs the canonical release payload for digital signing as per ARCHITECTURE_PLAN.md:
    FDR ID, Institution ID, Bank Name, Principal Amount, Release Authorization Date,
    Officer Signature Hash, and Public Verification URL.
    """
    officer_sig_hash = hashlib.sha256(officer_id.encode("utf-8")).hexdigest()
    return {
        "fdr_id": int(fdr.id),
        "institution_id": int(fdr.institution_id),
        "bank_name": str(fdr.bank_name or ""),
        "principal_amount": str(fdr.principal_amount or "0.00"),
        "release_authorization_date": release_date_str,
        "officer_signature_hash": officer_sig_hash,
        "public_verification_url": f"{base_url}/verify/{fdr.id}",
    }


def canonical_payload_bytes(payload: Dict[str, Any]) -> bytes:
    """Returns deterministic sorted JSON bytes for cryptographic signing."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_payload(payload: Dict[str, Any]) -> str:
    """Signs the canonical release payload with the Ed25519 DSC private key."""
    data_to_sign = canonical_payload_bytes(payload)
    signature = AUTHORITY_PRIVATE_KEY.sign(data_to_sign)
    return signature.hex()


def verify_signature(payload: Dict[str, Any], signature_hex: str) -> bool:
    """Verifies that the Ed25519 signature corresponds to the canonical release payload."""
    try:
        data_to_verify = canonical_payload_bytes(payload)
        sig_bytes = bytes.fromhex(signature_hex)
        AUTHORITY_PUBLIC_KEY.verify(sig_bytes, data_to_verify)
        return True
    except Exception:
        return False


def generate_qr_image_bytes(url: str) -> io.BytesIO:
    """Generates a PNG image of the QR code pointing to the public verification URL."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def generate_noc_pdf(
    fdr: FDR,
    payload: Dict[str, Any],
    signature_hex: str,
    officer_id: str,
) -> bytes:
    """
    Generates a formal, government-grade AICTE Discharge / NOC PDF
    with embedded QR code and Ed25519 digital signature block.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "AICTETitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        alignment=1,  # Center
        textColor=colors.HexColor("#1e3a8a"),
    )
    sub_title_style = ParagraphStyle(
        "AICTESubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=1,
        textColor=colors.HexColor("#475569"),
    )
    doc_type_style = ParagraphStyle(
        "DocType",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        alignment=1,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=8,
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "NOCBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1e293b"),
    )
    bold_style = ParagraphStyle(
        "NOCBold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    legal_style = ParagraphStyle(
        "LegalNotice",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )

    story = []

    # 1. Header Banner
    story.append(Paragraph("ALL INDIA COUNCIL FOR TECHNICAL EDUCATION", title_style))
    story.append(Paragraph("(A Statutory Body of the Government of India)", sub_title_style))
    story.append(Paragraph("Nelson Mandela Marg, Vasant Kunj, New Delhi - 110070", sub_title_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#1e3a8a"), spaceAfter=10))

    # 2. Document Title & Reference
    noc_ref = f"AICTE/NOC/DISCHARGE/{datetime.now().year}/{fdr.id:05d}"
    story.append(Paragraph("DISCHARGE ORDER & NO OBJECTION CERTIFICATE (NOC)", doc_type_style))

    meta_table = Table(
        [
            [
                Paragraph(f"<b>NOC Order Reference:</b> {noc_ref}", body_style),
                Paragraph(f"<b>Authorization Date:</b> {payload['release_authorization_date']}", body_style),
            ],
            [
                Paragraph(f"<b>Statutory Reference:</b> Handbook Clause 6.46", body_style),
                Paragraph("<b>Lien Status:</b> <font color='#16a34a'><b>DISCHARGED & RELEASED</b></font>", body_style),
            ],
        ],
        colWidths=[270, 270],
    )
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # 3. Instrument & Institution Details
    inst_name = fdr.institution.name if getattr(fdr, "institution", None) else f"Institution ID {fdr.institution_id}"
    aicte_id = fdr.institution.aicte_permanent_id if getattr(fdr, "institution", None) else f"AICTE-{fdr.institution_id}"

    details_data = [
        [Paragraph("<b>Depositor Institution:</b>", body_style), Paragraph(f"{inst_name} ({aicte_id})", body_style)],
        [Paragraph("<b>Fixed Deposit Receipt No:</b>", body_style), Paragraph(str(fdr.fdr_number), bold_style)],
        [Paragraph("<b>Depository Bank & Branch:</b>", body_style), Paragraph(f"{fdr.bank_name} (IFSC: {fdr.ifsc_code})", body_style)],
        [Paragraph("<b>Principal Deposit Amount:</b>", body_style), Paragraph(f"INR {fdr.principal_amount:,.2f}", bold_style)],
        [Paragraph("<b>Original Deposit / Maturity:</b>", body_style), Paragraph(f"{fdr.issue_date} to {fdr.maturity_date}", body_style)],
        [Paragraph("<b>Mandatory Clearances:</b>", body_style), Paragraph("<b>100% Cleared</b> (PGRC, Vigilance, Approval Bureau, Legal, Finance)", body_style)],
    ]
    details_table = Table(details_data, colWidths=[180, 360])
    details_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    story.append(details_table)
    story.append(Spacer(1, 12))

    # 4. Discharge Declaration Text
    declaration_text = (
        "<b>CERTIFICATE OF DISCHARGE:</b> In accordance with the powers vested under the All India Council for Technical "
        "Education Act and Clause 6.46 of the AICTE Approval Process Handbook (2024–2027), it is hereby certified that the "
        "institution has satisfactorily fulfilled all prescribed conditions. All five parallel regulatory clearance cells "
        "(PGRC, Vigilance, Approval Bureau, Legal, and Finance) have recorded unconditional approvals. "
        "The Council has <b>NO OBJECTION</b> to the complete discharge of AICTE lien and authorizes the designated bank to "
        "release and credit the principal deposit and accrued interest to the registered account of the institution."
    )
    story.append(Paragraph(declaration_text, body_style))
    story.append(Spacer(1, 12))

    # 5. Verification QR Code and Ed25519 Digital Signature Block
    qr_buffer = generate_qr_image_bytes(payload["public_verification_url"])
    qr_image = Image(qr_buffer, width=75, height=75)

    sig_short = f"{signature_hex[:24]}...{signature_hex[-24:]}"
    pub_short = f"{PUBLIC_KEY_HEX[:20]}...{PUBLIC_KEY_HEX[-20:]}"

    sig_paragraph = Paragraph(
        f"<b>DIGITALLY SIGNED & SEALED</b><br/>"
        f"<b>Authorized Signatory:</b> {officer_id} (Competent Authority, AICTE)<br/>"
        f"<b>DSC Algorithm:</b> Ed25519 Curve25519 (RFC 8032)<br/>"
        f"<b>DSC Public Key:</b> <code>{pub_short}</code><br/>"
        f"<b>Cryptographic Signature:</b> <code>{sig_short}</code><br/>"
        f"<b>Live Public Verification:</b> <font color='#2563eb'><u>{payload['public_verification_url']}</u></font>",
        legal_style,
    )

    qr_sig_table = Table([[qr_image, sig_paragraph]], colWidths=[90, 450])
    qr_sig_table.setStyle(
        TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#94a3b8")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(qr_sig_table)
    story.append(Spacer(1, 8))
    story.append(Paragraph("<i>This document is cryptographically signed. Authenticity can be verified live by scanning the QR code above.</i>", sub_title_style))

    doc.build(story)
    return buffer.getvalue()


class NOCService:
    """
    NOC & Cryptographic Digital Discharge Service
    Manages Ed25519 DSC signing, ReportLab PDF order generation with QR verification,
    and MinIO secure certificate archiving.
    """

    @staticmethod
    async def generate_and_sign_noc(
        session: AsyncSession,
        fdr: FDR,
        officer_id: str = "COMPETENT_AUTHORITY",
        base_url: str = "http://localhost:3000",
    ) -> Dict[str, Any]:
        """
        1. Builds canonical release payload.
        2. Signs payload with Ed25519 DSC private key.
        3. Renders formal AICTE NOC PDF with embedded QR code.
        4. Uploads PDF into MinIO 'noc-certificates' bucket.
        5. Updates FDR record with NOC path and signature.
        """
        release_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        payload = generate_release_payload(
            fdr=fdr,
            release_date_str=release_date,
            officer_id=officer_id,
            base_url=base_url,
        )

        # 1. Sign canonical payload
        signature_hex = sign_payload(payload)

        # 2. Render formal NOC PDF with embedded QR
        pdf_bytes = generate_noc_pdf(
            fdr=fdr,
            payload=payload,
            signature_hex=signature_hex,
            officer_id=officer_id,
        )

        # 3. Upload to MinIO under 'noc-certificates'
        object_key = storage_service.upload_fdr_document(
            fdr_id=fdr.id,
            file_bytes=pdf_bytes,
            filename=f"NOC_AICTE_{fdr.id}_{fdr.fdr_number}.pdf",
            content_type="application/pdf",
            bucket_name=NOC_BUCKET,
        )

        # 4. Update FDR model
        fdr.noc_path = object_key
        fdr.noc_signature = signature_hex
        fdr.noc_payload = json.dumps(payload, sort_keys=True)
        fdr.authorizing_officer = officer_id
        fdr.noc_verified_at = datetime.now(timezone.utc)
        session.add(fdr)
        await session.flush()

        presigned_url = storage_service.generate_presigned_url(
            object_key=object_key,
            expires_in_seconds=300,
            bucket_name=NOC_BUCKET,
        )

        return {
            "fdr_id": fdr.id,
            "noc_path": object_key,
            "noc_signature": signature_hex,
            "public_key_hex": PUBLIC_KEY_HEX,
            "presigned_url": presigned_url,
            "public_verification_url": payload["public_verification_url"],
            "release_date": release_date,
            "payload": payload,
        }

    @staticmethod
    def verify_noc_signature(fdr: FDR, officer_id: Optional[str] = None) -> bool:
        """
        Cryptographically verifies the FDR's Ed25519 NOC signature against its release payload.
        """
        if not fdr.noc_signature:
            return False

        if fdr.noc_payload:
            try:
                payload = json.loads(fdr.noc_payload)
                return verify_signature(payload, fdr.noc_signature)
            except Exception:
                return False

        release_date_str = (
            fdr.noc_verified_at.strftime("%Y-%m-%d")
            if fdr.noc_verified_at
            else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        )
        auth_officer = officer_id or fdr.authorizing_officer or "COMPETENT_AUTHORITY"
        payload = generate_release_payload(
            fdr=fdr,
            release_date_str=release_date_str,
            officer_id=auth_officer,
        )

        return verify_signature(payload, fdr.noc_signature)
