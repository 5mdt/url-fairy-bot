FROM python:3.11-buster
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt
WORKDIR /app
VOLUME [ "/cache" ]
CMD ["python", "/app/main.py"]
COPY main.py /app/
