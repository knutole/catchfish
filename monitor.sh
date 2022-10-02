#!/bin/bash

MONITORED_FILE1=catchfish.py
MONITORED_FILE2=analyse-it.py
MONITORED_FILE3=tests/test_classes.py
MONITORED_FILE4=evaluate-it.py
OLD_MD51=$(md5 $MONITORED_FILE1)
OLD_MD52=$(md5 $MONITORED_FILE2)
OLD_MD53=$(md5 $MONITORED_FILE3)
OLD_MD54=$(md5 $MONITORED_FILE4)

REMOTE_FOLDER=/home/ubuntu/catchfish/catchfish/

while true; do
    MD51=$(md5 $MONITORED_FILE1)
    MD52=$(md5 $MONITORED_FILE2)
    MD53=$(md5 $MONITORED_FILE3)
    MD54=$(md5 $MONITORED_FILE4)
    if [ "$MD51" != "$OLD_MD51" ]; then
        echo -ne "File changed, copying..."
        scp -q $MONITORED_FILE1 catchfish:$REMOTE_FOLDER
        OLD_MD51=$MD51
        echo "done!"
    fi 
   if [ "$MD52" != "$OLD_MD52" ]; then
        echo -ne "File changed, copying..."
        OLD_MD52=$MD52
        scp -q  $MONITORED_FILE2 catchfish:$REMOTE_FOLDER
        echo "done!"
    fi
    if [ "$MD53" != "$OLD_MD53" ]; then
        echo -ne "File changed, copying..."
        OLD_MD53=$MD53
        scp -q  $MONITORED_FILE3 catchfish:$REMOTE_FOLDER
        echo "done!"
    fi
    if [ "$MD54" != "$OLD_MD54" ]; then
        echo -ne "File changed, copying..."
        OLD_MD54=$MD54
        scp -q  $MONITORED_FILE4 catchfish:$REMOTE_FOLDER
        echo "done!"
    fi
    sleep 1
done