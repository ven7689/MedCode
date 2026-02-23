import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Medcode.settings")

app = Celery("Medcode")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
