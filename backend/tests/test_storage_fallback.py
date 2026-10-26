import os
import shutil
import uuid
import pytest
from sqlalchemy import Column, Integer, Table, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, CompatibleJSON, CompatibleUUID, FALLBACK_SQLITE_URL, init_db
from app.services.storage_service import StorageService


# Test Table for CompatibleUUID and CompatibleJSON
class ModelWithUUIDAndJSON(Base):
    __tablename__ = "test_uuid_json_table"
    id = Column(Integer, primary_key=True, autoincrement=True)
    custom_id = Column(CompatibleUUID, nullable=False)
    metadata_json = Column(CompatibleJSON, nullable=False)


@pytest.mark.asyncio
async def test_sqlite_compatible_uuid_and_json():
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    test_session_maker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_uuid = uuid.uuid4()
    test_payload = {"deposit_type": "security", "lien": "AICTE", "tier": 1}

    async with test_session_maker() as session:
        row = ModelWithUUIDAndJSON(
            custom_id=test_uuid,
            metadata_json=test_payload,
        )
        session.add(row)
        await session.commit()

        # Query back
        stmt = select(ModelWithUUIDAndJSON).where(ModelWithUUIDAndJSON.id == 1)
        res = await session.execute(stmt)
        retrieved = res.scalar_one()

        assert retrieved.custom_id == test_uuid
        assert retrieved.metadata_json == test_payload
        assert retrieved.metadata_json["lien"] == "AICTE"

    await test_engine.dispose()


def test_storage_service_offline_fallback(tmp_path):
    local_storage_dir = str(tmp_path / "local_storage")

    # Instantiate StorageService pointing to non-existent MinIO port
    service = StorageService(
        endpoint="localhost:9999",  # Unreachable port
        local_dir=local_storage_dir,
        bucket_name="fdr-documents",
    )

    # 1. Bucket existence check
    service.ensure_bucket_exists("fdr-documents")
    assert os.path.exists(os.path.join(local_storage_dir, "fdr-documents"))

    # 2. Upload file
    sample_content = b"%PDF-1.4 Mock Offline FDR Document for Testing"
    object_key = service.upload_fdr_document(
        fdr_id=1234,
        file_bytes=sample_content,
        filename="sbi_offline_fdr.pdf",
        bucket_name="fdr-documents",
    )

    assert object_key.startswith("fdrs/1234/")
    assert object_key.endswith("sbi_offline_fdr.pdf")

    # Verify physical file exists on local disk
    local_file_path = os.path.join(local_storage_dir, "fdr-documents", *object_key.split("/"))
    assert os.path.exists(local_file_path)
    with open(local_file_path, "rb") as f:
        assert f.read() == sample_content

    # 3. Download file
    downloaded_bytes = service.download_fdr_document(object_key, bucket_name="fdr-documents")
    assert downloaded_bytes == sample_content

    # 4. Generate download URL
    url = service.generate_presigned_url(object_key, bucket_name="fdr-documents")
    assert url.startswith("http://localhost:8000/storage/fdr-documents/fdrs/1234/")
    assert "sbi_offline_fdr.pdf" in url
