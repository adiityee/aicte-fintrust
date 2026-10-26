from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models.provenance import ProvenanceSourceType


class ProvenanceResponse(BaseModel):
    id: int
    fdr_id: int
    field_name: str
    source_type: ProvenanceSourceType
    confidence_score: Optional[float] = None
    extracted_value: Optional[str] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
