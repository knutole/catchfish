#!/bin/bash

MONITORED_FILE=catchfish.py
# MONITORED_FILE2=catchfish2.py
MONITORED_FILE3=tests/test_classes.py
OLD_MD5=$(md5 $MONITORED_FILE)
# OLD_MD52=$(md5 $MONITORED_FILE2)
OLD_MD53=$(md5 $MONITORED_FILE3)

REMOTE_FOLDER=/home/ubuntu/catchfish/catchfish

while true; do
    MD5=$(md5 $MONITORED_FILE)
    # MD52=$(md5 $MONITORED_FILE2)
    MD53=$(md5 $MONITORED_FILE3)
    if [ "$MD5" != "$OLD_MD5" ]; then
        echo -ne "File changed, copying..."
        scp -q $MONITORED_FILE catchfish:$REMOTE_FOLDER
        OLD_MD5=$MD5
        echo "done!"
    fi 
    # if [ "$MD52" != "$OLD_MD52" ]; then
    #     echo -ne "File changed, copying..."
    #     OLD_MD52=$MD52
    #     scp -q catchfish2.py catchfish:$REMOTE_FOLDER
    #     echo "done!"
    # fi
    if [ "$MD53" != "$OLD_MD53" ]; then
        echo -ne "File changed, copying..."
        OLD_MD53=$MD53
        scp -q  $MONITORED_FILE3 catchfish:$REMOTE_FOLDER/$MONITORED_FILE3
        echo "done!"
    fi
    sleep 1
done