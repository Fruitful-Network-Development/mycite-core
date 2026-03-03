FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies (portal prototype requirements are minimal)
COPY mycite-le_fnd/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy portal instance code + shared dev assets (icons)
COPY mycite-le_fnd/ /app/mycite-le_fnd/
COPY assets/ /app/assets/

WORKDIR /app/mycite-le_fnd

EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]

