# syntax=docker/dockerfile:1.4
# COPY --link lets BuildKit treat tree copies as independent layers (often faster on large contexts).
FROM python:3.12-slim

WORKDIR /app

COPY runtime/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY --link runtime/ /app/runtime/
COPY --link _shared/ /app/_shared/
COPY --link assets/ /app/assets/

WORKDIR /app/runtime

EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
