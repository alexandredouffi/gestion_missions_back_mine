#!/usr/bin/env bash
set -o errexit

pip install --no-cache-dir -r ../requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate 
python manage.py flush --no-input
python manage.py loaddata data