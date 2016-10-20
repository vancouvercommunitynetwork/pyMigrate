#!/usr/bin/env bash

echo Creating dummies
for i in $(seq 2001 2006)
do
    useradd -u $i -g 1105 -s "/usr/sbin/nologin" -c "John Smith" -d "/home" -M dummy$i
done

grep dummy /etc/passwd