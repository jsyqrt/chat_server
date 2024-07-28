#!/bin/bash

set -ex

# pkill flask
pkill meilisearch
pkill livekit-server
pkill redis-server
