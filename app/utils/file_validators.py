from django.core.exceptions import ValidationError

MAX_PDF_UPLOAD_SIZE_MB = 3
MAX_PDF_UPLOAD_SIZE_BYTES = MAX_PDF_UPLOAD_SIZE_MB * 1024 * 1024


def validate_pdf_upload(file_obj):
    """Ensure an uploaded file is a PDF no larger than MAX_PDF_UPLOAD_SIZE_MB."""
    if not file_obj:
        return

    name = getattr(file_obj, "name", "") or ""
    if not name.lower().endswith(".pdf"):
        raise ValidationError("Only PDF files are allowed.")

    content_type = getattr(file_obj, "content_type", None)
    if content_type and content_type != "application/pdf":
        raise ValidationError("Only PDF files are allowed.")

    size = getattr(file_obj, "size", None)
    if size and size > MAX_PDF_UPLOAD_SIZE_BYTES:
        raise ValidationError(
            f"File size must not exceed {MAX_PDF_UPLOAD_SIZE_MB} MB."
        )
