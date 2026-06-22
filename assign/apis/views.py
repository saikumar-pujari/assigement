import logging

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

from .models import Job
from .serializers import JobSerializer, JobResultsSerializer, JobSummarySerializer
from .tasks import process_csv

logger = logging.getLogger(__name__)

MAX_CSV_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


class JobUploadView(APIView):
    """POST /jobs/upload — Upload CSV, create Job, enqueue Celery task."""
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        csv_file = request.FILES.get('file')
        if not csv_file:
            return Response(
                {'error': 'No file provided. Use multipart/form-data with key "file".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not csv_file.name.lower().endswith('.csv'):
            return Response(
                {'error': 'File must be a .csv'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if csv_file.size > MAX_CSV_SIZE_BYTES:
            return Response(
                {'error': 'File exceeds 10MB size limit.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            csv_content = csv_file.read().decode('utf-8')
        except UnicodeDecodeError:
            return Response(
                {'error': 'CSV file must be UTF-8 encoded.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lines = [l for l in csv_content.splitlines() if l.strip()]
        if len(lines) < 2:
            return Response(
                {'error': 'CSV file appears to be empty or contains only a header.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job = Job.objects.create(filename=csv_file.name)
        process_csv.delay(str(job.id), csv_content, csv_file.name)
        logger.info(f"Job {job.id} created for file '{csv_file.name}', enqueued.")

        return Response(
            {
                'job_id': str(job.id),
                'status': job.status,
                'message': 'Job accepted and queued for processing.',
            },
            status=status.HTTP_202_ACCEPTED,
        )


class JobStatusView(APIView):
    """GET /jobs/{job_id}/status"""

    def get(self, request, job_id):
        job = get_object_or_404(Job, id=job_id)
        data = JobSerializer(job).data

        if job.status == 'completed':
            try:
                s = job.summary
                data['summary'] = JobSummarySerializer(s).data
            except Exception:
                pass

        return Response(data)


class JobResultsView(APIView):
    """GET /jobs/{job_id}/results"""

    def get(self, request, job_id):
        job = get_object_or_404(Job, id=job_id)

        if job.status not in ('completed', 'failed'):
            return Response(
                {
                    'error': f"Job not yet complete. Current status: '{job.status}'. "
                             "Poll /jobs/{job_id}/status until status is 'completed'."
                },
                status=status.HTTP_425_TOO_EARLY,
            )

        return Response(JobResultsSerializer(job).data)


class JobListView(APIView):
    """GET /jobs?status=<pending|processing|completed|failed>"""

    def get(self, request):
        qs = Job.objects.all()
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        serializer = JobSerializer(qs, many=True)
        return Response({
            'count': qs.count(),
            'jobs': serializer.data,
        })
