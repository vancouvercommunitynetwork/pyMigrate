#!/usr/bin/env python
#
#
# TO DO
# Make useradd specify the mail folder as /dev/null and suppress the corresponding error message.
# Auto-change home directory to just /home
# Propagate user deletions. If they're not on the source they should be deleted from the destination.
# Document that passwords are the only user change this program updates.
# Write a getUserData(target=None) function that returns a list of usernames and a dictionary of Accounts.
# Remove the functions that return dictionaries of entries after switching over to getUserData().
# Add the feature of an unlistedUsersGetDeleted flag and default to false.
# Experiment with list operations to find best forms. In particular, doomedUsers should be formed by list subtraction.
# Error Modes to Cover:
#   No route to host: a remote machine can't be found on the network.
#   No SSH pre-authorization for remote machine.
#   SSH pre-authorization for remote machine exists but lacks root privilege.
#   Insufficient privilege. No root access on local machine.
#   The file couldn't be opened for lack of root privilege (local and remote /etc/shadow access).
#   Bad input file:
#       The specified file doesn't exist.
#       The specified file is empty.
#       The specified file is binary and possibly huge.
#       The file is wrong but coincidentally contains the username of a system user.
# Setup the script to return error codes

# Source Code Terminology
#   Entry: A line from /etc/passwd or /etc/shadow containing fields separated by colons.
#   Field: An item in a line from /etc/passwd or /etc/shadow.
#   User: Synonym for username.
#   Account: A data structure representing a user's data with attributes like UID and password.
#   Source: The machine that users are migrating from.
#   Destination: The machine that users are migrating to.
#   Migrants: The users whose usernames are listed in the text file given to this program.

# Conditions
#   The program will not alter system users (uid<1000).
#   The program will not alter user accounts on the machine it is run from.
#   The program will not alter the text file it is given (the one listing users to be migrated).

import subprocess
import commands

# Constants
LOWEST_USER_ID = 1000       # User IDs below this are for system accounts.
MOST_USERNAMES_TO_LIST = 5  # No message should dump more than this many usernames.


# An object to represent the attributes of a Linux user account.
class Account:
    # Construct an Account object using entries taken from /etc/passwd and /etc/shadow.
    def __init__(self, passwdEntry, shadowEntry):
        # Pull the needed fields from the entries. The field ordering in passwd and shadow are:
        #    username:password:userID:groupID:gecos:homeDir:shell
        #    username:password:lastchanged:minimum:maximum:warn:inactive:expire
        [self.username, self.password, self.uid, self.gid, self.gecos, \
            self.homeDir, self.shell] = passwdEntry.split(':')
        self.password = shadowEntry.split(':')[1]  # Second field in /etc/shadow is password.

    # Construct an Account object from an /etc/passwd entry.
    def __init__(self, passwdEntry):
        # Pull the needed fields from the entries. The field ordering in passwd and shadow are:
        #    username:password:userID:groupID:gecos:homeDir:shell
        #    username:password:lastchanged:minimum:maximum:warn:inactive:expire
        [self.username, self.password, self.uid, self.gid, self.gecos, \
            self.homeDir, self.shell] = passwdEntry.split(':')


# Converts a list of lines to a dictionary keyed on the first thing before the delimiter.
def makeDictBySplitToFirstField(lines, delimiter):
    dict = {}
    for line in lines:
        head = line.split(delimiter, 1)[0]
        dict[head] = line
    return dict


# Read /etc/passwd and /etc/shadow files to produce a list of the non-system usernames
# present on a system and a dictionary of Accounts keyed by username.
def getUserData(target=None):
    # Get file handles.
    if target is None:
        passwdFile = open('/etc/passwd', 'r')
        shadowFile = open('/etc/shadow', 'r')
    else:
        passwdFile = subprocess.Popen(['ssh', target, 'cat', '/etc/passwd'], stdout=subprocess.PIPE).stdout
        shadowFile = subprocess.Popen(['ssh', target, 'cat', '/etc/shadow'], stdout=subprocess.PIPE).stdout

    # Split text files into lists of lines.
    passwdEntries = passwdFile.read().splitlines()
    shadowEntries = shadowFile.read().splitlines()

    # Construct user list and preliminary user dictionary from passwd file entries.
    users, userAccountDict = [], {}
    for passwdEntry in passwdEntries:
        account = Account(passwdEntry)
        users.append(account.username)
        userAccountDict[account.username] = account

    # Replace account password field placeholders with actual passwords from /etc/shadow entries.
    for shadowEntry in shadowEntries:
        shadowFields = shadowEntry.split(':')
        username, shadowPassword = shadowFields[0], shadowFields[1]
        userAccountDict[username].password = shadowPassword

    return users, userAccountDict


# Read remote /etc/passwd and /etc/shadow files into dictionaries keyed by username.
def getRemoteUserEntries(target):
    # Read the /etc/passwd file into a list of lines, then convert it to a dictionary keyed by username.
    passwdFile = subprocess.Popen(['ssh', target, 'cat', '/etc/passwd'], stdout=subprocess.PIPE).stdout
    passwdEntries = passwdFile.read().splitlines()
    passwdDict = makeDictBySplitToFirstField(passwdEntries, ':')

    # Read the /etc/shadow file into a list of lines, then convert it to a dictionary keyed by username.
    shadowFile = subprocess.Popen(['ssh', target, 'cat', '/etc/shadow'], stdout=subprocess.PIPE).stdout
    shadowEntries = shadowFile.read().splitlines()
    shadowDict = makeDictBySplitToFirstField(shadowEntries, ':')

    return passwdDict, shadowDict


# Read local /etc/passwd and /etc/shadow files into dictionaries keyed by username.
def getLocalUserEntries():
    # Read the /etc/passwd file into a list of lines.
    with open('/etc/passwd', 'r') as localPasswdFile:
        passwdEntries = localPasswdFile.read().splitlines()
    passwdDict = makeDictBySplitToFirstField(passwdEntries, ':')

    # Read the /etc/shadow file into a dictionary of lines keyed by username.
    with open('/etc/shadow', 'r') as shadowPasswdFile:
        shadowEntries = shadowPasswdFile.read().splitlines()
    shadowDict = makeDictBySplitToFirstField(shadowEntries, ':')

    return passwdDict, shadowDict


# Convert passwd and shadow dictionaries into a list of Accounts while stripping out system users.
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


# Create a new user account at a remote machine.
def addRemoteUser(target, account):
    # Construct command.
    cmd = 'ssh -n ' + target + ' /usr/sbin/useradd -p "' + \
          account.password + '" -u ' + account.uid + ' -g ' + account.gid
    if account.gecos != "":
        cmd += '" -c "' + account.gecos + '"'
    cmd += ' -M -s ' + account.shell + ' ' + account.username
    output = commands.getoutput(cmd)
    if output:
        print output


# Delete a user account at a remote machine.
def deleteRemoteUser(target, username):
    # Construct command.
    cmd = 'ssh -n ' + target + ' /usr/sbin/deluser ' + username
    output = commands.getoutput(cmd)
    if output:
        print output


# Change a user password at a remote machine
def changeRemoteUserPassword(target, username, newPassword):
    # Construct command.
    cmd = "ssh -n " + target + " /usr/sbin/usermod -p '" + newPassword + "' " + username

    output = commands.getoutput(cmd)
    if output:
        print output


# Turn a list of usernames into a string while limiting the possible length of the string.
def usernameListToLimitedString(userList):
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
    # destAddress = 'root@192.168.20.45'
    destAddress = 'pi@192.168.1.11'
    migrantUsersFilename = 'list_of_users.txt'

    # Load user files from source and destination machines.
    srcPasswdDict, srcShadowDict = getLocalUserEntries()
    destPasswdDict, destShadowDict = getRemoteUserEntries(destAddress)

    # Load list of usernames from file of migrating users.
    with open(migrantUsersFilename, 'r') as migrantUsersFile:
        migrantUsers = migrantUsersFile.read().splitlines()

    # Create lists of usernames and some counters.
    missingUsers, newUsers, changedUsers, doomedUsers = [], [], [], []
    newUserCount, changedUserCount, unchangedUserCount = 0, 0, 0

    # Analyse users from the given text file of usernames.
    for username in migrantUsers:
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
            account.homeDir = "/home"  # Give all users the same home directory.
            print "Migrating new user: " + account.username
            addRemoteUser(destAddress, account)

    # Delete users at destination if they have been marked for destruction.
    if doomedUsers:
        for username in doomedUsers:
            deleteRemoteUser(destAddress, username)

    # Update changed users.
    if changedUsers:
        changedAccounts = getNonSystemAccounts(changedUsers, srcPasswdDict, srcShadowDict)
        for account in changedAccounts:
            print "Updating password for user: " + account.username
            changeRemoteUserPassword(destAddress, account.username, account.password)

    # Warn of usernames that were not found on the source machine.
    if missingUsers:
        print "WARNING: The following users were named in \"" + migrantUsersFilename + \
              "\" but could not be found on the source machine:",
        print usernameListToLimitedString(missingUsers)

    # Give a final accounting of the user migration results.
    print '\nUser outcomes: ' + str(len(newUsers)) + " migrated, " + str(len(changedUsers)) \
        + " updated, " + str(unchangedUserCount) + " unchanged, " + str(len(doomedUsers)) + " deleted, " \
        + str(len(missingUsers)) + " not found."

main()
