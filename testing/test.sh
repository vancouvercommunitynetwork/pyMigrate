#!/usr/bin/env bash

# A script for generating a set of users that will test all the use cases of the program.
target="root@192.168.20.45"
dummies="test_users.txt"

rm $dummies  # Delete any existing copy of the list of test users.

# Normal migration case.
echo testm >> $dummies
useradd -c "'fake user'" -u 2001 -g 1105 testm
ssh -n $target deluser testm

# !list, !source, dest. Deleted.
deluser testd1
ssh -n $target useradd -c "'fake user'" -u 2002 -g 1105 testd1

# list, !source, dest. Deleted.
echo testd2 >> $dummies
deluser testd2
ssh -n $target useradd -c "'fake user'" -u 2003 -g 1105 testd2

# !list, source, dest. Deleted if -u option, ignored otherwise.
useradd -c "'fake user'" -u 2004 -g 1105 testugd
ssh -n $target useradd -c "'fake user'" -g 1105 testugd

# !list, source, dest, changed. Deleted if -u option, updated otherwise.
useradd -c "'fake user'" -u 2005 -g 1105 testugdpass -p newpass
ssh -n $target deluser testugdpass
ssh -n $target useradd -c "'fake user'" -g 1105 testugdpass -p oldpass

# list, source, dest, changed. Updated.
echo testpass >> $dummies
useradd -c "'fake user'" -u 2006 -g 1105 testpass -p newpass
ssh -n $target deluser testpass
ssh -n $target useradd -c "'fake user'" -g 1105 testpass -p oldpass

# list, !source, !dest. Missing.
echo testmissing >> $dummies

# !list, source, !dest. Ignored
useradd -c "'fake user'" -u 2007 -g 1105 testignore

# list, source, dest. Ignored.
echo testignore2 >> $dummies
useradd -c "'fake user'" -u 2008 -g 1105 testignore2
ssh -n $target useradd -c "'fake user'" -g 1105 testignore2