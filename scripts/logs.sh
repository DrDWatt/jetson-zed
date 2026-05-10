#!/bin/bash
# View logs from ZED Capture services
cd "$(dirname "$0")/.."

if [ -f docker-compose.orin.yml ]; then
    docker-compose -f docker-compose.orin.yml logs -f "$@"
else
    docker-compose logs -f "$@"
fi
