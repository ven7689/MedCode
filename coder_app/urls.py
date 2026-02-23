from django.urls import path
from .views import UploadDocumentView, DocumentStatusView

urlpatterns = [
    path("upload/", UploadDocumentView.as_view()),
    path("documents/<int:pk>/", DocumentStatusView.as_view()),
]
