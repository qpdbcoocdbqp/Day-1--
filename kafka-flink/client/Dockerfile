FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY client.py .

ENTRYPOINT ["python", "client.py"]
CMD ["produce", "--rate", "5"]
