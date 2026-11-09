#!/bin/bash
# Run when INITIALIZE_DB parameter is set and migrations are available.
if ! python src/manage.py migrate --check && "$INITIALIZE_DB" = "true";
then
    python src/manage.py migrate;
fi
