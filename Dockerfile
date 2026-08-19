FROM python:3.13-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY examples/python/fsae ./examples/python/fsae
COPY database/vehicles/fsae ./database/vehicles/fsae
COPY database/tracks/fsae_2019_endurance ./database/tracks/fsae_2019_endurance
COPY database/tracks/fsae_skidpad ./database/tracks/fsae_skidpad
COPY public ./public

ENV PYTHONPATH=/app/examples/python
ENV PYTHONUNBUFFERED=1

EXPOSE 18080

CMD ["python", "examples/python/fsae/qss_server.py", "--bind", "0.0.0.0", "--port", "18080", "-o", "/tmp/qss_out"]
