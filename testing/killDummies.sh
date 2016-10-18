#!/usr/bin/env bash

cut -d: -f1 /etc/passwd | grep dummy | while read name; do
    echo Deleting $name
    deluser "$name" > /dev/null
done