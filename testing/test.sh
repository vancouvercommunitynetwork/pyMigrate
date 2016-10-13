#!/usr/bin/env bash

# A script for generating a set of users that will test all the use cases of the program.
dummies="list_of_users_for_testing.txt"

# Check that a destination argument was given.
if [ $# -ne 1 ]; then
    echo Missing destination
    echo USAGE EXAMPLE: $0 root@192.168.1.257
    exit 1
fi

target=$1

rm $dummies  # Delete any existing copy of the list of test users.

for i in $(seq 100 15099)
do
    echo test$i >> $dummies
done

# Normal migration case.
echo testMigrate >> $dummies
useradd -c "'fake user'" -u 40001 -g 1105 testMigrate
ssh -n $target deluser testMigrate

# !list, !source, dest. Deleted.
deluser testDelete
ssh -n $target useradd -c "'fake user'" -u 40002 -g 1105 testDelete

# list, !source, dest. Deleted.
echo testDelete2 >> $dummies
deluser testDelete2
ssh -n $target useradd -c "'fake user'" -u 40003 -g 1105 testDelete2

# !list, source, dest. Deleted if -u option, ignored otherwise.
useradd -c "'fake user'" -u 40004 -g 1105 testUnlisted
ssh -n $target useradd -c "'fake user'" -g 1105 testUnlisted

# !list, source, dest, changed. Deleted if -u option, updated otherwise.
useradd -c "'fake user'" -u 40005 -g 1105 testUpdateUL -p newpass
ssh -n $target deluser testUpdateUL
ssh -n $target useradd -c "'fake user'" -g 1105 testUpdateUL -p oldpass

# list, source, dest, changed. Updated.
echo testUpdate >> $dummies
useradd -c "'fake user'" -u 40006 -g 1105 testUpdate -p newpass
ssh -n $target deluser testUpdate
ssh -n $target useradd -c "'fake user'" -g 1105 testUpdate -p oldpass

# list, !source, !dest. Missing.
echo testMissing >> $dummies

# !list, source, !dest. Ignored
useradd -c "'fake user'" -u 40007 -g 1105 testIgnore

# list, source, dest. Ignored.
echo testIgnore2 >> $dummies
useradd -c "'fake user'" -u 40008 -g 1105 testIgnore2
ssh -n $target useradd -c "'fake user'" -g 1105 testIgnore2