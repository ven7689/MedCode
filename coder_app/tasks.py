from celery import shared_task
from .models import MedicalDocument
from .services import call_vlm


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def process_document(self, doc_id: int):
    """
    Background task: call the VLM and store results on the MedicalDocument.
    """
    try:
        doc = MedicalDocument.objects.get(pk=doc_id)
    except MedicalDocument.DoesNotExist:
        return  # Nothing to do

    doc.status = MedicalDocument.STATUS_PROCESSING
    doc.save(update_fields=["status"])

    try:
        results = call_vlm(doc.file.path)
        doc.vlm_results = results
        doc.status = MedicalDocument.STATUS_COMPLETED
        doc.error_message = None
        doc.save(update_fields=["vlm_results", "status", "error_message"])

    except Exception as exc:
        doc.status = MedicalDocument.STATUS_FAILED
        doc.error_message = str(exc)
        doc.save(update_fields=["status", "error_message"])
        raise self.retry(exc=exc)
