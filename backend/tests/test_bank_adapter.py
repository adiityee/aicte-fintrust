from decimal import Decimal
import pytest

from app.services.bank_adapter import (
    BankConfirmationPayload,
    SFMSAdapter,
    SignedLinkAdapter,
    SimulatedBankAdapter,
)


@pytest.mark.asyncio
async def test_simulated_bank_adapter():
    adapter = SimulatedBankAdapter()

    # 1. Generate link
    link = await adapter.generate_signed_link(fdr_id=101, branch_email="nodal@sbi.co.in")
    assert "token=simulated_token_101_" in link

    # 2. Verify link token
    token = link.split("token=")[1]
    verified_id = await adapter.verify_signed_link(token)
    assert verified_id == 101

    # 3. Confirm lien
    payload = BankConfirmationPayload(
        lien_affirmed=True,
        no_encashment_without_aicte=True,
        auto_renewal_status=True,
        balance_confirmed=Decimal("2500000.00"),
    )
    result = await adapter.confirm_lien(fdr_id=101, payload=payload, officer_id="OFFICER_PATIL")
    assert result.fdr_id == 101
    assert result.is_confirmed is True
    assert result.adapter_name == "SimulatedBankAdapter"
    assert result.confirmation_ref.startswith("SIM-BANK-")
    assert result.details["simulated"] is True


@pytest.mark.asyncio
async def test_signed_link_adapter_hmac_and_tamper_detection():
    adapter = SignedLinkAdapter(secret_key="test-secret-key")

    # 1. Valid Link Generation & Verification
    link = await adapter.generate_signed_link(fdr_id=202, branch_email="manager@pnb.co.in", valid_hours=24)
    token = link.split("/bank/verify/")[1]

    verified_id = await adapter.verify_signed_link(token)
    assert verified_id == 202

    # 2. Tampered token verification fails
    tampered_token = token[:-4] + "ffff"
    assert await adapter.verify_signed_link(tampered_token) is None

    # 3. Expired token verification fails
    # Manually craft token with timestamp in the past
    past_ts = 1000000000
    expired_token = adapter._generate_hmac_token(fdr_id=202, expires_at_ts=past_ts)
    assert await adapter.verify_signed_link(expired_token) is None

    # 4. Confirm lien
    payload = BankConfirmationPayload(
        lien_affirmed=True,
        no_encashment_without_aicte=True,
        auto_renewal_status=False,
        balance_confirmed=Decimal("5000000.00"),
    )
    result = await adapter.confirm_lien(fdr_id=202, payload=payload, officer_id="BRANCH_MGR_01")
    assert result.is_confirmed is True
    assert result.adapter_name == "SignedLinkAdapter"
    assert result.confirmation_ref.startswith("NODAL-AFFIRM-")
    assert result.details["hmac_verified"] is True


@pytest.mark.asyncio
async def test_sfms_adapter_stub():
    adapter = SFMSAdapter()

    payload = BankConfirmationPayload(
        lien_affirmed=True,
        no_encashment_without_aicte=True,
        auto_renewal_status=True,
        balance_confirmed=Decimal("10000000.00"),
    )
    result = await adapter.confirm_lien(fdr_id=303, payload=payload, officer_id="SFMS_GATE")
    assert result.is_confirmed is True
    assert result.adapter_name == "SFMSAdapter"
    assert result.confirmation_ref.startswith("SFMS-MT760-")
    assert result.details["swift_message_type"] == "MT760"

    with pytest.raises(NotImplementedError):
        await adapter.generate_signed_link(303, "sfms@rbi.org.in")
