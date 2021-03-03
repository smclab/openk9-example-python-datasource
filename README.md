# Example Python Parser

This is an example of Parser to connect a data source to Openk9 Search System.\
This example takes up the case of extracting users from a Liferay portal, using Json APIs.
The parser is written in Python code, using Flask framework, to build it as Rest service.\
The service can then be built as Docker container, and executed with Gunicorn ad WSGI application server.

## Parser Api

### Execute endpoint

Every parser needs an endpoint to run and schedule extraction and parsing from the chosen data source. You can modify 
the endpoint *execute* in the *main.py* file for your own purposes.\
Modify the parameters to be taken from the request 
and then modify the class that defines the extraction asynchronous task.

### Status endpoint

It presents also an endpoint to get the current status of extraction task. Use *status-logger* to log every event, 
and automatically this will be retrieved by calling this endpoint.

### Swagger

In *static* folder is present code to view, at the root url endpoint, a Swagger with Openapi declaration 
of available endpoints.

## Extraction task

In *extraction* folder, inside *user_extraction.py* file, is defined an asynchronous task, to execute extraction from
specific data source. \
Modify this with your own logic, to call external APIs, or other components, to retrieve data, and then send them to 
Openk9 Ingestion APIs.

## Ingestion Api Endpoint

Ingestion Api enpoint must be passed as an environment variable to Docker container.\
Set *INGESTION_URL* to *<host>/api/v1/ingestion/*, replacing the host.


## Build and Run

Build your service with:
```
docker build -t example-parser .
```

The run with
```
docker run -p 5000:80 -e INGESTION_URL=<host>/api/v1/ingestion/ --name example-parser example-parser:latest
```

or eventually ad it to your docker-compose file
```
example-parser:
    image: example-parser:latest
    container_name: example-parser
    command: gunicorn -w 1 -t 60 -b 0.0.0.0:80 main:app
    ports:
        - "5000:80"
    environment:
        INGESTION_URL: <host>/api/v1/ingestion/
```

