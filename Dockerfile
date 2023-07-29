FROM python:3.9.16-slim
EXPOSE 8080

ENV PROJECT_DIR /app
WORKDIR ${PROJECT_DIR}
ADD . ${PROJECT_DIR}/
RUN pip install --trusted-host pypi.python.org -r requirements.txt
COPY . .
CMD ["python", "main.py"]
