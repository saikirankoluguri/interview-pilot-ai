# FUTURE PLACEHOLDER: Docker is not used for the first POC deployment.
# Build from repository root: docker build -f deployment/docker/Dockerfile .
# Code goes in the image; model weights remain in cloud persistent storage.
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements-base.txt ./
RUN python -m pip install --no-cache-dir -r requirements-base.txt
COPY app ./app
COPY configs ./configs
COPY prompts ./prompts
# Status-only command at M0; add cloud runtime/user/volume policy in M4.
CMD ["python", "-m", "app.main"]
