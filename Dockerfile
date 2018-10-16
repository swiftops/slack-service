FROM python:alpine

# Add your own code as per required by your microservice

# Do not change below code. If you want to do so connect with DevOps team.
RUN mkdir -p /usr/src/app

COPY . /usr/src/app

WORKDIR /usr/src/app

RUN pip3 install --no-cache-dir -r requirements.txt

EXPOSE 8080

ENTRYPOINT ["python3"]

CMD ["services.py"]
