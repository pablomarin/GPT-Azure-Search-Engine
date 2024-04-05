#!/bin/bash

# Starts the LangServe FastAPI on port 8000
gunicorn --bind 0.0.0.0:8000 --worker-class uvicorn.workers.UvicornWorker --timeout 300 server:app &

# Wait for any processes to exit
wait -n

# Exit with the status of the process that exited first
exit $?
