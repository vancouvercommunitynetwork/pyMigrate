#!/usr/bin/env python
#
#
# TO DO
# Explore all cases of whether a user is present at the source, present at the destination and/or present in the list_of_users.txt
# Make useradd either not create a mail folder or specify the mail folder as /dev/null and suppress the error message it produces.
# Propagate user deletions. If they're not on the source they should be deleted from the destination.
# Document that passwords are the only user change this program updates.
# Error Modes to Cover:
#   No route to host: a remote machine can't be found on the network.
#   No SSH pre-authorization for remote machine.
#   SSH pre-authorization for remote machine exists but lacks root privilege.
#   Insufficient privilege. No root access on local machine.
#   Bad input file:
#       The specified file doesn't exist.
#       The specified file is empty.
#       The specified file is binary and possibly huge.
#       The file is wrong but coincidentally contains the username of a system user.


import subprocess
import commands

# Constants
LOWEST_USER_ID = 1000       # User IDs below this are for system accounts.
MOST_USERNAMES_TO_LIST = 5  # No message should dump more than this many usernames.


# An object to represent the attributes of a linux user account.
class Account:
    def __init__(self, passwdEntry, shadowEntry):
        # Pull the needed fields from the entries. The field ordering in passwd and shadow are:
        #    username:password:userID:groupID:gecos:homeDir:shell
        #    username:password:lastchanged:minimum:maximum:warn:inactive:expire
        # TO DO: split the strings into the fields and return an instance of Account
        [self.username, self.password, self.uid, self.gid, self.gecos, \
            self.homeDir, self.shell] = passwdEntry.split(':')
        self.password = shadowEntry.split(':')[1]  # Second field in shadow is password.


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
    shadowFile = subprocess.Popen(['ssh', target, 'cat', '/etc/shadow'], stdout=subprocess.PIPE).stdout
    shadowEntries = shadowFile.read().splitlines()
    shadowDict = makeDictBySplitToFirstField(shadowEntries, ':')

    return passwdDict, shadowDict


def getLocalUserData():
    # Read the /etc/passwd file into a list of lines.
    with open('/etc/passwd', 'r') as localPasswdFile:
        passwdEntries = localPasswdFile.read().splitlines()
    passwdDict = makeDictBySplitToFirstField(passwdEntries, ':')

    # Read the /etc/shadow file into a dictionary of lines keyed by username.
    with open('/etc/shadow', 'r') as shadowPasswdFile:
        shadowEntries = shadowPasswdFile.read().splitlines()
    shadowDict = makeDictBySplitToFirstField(shadowEntries, ':')

    return passwdDict, shadowDict


def getNonSystemAccounts(usernameList, passwdDict, shadowDict):
    accountList = []
    for username in usernameList:
        # Convert username to user Account instance.
        account = Account(passwdDict[username], shadowDict[username])

        # Disregard system users.
        if account.uid < LOWEST_USER_ID:
            continue
        accountList.append(account)

    return accountList


def sshAddRemoteUser(target, account):
    # Construct command.
    cmd = 'ssh -n ' + target + ' /usr/sbin/useradd -p "' + \
          account.password + '" -u ' + account.uid + ' -g ' + account.gid
    if account.gecos != "":
        cmd += '" -c "' + account.gecos + '"'
    cmd += ' -M -s ' + account.shell + ' ' + account.username
    output = commands.getoutput(cmd)
    if output:
        print output


def sshDeleteRemoteUser(target, username):
    # Construct command.
    cmd = 'ssh -n ' + target + ' /usr/sbin/deluser ' + username
    output = commands.getoutput(cmd)
    if output:
        print output


def sshChangeUserPassword(target, username, newPassword):
    # Construct command.
    cmd = "ssh -n " + target + " /usr/sbin/usermod -p '" + newPassword + "' " + username

    output = commands.getoutput(cmd)
    if output:
        print output


def limitedUserListString(userList):
    global MOST_USERNAMES_TO_LIST
    returnString = ""
    # Construct a string listing users without being too long.
    if len(userList) <= MOST_USERNAMES_TO_LIST:
        for username in userList:
            returnString += username + ' '
    # If there's lots of missing users then just list the first few
    else:
        for username in userList[:MOST_USERNAMES_TO_LIST]:
            print username,
            returnString += "... and " + \
                str(len(userList) - MOST_USERNAMES_TO_LIST) + " others."
    return returnString


def main():
    # Settings that will later be taken as command-line arguments.
    destAddress = 'root@192.168.20.45'
    # destAddress = 'pi@192.168.1.11'
    userListFile = 'list_of_users.txt'

    # Load user files from source and destination machines.
    srcPasswdDict, srcShadowDict = getLocalUserData()
    destPasswdDict, destShadowDict = getRemoteUserData(destAddress)

    # Load list of users.
    with open(userListFile, 'r') as localPasswdFile:
        userList = localPasswdFile.read().splitlines()

    # Create lists of user names and some counters.
    missingUsers, newUsers, changedUsers, doomedUsers = [], [], [], []
    newUserCount, changedUserCount, unchangedUserCount = 0, 0, 0

    # Analyse users from the given text file of usernames.
    for username in userList:
        # If username not found at source machine add them to list of missing users.
        if username not in srcPasswdDict:
            missingUsers.append(username)

        # If username found at source but not at destination then copy user over.
        if username in srcPasswdDict and username not in destPasswdDict:
            newUsers.append(username)

        # If username not found at source but found at destination then delete user.
        if username not in srcPasswdDict and username in destPasswdDict:
            doomedUsers.append(username)

        # If username found at source and destination then check if password has changed.
        if username in srcPasswdDict and username in destPasswdDict:
            srcPassword = srcShadowDict[username].split(':')[1]
            destPassword = destShadowDict[username].split(':')[1]
            if srcPassword != destPassword:
                changedUsers.append(username)
            else:
                unchangedUserCount += 1

    # Migrate new users.
    if newUsers:
        newAccounts = getNonSystemAccounts(newUsers, srcPasswdDict, srcShadowDict)
        for account in newAccounts:
            account.shell = "/usr/sbin/nologin"  # Disable shell for security sake.
            print "Migrating new user: " + account.username
            sshAddRemoteUser(destAddress, account)

    # Delete users at destination if they don't exist at source machine.
    if doomedUsers:
        for username in doomedUsers:
            sshDeleteRemoteUser(destAddress, username)

    # Update changed users.
    if changedUsers:
        changedAccounts = getNonSystemAccounts(changedUsers, srcPasswdDict, srcShadowDict)
        for account in changedAccounts:
            print "Updating password for user: " + account.username
            sshChangeUserPassword(destAddress, account.username, account.password)

    # Warn of user names that were not found on the source machine.
    if missingUsers:
        print "WARNING: The following users were named in \"" + userListFile + \
              "\" but could not be found on the source machine:",
        print limitedUserListString(missingUsers)

    # Give a final accounting the user migration results.
    print '\nUser outcomes: ' + str(len(newUsers)) + " migrated, " + str(len(changedUsers)) \
        + " updated, " + str(unchangedUserCount) + " unchanged, " \
        + str(len(missingUsers)) + " not found."

main()
