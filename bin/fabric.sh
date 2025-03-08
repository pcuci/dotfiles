#!/usr/bin/env bash

# Path to your docker-compose.yml file
COMPOSE_PATH="$HOME/code/github/fabric/docker-compose.yml"

# Get the Fabric container name from docker-compose
CONTAINER_NAME=$(docker compose -f "$COMPOSE_PATH" ps -q fabric-api)

# Start the container if it's not running
if [ -z "$CONTAINER_NAME" ]; then
  echo "Starting the Fabric container..."
  docker compose -f "$COMPOSE_PATH" up -d
  CONTAINER_NAME=$(docker compose -f "$COMPOSE_PATH" ps -q fabric-api)
  if [ -z "$CONTAINER_NAME" ]; then
    echo "Failed to start the Fabric container. Exiting."
    exit 1
  fi
fi

# Function to run a pattern alias
run_pattern() {
  local pattern_name="$1"
  shift
  docker exec -i "$CONTAINER_NAME" sh -c "/fabric --stream --pattern /patterns/$pattern_name/system.md"
}

# Function to run the yt alias
yt_command() {
  local video_link="$1"
  docker exec "$CONTAINER_NAME" sh -c "/fabric -y "$video_link" --transcript"
}

# Parse the command
case "$1" in
  yt)
    shift
    yt_command "$@"
    ;;
  *)
    run_pattern "$@"
    ;;
esac
