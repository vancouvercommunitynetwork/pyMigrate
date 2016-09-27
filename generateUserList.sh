#!/usr/bin/env bash

echo Overwriting userList.txt

echo > userList.txt

for i in $(seq 10 1000)
do
    echo test$i >> userList.txt
done

