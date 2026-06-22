import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'assign.settings')

app = Celery('assign')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
