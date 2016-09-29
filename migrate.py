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
# Experiment with list operations to find concision. In particular, doomedUsers could be formed by list subtraction.
# Test performance of list building. A for-loop over migrantUsers may be more efficient than using list comprehensions.
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
EXIT_CODE_FAILURE_TO_OPEN_LOCAL_FILE = 1


# An object to represent the attributes of a Linux user account.
class Account:
    # Construct an Account object from an /etc/passwd entry.
    def __init__(self, passwdEntry):
        # Pull the needed fields from the entries. The field ordering in passwd and shadow are:
        #    username:password:userID:groupID:gecos:homeDir:shell
        #    username:password:lastchanged:minimum:maximum:warn:inactive:expire
        [self.username, self.password, self.uid, self.gid, self.gecos, \
            self.homeDir, self.shell] = passwdEntry.split(':')


# Attempt to open a local text file and convert to a list of lines.
def textFileIntoLines(filePath):
    try:
        with open(filePath, 'r') as textFile:
            textLines = textFile.read().splitlines()
    except IOError as e:
        print "ERROR: Unable to open local file."
        print e
        exit(EXIT_CODE_FAILURE_TO_OPEN_LOCAL_FILE)

    return textLines


# Read /etc/passwd and /etc/shadow files to produce a list of the non-system usernames
# present on a system and a dictionary of Accounts keyed by username.
def getNonSystemUserData(target=None):
    # Get file handles.
    if target is None:  # If no target was given then open local files.
        try:
            passwdFile = open('/etc/passwd', 'r')
            shadowFile = open('/etc/shadow', 'r')
        except IOError as e:
            print "ERROR: Unable to open local file."
            print e
            exit(EXIT_CODE_FAILURE_TO_OPEN_LOCAL_FILE)
    else:  # If a remote target was given then open remote files.
        passwdFile = subprocess.Popen(['ssh', target, 'cat', '/etc/passwd'], stdout=subprocess.PIPE).stdout
        shadowFile = subprocess.Popen(['ssh', target, 'cat', '/etc/shadow'], stdout=subprocess.PIPE).stdout

    # Split text files into lists of lines.
    passwdEntries = passwdFile.read().splitlines()
    shadowEntries = shadowFile.read().splitlines()

    # Construct user list and preliminary user dictionary from passwd file entries.
    users, userAccountDict = [], {}
    for passwdEntry in passwdEntries:
        account = Account(passwdEntry)
        if int(account.uid) >= LOWEST_USER_ID:  # Ignore system users.
            users.append(account.username)
            userAccountDict[account.username] = account

    # Replace account password field placeholders with actual passwords from /etc/shadow entries.
    for shadowEntry in shadowEntries:
        shadowFields = shadowEntry.split(':')
        username, shadowPassword = shadowFields[0], shadowFields[1]
        if username in userAccountDict:
            userAccountDict[username].password = shadowPassword

    return users, userAccountDict


# Create a new user account at a remote machine.
# NOTE: User fields are copied as is with the exceptions:
#       home directory is forced to be /home
#       shell is forced to be /usr/sbin/nologin
def addRemoteUser(target, account):
    # Construct and execute command to remotely add user.
    cmd = 'ssh -n ' + target + ' /usr/sbin/useradd -p "' + \
          account.password + '" -u ' + account.uid + ' -g ' + account.gid
    if account.gecos != "":
        cmd += '" -c "' + account.gecos + '"'
    cmd += ' -d "/home" -M -s "/usr/sbin/nologin" ' + account.username

    output = commands.getoutput(cmd)
    if output:
        print output


# Delete a user account at a remote machine.
def deleteRemoteUser(target, username):
    # Construct command.
    cmd = 'ssh -n ' + target + ' /usr/sbin/deluser -quiet ' + username

    output = commands.getoutput(cmd)
    if output:
        print output


# Change a user password at a remote machine
def updateRemoteUserPassword(target, username, newPassword):
    # Construct command.
    cmd = "ssh -n " + target + " /usr/sbin/usermod -p '" + newPassword + "' " + username

    output = commands.getoutput(cmd)
    if output:
        print output


# Turn a list of usernames into a string but limit the possible length of the string.
# Example: ["user1", "user2", "user3", "user4", "user5", "user6", "user7"]
# Becomes: "user1 user2 user3 user4 user5 ...and 2 others."
def usernameListToLimitedString(userList):
    global MOST_USERNAMES_TO_LIST
    returnString = ""
    # If there aren't too many usernames then list them all.
    if len(userList) <= MOST_USERNAMES_TO_LIST:
        for username in userList:
            returnString += username + ' '
    # If there's lots of usernames then just list the first few.
    else:
        for username in userList[:MOST_USERNAMES_TO_LIST]:
            returnString += username + ' '
        returnString += "...and " + \
            str(len(userList) - MOST_USERNAMES_TO_LIST) + " others."
    return returnString


def main():
    # Settings that will later be taken as command-line arguments.
    destAddress = 'root@192.168.20.45'
    # destAddress = 'pi@192.168.1.11'
    migrantUsersFilename = 'list_of_users.txt'
    deleteUnlistedUsersFlag = True

    srcUsers, srcAccountDict = getNonSystemUserData()
    destUsers, destAccountDict = getNonSystemUserData(destAddress)

    # Load list of usernames from file of migrating users.
    migrantUsers = textFileIntoLines(migrantUsersFilename)

    # Any users at destination and not at source should be marked for deletion.
    doomedUsers = [user for user in destUsers if user not in srcUsers]

    # If desired then also delete users who are not listed as migrants.
    if deleteUnlistedUsersFlag:
        unlistedUsers = [user for user in destUsers if user not in migrantUsers]
        doomedUsers += [user for user in unlistedUsers if user not in doomedUsers]
        print "Unlisted users: " + usernameListToLimitedString(unlistedUsers)  # DEBUG

    # Create lists of usernames and some counters.
    missingUsers, newUsers, changedUsers = [], [], []
    newUserCount, changedUserCount, unchangedUserCount = 0, 0, 0

    # Analyze migrating users listed in the given text file.
    for username in migrantUsers:
        # If username not found at source machine add them to list of missing users.
        if username not in srcUsers:
            missingUsers.append(username)

        # If username found at source but not at destination then copy user over.
        if username in srcUsers and username not in destUsers:
            newUsers.append(username)

        # If username found at source and destination then check if password has changed.
        if username in srcUsers and username in destUsers:
            if srcAccountDict[username].password != destAccountDict[username].password:
                changedUsers.append(username)
            else:
                unchangedUserCount += 1

    # Migrate new users.
    for username in newUsers:
        print "Migrating new user: " + username  # DEBUG
        addRemoteUser(destAddress, srcAccountDict[username])

    # Delete users at destination if they have been marked for destruction.
    for username in doomedUsers:
        print "Deleting user: " + username  # DEBUG
        deleteRemoteUser(destAddress, username)

    # Update users who have changed their password.
    for username in changedUsers:
        print "Updating password for user: " + username  # DEBUG
        updateRemoteUserPassword(destAddress, username, srcAccountDict[username].password)

    # Warn of usernames that were not found on the source machine.
    if missingUsers:
        print "WARNING: The following users were named in \"" + migrantUsersFilename + \
              "\" but could not be found on the source machine:",
        print usernameListToLimitedString(missingUsers)

    # Give a final accounting of the user migration results.
    print "\nUser outcomes: " + str(len(newUsers)) + " migrated, " + str(len(changedUsers)) \
        + " updated, " + str(unchangedUserCount) + " unchanged, " + str(len(doomedUsers)) + " deleted, " \
        + str(len(missingUsers)) + " not found."

main()
