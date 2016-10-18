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
echo dummyMigrate >> $dummies
useradd -c "'fake user'" -u 40001 -g 1105 dummyMigrate
ssh -n $target deluser dummyMigrate

# !list, !source, dest. Deleted.
deluser dummyDelete
ssh -n $target useradd -c "'fake user'" -u 40002 -g 1105 dummyDelete

# list, !source, dest. Deleted.
echo dummyDelete2 >> $dummies
deluser dummyDelete2
ssh -n $target useradd -c "'fake user'" -u 40003 -g 1105 dummyDelete2

# !list, source, dest. Deleted if -u option, ignored otherwise.
useradd -c "'fake user'" -u 40004 -g 1105 dummyUnlisted
ssh -n $target useradd -c "'fake user'" -g 1105 dummyUnlisted

# !list, source, dest, changed. Deleted if -u option, updated otherwise.
useradd -c "'fake user'" -u 40005 -g 1105 dummyUpdateUL -p newpass
ssh -n $target deluser dummyUpdateUL
ssh -n $target useradd -c "'fake user'" -g 1105 dummyUpdateUL -p oldpass

# list, source, dest, changed. Updated.
echo dummyUpdate >> $dummies
useradd -c "'fake user'" -u 40006 -g 1105 dummyUpdate -p newpass
ssh -n $target deluser dummyUpdate
ssh -n $target useradd -c "'fake user'" -g 1105 dummyUpdate -p oldpass

# list, !source, !dest. Missing.
echo dummyMissing >> $dummies

# !list, source, !dest. Ignored
useradd -c "'fake user'" -u 40007 -g 1105 dummyIgnore

# list, source, dest. Ignored.
echo dummyIgnore2 >> $dummies
useradd -c "'fake user'" -u 40008 -g 1105 dummyIgnore2
ssh -n $target useradd -c "'fake user'" -g 1105 dummyIgnore2