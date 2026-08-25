#!/usr/bin/env bash
set -o errexit

# environment setup
python -m pip install "pip<24.1"
pip install -r requirements.txt

# handle static files
python manage.py collectstatic --no-input

echo "Apply database migrations"
python manage.py migrate --noinput

if [[ "${OEF_RUN_GALLERY_PORT_ON_DEPLOY:-false}" == "true" ]]; then
    if [[ "${OEF_CLOUDINARY_ENVIRONMENT:-local}" != "production" ]]; then
        echo "Refusing gallery port outside the production Cloudinary environment" >&2
        exit 1
    fi
    echo "Port legacy production gallery assets and build the database index"
    python manage.py backfill_event_gallery_tags --execute --environment production
    python manage.py sync_event_gallery_index --execute --require-assets
fi

echo "create super user"
python manage.py create_super_user
python manage.py create_site_url
