from rest_framework.generics import GenericAPIView, RetrieveAPIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

from .models import MedicalDocument
from .serializers import DocumentSerializer
from .tasks import process_document


class UploadDocumentView(GenericAPIView):
    """
    POST /api/upload/
    Accepts a medical document image, saves it, and queues VLM processing.
    Returns 202 Accepted immediately — poll /api/documents/<id>/ for results.
    """
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = serializer.save()

        # Fire-and-forget: Celery worker picks this up
        process_document.delay(doc.id)

        return Response(
            self.get_serializer(doc).data,
            status=status.HTTP_202_ACCEPTED,
        )


class DocumentStatusView(RetrieveAPIView):
    """
    GET /api/documents/<id>/
    Returns current status and VLM results once processing is complete.
    """
    queryset = MedicalDocument.objects.all()
    serializer_class = DocumentSerializer
