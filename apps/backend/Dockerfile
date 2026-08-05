FROM python:3.12-slim

WORKDIR /app

# Install deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ app/
COPY gunicorn.conf.py .

EXPOSE 8000

# Bind, workers, worker class and log routing all live in gunicorn.conf.py so
# that INFO goes to stdout and WARNING+ to stderr — otherwise every startup
# line lands on stderr and log platforms flag it as an error.
CMD ["gunicorn", "app.main:app", "-c", "gunicorn.conf.py"]
