#!/bin/bash

# Start the BotService API on port 8000
gunicorn --bind 0.0.0.0:8000 --worker-class aiohttp.worker.GunicornWebWorker --timeout 300 app:APP &

# Wait for any processes to exit
wait -n

# Exit with the status of the process that exited first
exit $?
