FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --system --uid 10001 appuser && mkdir -p /srv/app/data /srv/app/hosted_bots && chown -R appuser:appuser /srv/app
USER appuser
CMD ["python","main.py"]
