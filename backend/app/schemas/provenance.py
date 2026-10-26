from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

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


class FDRProvenanceResponse(BaseModel):
    """Provenance response for split-screen comparison UI."""
    fdr_id: int
    provenance_records: List[ProvenanceResponse]
    confidence_flags: Dict[str, Any] = Field(default_factory=dict)
    needs_human_review: bool = False

    model_config = ConfigDict(from_attributes=True)
