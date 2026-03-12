FROM python:3.12-slim

WORKDIR /app

COPY mycite-ne_mt/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY mycite-ne_mt/ /app/mycite-ne_mt/
COPY _shared/ /app/_shared/
COPY assets/ /app/assets/

WORKDIR /app/mycite-ne_mt

EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
