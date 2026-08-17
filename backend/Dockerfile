FROM python:3.12-slim

ARG INSTALL_CV=false

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt /tmp/requirements.txt
COPY backend/requirements-cv.txt /tmp/requirements-cv.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

RUN if [ "$INSTALL_CV" = "true" ]; then \
      pip install --no-cache-dir -r /tmp/requirements-cv.txt; \
    fi

COPY backend /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
