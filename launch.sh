#!/bin/bash

# Versions:
# flask --version
#   Python 3.11.9
#   Flask 3.0.3
#   Werkzeug 3.0.3
# ./meilisearch --version
#   meilisearch 1.8.3
# redis-server --version
#   Redis server v=7.2.5 sha=00000000:0 malloc=libc bits=64 build=bd81cd1340e80580
# livekit-server --version
#   livekit-server version 1.7.0
# lk --version
#   lk version 2.0.4

set -ex

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
LOG_DIR=$SCRIPT_DIR/log
INSTANCE_DIR=$SCRIPT_DIR/instance
# LIVEKIT_CONFIG_DIR=$SCRIPT_DIR/zchat/livekit

cd $SCRIPT_DIR
mkdir -p $LOG_DIR

cd $SCRIPT_DIR/vectordb
nohup ./meilisearch --http-addr 0.0.0.0:7700 --db-path $INSTANCE_DIR/meilidata.ms --master-key="aSampleMasterKey" --no-analytics >> $LOG_DIR/meili.log 2>&1 &
echo "meili started"
sleep 5

cd $SCRIPT_DIR
nohup flask --app zchat run --debug -h 0.0.0.0 >> $LOG_DIR/flask.log 2>&1 &
echo "flask started"

sleep 10
tail -n 20 $LOG_DIR/flask.log

# cd $INSTANCE_DIR
# nohup redis-server $LIVEKIT_CONFIG_DIR/redis.conf >> $LOG_DIR/redis.log 2>&1 &
# echo "redis started"

# sleep 5
# nohup livekit-server --dev --bind 0.0.0.0 --config $LIVEKIT_CONFIG_DIR/livekit.yaml >> $LOG_DIR/livekit.log 2>&1 &
# echo "livekit started"

# sleep 5
# nohup docker run --rm \
#     --cap-add SYS_ADMIN \
#     -e EGRESS_CONFIG_FILE=/config/egress.conf \
#     -v $INSTANCE_DIR/livekit:/out \
#     -v $LIVEKIT_CONFIG_DIR:/config \
#     --security-opt seccomp=$LIVEKIT_CONFIG_DIR/chrome-sandboxing-seccomp-profile.json \
#     livekit/egress:v1.8.5 >> $LOG_DIR/livekit-egress.log 2>&1 &
# echo "livekit egress started"
