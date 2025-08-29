FROM python:3
COPY . /usr/src/app
WORKDIR /usr/src/app
RUN pip install -r requirements.txt
CMD ["sh", "-c", "python manage.py startup_cmd && python manage.py process_tasks && python manage.py runserver 0.0.0.0:8000"]
EXPOSE 8000

