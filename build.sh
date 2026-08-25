#!/usr/bin/env bash
set -o errexit

# environment setup
python -m pip install "pip<24.1"
pip install -r requirements.txt

# handle static files
python manage.py collectstatic --no-input

echo "Apply database migrations"
python manage.py migrate --noinput

echo "create super user"
python manage.py create_super_user
python manage.py create_site_url
