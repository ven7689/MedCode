"""
Test suite for coder_app.

Run with:
    python manage.py test coder_app
"""
import io
import json
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import MedicalDocument
from .services import call_vlm
from .tasks import process_document


# ─── Helpers ────────────────────────────────────────────────────────────────

def _fake_image():
    """Return a minimal valid JPEG binary (1x1 white pixel)."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buf, format="JPEG")
    buf.seek(0)
    return buf.read()


def _uploaded_image(name="test.jpg"):
    return SimpleUploadedFile(name, _fake_image(), content_type="image/jpeg")


# ─── Model Tests ─────────────────────────────────────────────────────────────

class MedicalDocumentModelTest(TestCase):
    def test_status_constants(self):
        self.assertEqual(MedicalDocument.STATUS_PENDING, "pending")
        self.assertEqual(MedicalDocument.STATUS_PROCESSING, "processing")
        self.assertEqual(MedicalDocument.STATUS_COMPLETED, "completed")
        self.assertEqual(MedicalDocument.STATUS_FAILED, "failed")

    def test_default_status_is_pending(self):
        doc = MedicalDocument.objects.create(file=_uploaded_image())
        self.assertEqual(doc.status, MedicalDocument.STATUS_PENDING)

    def test_str_representation(self):
        doc = MedicalDocument.objects.create(file=_uploaded_image())
        self.assertIn(str(doc.id), str(doc))
        self.assertIn("pending", str(doc))

    def test_vlm_results_nullable(self):
        doc = MedicalDocument.objects.create(file=_uploaded_image())
        self.assertIsNone(doc.vlm_results)
        self.assertIsNone(doc.error_message)


# ─── View Tests ──────────────────────────────────────────────────────────────

class UploadDocumentViewTest(TestCase):
    @patch("coder_app.views.process_document")
    def test_upload_returns_202(self, mock_task):
        """POST /api/upload/ should return 202 Accepted."""
        mock_task.delay = MagicMock()
        response = self.client.post(
            "/api/upload/",
            {"file": _uploaded_image()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 202)

    @patch("coder_app.views.process_document")
    def test_upload_creates_document(self, mock_task):
        """POST /api/upload/ should create a MedicalDocument in DB."""
        mock_task.delay = MagicMock()
        self.client.post("/api/upload/", {"file": _uploaded_image()})
        self.assertEqual(MedicalDocument.objects.count(), 1)

    @patch("coder_app.views.process_document")
    def test_upload_queues_celery_task(self, mock_task):
        """POST /api/upload/ should call process_document.delay(doc.id)."""
        mock_task.delay = MagicMock()
        self.client.post("/api/upload/", {"file": _uploaded_image()})
        mock_task.delay.assert_called_once()

    @patch("coder_app.views.process_document")
    def test_upload_no_file_returns_400(self, mock_task):
        """POST /api/upload/ with no file should return 400."""
        mock_task.delay = MagicMock()
        response = self.client.post("/api/upload/", {})
        self.assertEqual(response.status_code, 400)


class DocumentStatusViewTest(TestCase):
    def _create_completed_doc(self):
        doc = MedicalDocument.objects.create(file=_uploaded_image())
        doc.status = MedicalDocument.STATUS_COMPLETED
        doc.vlm_results = [{"code": "J18.9", "description": "Pneumonia"}]
        doc.save()
        return doc

    def test_get_existing_document_returns_200(self):
        doc = self._create_completed_doc()
        response = self.client.get(f"/api/documents/{doc.id}/")
        self.assertEqual(response.status_code, 200)

    def test_get_nonexistent_document_returns_404(self):
        response = self.client.get("/api/documents/9999/")
        self.assertEqual(response.status_code, 404)

    def test_response_contains_status_and_results(self):
        doc = self._create_completed_doc()
        response = self.client.get(f"/api/documents/{doc.id}/")
        data = response.json()
        self.assertEqual(data["status"], "completed")
        self.assertEqual(data["vlm_results"][0]["code"], "J18.9")


# ─── Service Tests ────────────────────────────────────────────────────────────

class CallVLMServiceTest(TestCase):
    def _mock_response(self, content, status_code=200):
        mock_resp = MagicMock()
        mock_resp.ok = status_code == 200
        mock_resp.status_code = status_code
        mock_resp.text = content
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": content}}]
        }
        return mock_resp

    @patch("coder_app.services.requests.post")
    @patch("coder_app.services.preprocess_image")
    def test_valid_json_response(self, mock_preprocess, mock_post):
        """call_vlm should return parsed list on valid JSON response."""
        mock_preprocess.return_value = (b"fakejpeg", "image/jpeg")
        expected = [{"code": "J18.9", "description": "Pneumonia"}]
        mock_post.return_value = self._mock_response(json.dumps(expected))

        result = call_vlm("/fake/path.jpg")
        self.assertEqual(result, expected)

    @patch("coder_app.services.requests.post")
    @patch("coder_app.services.preprocess_image")
    def test_strips_markdown_fences(self, mock_preprocess, mock_post):
        """call_vlm should strip ```json ... ``` wrappers from response."""
        mock_preprocess.return_value = (b"fakejpeg", "image/jpeg")
        fenced = '```json\n[{"code": "Z00.0", "description": "Encounter for general exam"}]\n```'
        mock_post.return_value = self._mock_response(fenced)

        result = call_vlm("/fake/path.jpg")
        self.assertEqual(result[0]["code"], "Z00.0")

    @patch("coder_app.services.requests.post")
    @patch("coder_app.services.preprocess_image")
    def test_invalid_json_raises_runtime_error(self, mock_preprocess, mock_post):
        """call_vlm should raise RuntimeError when model returns non-JSON."""
        mock_preprocess.return_value = (b"fakejpeg", "image/jpeg")
        mock_post.return_value = self._mock_response("Sorry, I cannot process this.")

        with self.assertRaises(RuntimeError) as ctx:
            call_vlm("/fake/path.jpg")
        self.assertIn("non-JSON", str(ctx.exception))

    @patch("coder_app.services.requests.post")
    @patch("coder_app.services.preprocess_image")
    def test_api_error_raises_runtime_error(self, mock_preprocess, mock_post):
        """call_vlm should raise RuntimeError on non-200 API response."""
        mock_preprocess.return_value = (b"fakejpeg", "image/jpeg")
        bad_resp = MagicMock()
        bad_resp.ok = False
        bad_resp.status_code = 429
        bad_resp.text = "Rate limit exceeded"
        mock_post.return_value = bad_resp

        with self.assertRaises(RuntimeError) as ctx:
            call_vlm("/fake/path.jpg")
        self.assertIn("429", str(ctx.exception))

    @patch("coder_app.services.requests.post")
    @patch("coder_app.services.preprocess_image")
    def test_non_list_response_raises_runtime_error(self, mock_preprocess, mock_post):
        """call_vlm should raise RuntimeError if JSON root is not a list."""
        mock_preprocess.return_value = (b"fakejpeg", "image/jpeg")
        mock_post.return_value = self._mock_response('{"code": "J18.9"}')

        with self.assertRaises(RuntimeError) as ctx:
            call_vlm("/fake/path.jpg")
        self.assertIn("Expected a JSON array", str(ctx.exception))


# ─── Task Tests ───────────────────────────────────────────────────────────────

class ProcessDocumentTaskTest(TestCase):
    def setUp(self):
        self.doc = MedicalDocument.objects.create(file=_uploaded_image())

    @patch("coder_app.tasks.call_vlm")
    def test_task_sets_status_completed_on_success(self, mock_vlm):
        """process_document should mark document COMPLETED with vlm_results."""
        icd_codes = [{"code": "J18.9", "description": "Pneumonia"}]
        mock_vlm.return_value = icd_codes

        process_document(self.doc.id)

        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, MedicalDocument.STATUS_COMPLETED)
        self.assertEqual(self.doc.vlm_results, icd_codes)
        self.assertIsNone(self.doc.error_message)

    @patch("coder_app.tasks.call_vlm")
    def test_task_sets_status_failed_on_exception(self, mock_vlm):
        """process_document should mark document FAILED and store error."""
        mock_vlm.side_effect = RuntimeError("VLM timeout")

        # Wrap in try/except because Celery retry raises Retry exception
        try:
            process_document(self.doc.id)
        except Exception:
            pass

        self.doc.refresh_from_db()
        self.assertEqual(self.doc.status, MedicalDocument.STATUS_FAILED)
        self.assertIn("VLM timeout", self.doc.error_message)

    def test_task_noop_for_nonexistent_doc(self):
        """process_document should silently return if doc ID doesn't exist."""
        # Should not raise
        process_document(99999)
