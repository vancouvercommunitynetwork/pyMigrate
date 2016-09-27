#!/usr/bin/env bash

for i in $(seq 11 20)
do
    echo "Creating user test$i"
    useradd -g 1105 -s "/sbin/nologin" -M test$i
done



