#!/usr/bin/env bash

cut -d: -f1 /etc/passwd | grep test | while read name; do 
    deluser "$name"
done 

