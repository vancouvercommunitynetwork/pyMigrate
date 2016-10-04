#!/usr/bin/env bash
echo -------------
echo CURRENT USERS
awk -F':' '{ if ( $3 >= 1000 && $3 <= 60000 ) print "    ", $0}' /etc/passwd
echo -------------
echo