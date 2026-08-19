#!/usr/bin/env bash
set -o errexit

pip install -r ../requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate 
python manage.py flush --no-input
python manage.py loaddata data