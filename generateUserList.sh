#!/usr/bin/env bash

echo Overwriting userList.txt

rm userList.txt

for i in $(seq 100 1099)
do
    echo test$i >> userList.txt
done

