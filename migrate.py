#!/usr/bin/env python

	
with open('/etc/passwd','r') as localPasswdFile:
    lines = localPasswdFile.readlines()

for line in lines:
    print line.split(':')
    

