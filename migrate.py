#!/usr/bin/env python
#
# TODO
#
# Error Modes to Cover:
#   No route to host: a remote machine can't be found on the network.
#   Bad input file:
#       The specified file doesn't exist.
#       The specified file is empty.
#       The specified file is binary and possibly huge.
#       The file is wrong but coincidentally contains the username of a system user.


import subprocess
# ssh = subprocess.Popen(['ssh', 'pi@192.168.1.11', 'cat', '/etc/passwd'], stdout=subprocess.PIPE)


class Account():
    def __init__(self, passwdEntry, shadowEntry):            #  <------------- PICK UP HERE AND BELOW
        # passwdString = passwdDict[username]
        # TODO: split the strings into the fields and return an instance of Account

# Converts a list of lines to a dictionary keyed on the first thing before the delimiter.
def makeDictBySplitToFirstField(lines, delimiter):
    dict = {}
    for line in lines:
        head = line.split(delimiter, 1)[0]
        dict[head] = line
    return dict


def getRemoteUserData(target):
    # Read the /etc/passwd file into a list of lines, then convert it to a dictionary keyed by username.
    passwdFile = subprocess.Popen(['ssh', target, 'cat', '/etc/passwd'], stdout=subprocess.PIPE).stdout
    passwdEntries = passwdFile.read().splitlines()
    passwdDict = makeDictBySplitToFirstField(passwdEntries, ':')

    # Read the /etc/shadow file into a list of lines, then convert it to a dictionary keyed by username.
    shadowFile = subprocess.Popen(['ssh', target, 'sudo cat', '/etc/shadow'], stdout=subprocess.PIPE).stdout
    shadowEntries = shadowFile.read().splitlines()
    shadowDict = makeDictBySplitToFirstField(shadowEntries, ':')

    return passwdDict, shadowDict


def getLocalUserData():
    # Read the /etc/passwd file into a list of lines.
    with open('/etc/passwd', 'r') as localPasswdFile:
        passwdEntries = localPasswdFile.read().splitlines()
    passwdDict = makeDictBySplitToFirstField(passwdEntries, ':')

    # Read the /etc/shadow file into a dictionary of lines keyed by username.
    with open('fakeShadow', 'r') as shadowPasswdFile:
    # with open('/etc/shadow', 'r') as shadowPasswdFile:
        shadowEntries = shadowPasswdFile.read().splitlines()
    shadowDict = makeDictBySplitToFirstField(shadowEntries, ':')

    return passwdDict, shadowDict


# Load user files from source and destination machines.
srcPasswdDict, srcShadowDict = getLocalUserData()
destPasswdDict, destShadowDict = getRemoteUserData('pi@192.168.1.11')

# Load list of users.
with open('list_of_users.txt', 'r') as localPasswdFile:
    userList = localPasswdFile.read().splitlines()

# Create three lists of user names.
missingUsers, newUsers, changedUsers = [], [], []

# Look for users that are missing from the source, new at the destination or
# present at both but have account attributes that have changed.
for username in userList:
    # If a user is not found on the source machine then mark it as missing.
    if username not in srcPasswdDict:
        missingUsers.append(username)

    # If a user exists at the source but not the destination then mark it as a new user.
    if username in srcPasswdDict and username not in destPasswdDict:
        newUsers.append(username)

    # If a user exists at both the source and the destination then check if it has changed.
    if username in srcPasswdDict and username in destPasswdDict:
        if srcPasswdDict[username] != destPasswdDict[username]:
            changedUsers.append(username)
        elif srcShadowDict[username] != destShadowDict[username]:
            changedUsers.append(username)

# Migrate new users.
if newUsers:
    for username in newUsers:
        # Convert username to user Account instance.
        account = Account(srcPasswdDict[username], srcShadowDict[username])    # <------------ PICK UP HERE AND ABOVE
        # Disregard system users.
        # if username.uid < 1000:  <-- I know this won't work, but something like this.

        print "Migrating new user: " + username

# Update changed users.
if changedUsers:
    for username in changedUsers:
        # Disregard system users.
        # if username.uid < 1000:  <-- I know this won't work, but something like this.

        print "Updating pre-existing users: " + username

# Warn of user names that were not found on the source machine.
if missingUsers:
    print "WARNING: The following users could not be found on the source machine:",
    for username in missingUsers:
        print username,



# print userList[1]
# print destPasswdDict['test3']
# print getLocalUserData()


