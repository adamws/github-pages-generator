FROM python:3.10-alpine

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
  && rm requirements.txt

COPY github-pages-generator /action

ENTRYPOINT ["python", "/action/build.py"]
