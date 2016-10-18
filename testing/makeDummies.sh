#!/usr/bin/env bash

echo Creating dummies
for i in $(seq 40000 40003)
do
    useradd -g 1105 -s "/usr/sbin/nologin" -c "John Smith" -d "/home" -M dummy$i
done

grep dummy /etc/passwd