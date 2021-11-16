#!/bin/bash

processes=$(ps aux -u vittorio | grep "python bot.py" | wc -l)

if [[ $processes -gt 1 ]]
then
    echo "Bot is already running"
else
    cd /home/vittorio/arxiv_daily
    git pull
    source venv/bin/activate
    python3 bot.py > output.txt &
    echo "Ok"
fi

