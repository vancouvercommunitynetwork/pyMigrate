#!/usr/bin/env python

for i in range(14147, 15100):
    print "echo Fixing user " + str(i)
    print "usermod -g 1105 -u " + str(i+40000) + " -c \"fake user\" -p nopass -d /home -s /usr/sbin/nologin test" + str(i)