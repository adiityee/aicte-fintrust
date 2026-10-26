"""
AICTE FinTrust OCR & Forensics Service Alias Module
Provides OCRForensicService interface for PDF text extraction and forensics.
"""

from app.services.ocr_service import OCRService

# Export OCRForensicService alias
OCRForensicService = OCRService

__all__ = ["OCRForensicService", "OCRService"]
