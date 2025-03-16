#!/bin/bash

set -x

kill -9 $(ps aux|grep flask|awk '{print $2 }')
# pkill meilisearch
# pkill livekit-server
# pkill redis-server
# docker stop $(docker ps|grep livekit|awk '{print $1 }')
