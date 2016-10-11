#!/usr/bin/env bash

for i in $(seq 100 109)
do
    echo "Creating user test$i"
    useradd -g 1105 -s "/usr/sbin/nologin" -M test$i
done



