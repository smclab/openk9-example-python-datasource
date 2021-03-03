FROM python:3.6

COPY ./requirements.txt /requirements.txt

RUN pip install -r requirements.txt

COPY ./app /app

WORKDIR /app

CMD ["gunicorn", "-w", "2", "-t", "60", "-b", "0.0.0.0:80", "main:app"]