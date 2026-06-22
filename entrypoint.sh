#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
python -c "
import time, os
import psycopg2

for i in range(30):
    try:
        conn = psycopg2.connect(
            dbname=os.environ.get('POSTGRES_DB', 'txndb'),
            user=os.environ.get('POSTGRES_USER', 'txnuser'),
            password=os.environ.get('POSTGRES_PASSWORD', 'txnpass'),
            host=os.environ.get('POSTGRES_HOST', 'db'),
            port=os.environ.get('POSTGRES_PORT', '5432'),
        )
        conn.close()
        print('PostgreSQL is ready.')
        break
    except psycopg2.OperationalError:
        print(f'Waiting for database... ({i+1}/30)')
        time.sleep(1)
else:
    print('ERROR: Could not connect to PostgreSQL after 30 attempts.')
    exit(1)
"

if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Creating migrations..."
    python manage.py makemigrations --noinput
    echo "Running migrations..."
    python manage.py migrate --noinput
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
    echo "Creating superuser..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='saikumar').exists():
    User.objects.create_superuser('saikumar', 'saikumar@example.com', 'saikumar')
    print('Superuser created.')
else:
    print('Superuser already exists.')
"
    echo "Loading sample data..."
    python manage.py load_sample_data
fi

echo "Starting: $@"
exec "$@"
