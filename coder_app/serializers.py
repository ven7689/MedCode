from rest_framework import serializers
from .models import MedicalDocument


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalDocument
        fields = [
            "id",
            "file",
            "status",
            "vlm_results",
            "error_message",
            "created_at",
        ]
        read_only_fields = ["status", "vlm_results", "error_message", "created_at"]
