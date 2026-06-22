from django.urls import path
from .views import JobUploadView, JobStatusView, JobResultsView, JobListView

urlpatterns = [
    path('jobs/upload', JobUploadView.as_view(), name='job-upload'),
    path('jobs/<uuid:job_id>/status', JobStatusView.as_view(), name='job-status'),
    path('jobs/<uuid:job_id>/results', JobResultsView.as_view(), name='job-results'),
    path('jobs', JobListView.as_view(), name='job-list'),
]
