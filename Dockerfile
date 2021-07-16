# Pull base image
FROM python:3.8

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV AWS_ACCESS_KEY_ID="AKIATI4TZBPNID2AQEM2"
ENV AWS_SECRET_ACCESS_KEY="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"
ENV AWS_STORAGE_BUCKET_NAME="feedsomeonebucket"
ENV EMAIL_HOST_USER="femolak@outlook.com"
ENV EMAIL_HOST_PASS="Ia00eAKAmf"
ENV POSTGRES_DB_NAME="feedsomeone"
ENV POSTGRES_DB_PASS="Ia00eAKApf"
ENV POSTGRES_DB_USER="postgres"
ENV SECRET_KEY="5f*ovu$9jd%2io#8yy0t5o6_&dt)co-_z$#=d%^#*)3)y0uu(y"

# Set work directory
WORKDIR /code

# Install dependencies
COPY requirements.txt /code/
RUN pip install -r requirements.txt

# Copy project
COPY . /code/

