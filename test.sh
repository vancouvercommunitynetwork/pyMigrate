#!/usr/bin/env bash

target="root@192.168.1.11"
dummies="test_users.txt"

rm $dummies  # Delete any existing copy of the list of test users.

# Normal migration case.
echo testm >> $dummies
useradd -g 1105 testm
ssh -n $target deluser testm

# !list, !source, dest. Deleted.
deluser testd1
ssh -n $target useradd -g 1105 testd1

# list, !source, dest. Deleted.
echo testd2 >> $dummies
deluser testd2
ssh -n $target useradd -g 1105 testd2

# !list, source, dest. Deleted if -u option, ignored otherwise.
useradd -g 1105 testugd
ssh -n $target useradd -g 1105 testugd

# !list, source, dest, changed. Deleted if -u option, updated otherwise.
useradd -g 1105 testugdpass -p newpass
ssh -n $target deluser testugdpass
ssh -n $target useradd -g 1105 testugdpass -p oldpass

# list, source, dest, changed. Updated.
echo testpass >> $dummies
useradd -g 1105 testpass -p newpass
ssh -n $target deluser testpass
ssh -n $target useradd -g 1105 testpass -p oldpass

# list, !source, !dest. Missing.
echo testmissing >> $dummies

# !list, source, !dest. Ignored
useradd -g 1105 testignore

# list, source, dest. Ignored.
echo testignore2 >> $dummies
useradd -g 1105 testignore2
ssh -n $target useradd -g 1105 testignore2