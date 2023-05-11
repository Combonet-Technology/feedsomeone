#!/usr/bin/env bash
# exit on error
set -o errexit

# environment setup
pip install --upgrade pip
pip install -r requirements.txt

# handle static files
python manage.py collectstatic --no-input

echo "migration commands"
#python manage.py makemigrations
python manage.py showmigrations
python manage.py migrate

echo "create super user"
python manage.py create_super_user
