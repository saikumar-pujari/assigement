import os
from pathlib import Path
from django.core.management.base import BaseCommand
from apis.models import Job
from apis.tasks import process_csv


CSV_PATH = Path('/app/data/transactions.csv')


class Command(BaseCommand):
    help = 'Load transactions.csv into the pipeline and persist results to the database.'

    def handle(self, *args, **options):
        if not CSV_PATH.exists():
            self.stderr.write(f'CSV not found at {CSV_PATH}')
            return

        if Job.objects.exists():
            self.stdout.write('Data already loaded (jobs exist). Skipping.')
            return

        csv_content = CSV_PATH.read_text(encoding='utf-8')
        filename = CSV_PATH.name

        job = Job.objects.create(filename=filename)
        process_csv.delay(str(job.id), csv_content, filename)

        self.stdout.write(
            self.style.SUCCESS(
                f'Job {job.id} created and queued. '
                f'Check status at /jobs/{job.id}/status'
            )
        )
