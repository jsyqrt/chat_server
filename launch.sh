#!/bin/bash

set -ex

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
LOG_DIR=$SCRIPT_DIR/log

cd $SCRIPT_DIR
mkdir -p $LOG_DIR

cd $SCRIPT_DIR
nohup flask --app zchat run --debug -h 0.0.0.0 >> $LOG_DIR/flask.log 2>&1 &
echo "flask started"

cd vectordb
nohup ./meilisearch --master-key="aSampleMasterKey" --no-analytics >> $LOG_DIR/meili.log 2>&1 &
echo "meili started"

cd $SCRIPT_DIR
nohup livekit-server --dev --bind 0.0.0.0 >> $LOG_DIR/livekit.log 2>&1 &
echo "livekit started"
