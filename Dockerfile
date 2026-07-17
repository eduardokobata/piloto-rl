FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dil_container ./dil_container

EXPOSE 8090
CMD ["uvicorn", "dil_container.api:app", "--host", "0.0.0.0", "--port", "8090"]
