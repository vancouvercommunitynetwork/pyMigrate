#!/usr/bin/env python
#
#
# TO DO
# Make sure that it locks out simultaneous execution.
# Create a few hundred users and test the running time of the program.
# Test that it correctly produces the user outcomes described in the decision tree spreadsheet and make sure that you have one example of every combination so you can test that none of them interfere with each other.
# Error Modes to Cover:
#   User gives 3 command-line arguments but one of them is an option (which will get read as file list).
#   No route to host: a remote machine can't be found on the network.
#   No SSH pre-authorization for remote machine.
#   SSH pre-authorization for remote machine exists but lacks root privilege.
#   Insufficient privilege. No root access on local machine.
#   The file couldn't be opened for lack of root privilege (local and remote /etc/shadow access).
#   Bad input file:
#       The specified file doesn't exist.
#       The specified file is empty.
#       The specified file is binary and possibly huge.
# Write the README.MD to describe the program.

# Source Code Terminology
#   Entry: A line from /etc/passwd or /etc/shadow containing. These contain fields separated by colons.
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
import sys
import fcntl

# Constants
LOWEST_USER_ID = 1001       # User IDs below this are not interfered with.
MOST_USERNAMES_TO_LIST = 5  # No message should dump more than this many usernames.
EXIT_CODE_SUCCESS = 0
EXIT_CODE_FAILURE_TO_OPEN_LOCAL_FILE = 1
EXIT_CODE_TOO_FEW_ARGUMENTS = 2
EXIT_CODE_HELP_MESSAGE = 3
EXIT_CODE_FOUND_UNCATEGORIZED_USERS = 4


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


# Execute a console command and print results.
def executeCommandWithEcho(command):
    status, output = commands.getstatusoutput(command)
    if output:
        print output
    return status


# Read /etc/passwd and /etc/shadow files to produce a list of the non-system usernames
# present on a system and a dictionary of Accounts keyed by username.
def getUsers(target=None):
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


# Get a list of usernames and a dictionary of user data from local machine.
def getLocalUsers():
    return getUsers()


# Get a list of usernames and a dictionary of user data from remote machine.
def getRemoteUsers(target):
    return getUsers(target)


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
    cmd += ' -d "/home" -M -s "/usr/sbin/nologin" -K MAIL_DIR=/dev/null ' + account.username
    return executeCommandWithEcho(cmd)


# Delete a user account at a remote machine.
def deleteRemoteUser(target, username):
    # Construct and execute command to remotely delete user.
    cmd = 'ssh -n ' + target + ' /usr/sbin/deluser -quiet ' + username
    executeCommandWithEcho(cmd)


# Change a user password at a remote machine
def updateRemoteUserPassword(target, username, newPassword):
    # Construct and execute command to remotely update user password
    cmd = "ssh -n " + target + " /usr/sbin/usermod -p '" + newPassword + "' " + username
    executeCommandWithEcho(cmd)


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


def printHelpMessage():
    print """
Usage: ./migrate.py [OPTION]... [DESTINATION] [USER LIST FILE]
Transfer/update user accounts specified in USER LIST FILE to the DESTINATION computer and delete users at the destination that no longer exist locally. The USER LIST FILE must contain a new-line separated list of usernames. Changed passwords are the only attribute that will be propagated and this will occur regardless of whether that user is in the USER LIST FILE.

  --help                      display this message and quit.
  -u, --unlisted-get-deleted  removing a user from USER LIST FILE will cause it to be deleted at DESTINATION.
  -v, --verbose               provide more information about actions taken.
  -c, --check-users           check that all users can be categorized and then quit.

Example:
    ./migrate.py root@192.168.1.257 bunch_of_users.txt
"""


# Return a list of all command-line arguments that start with a dash.
def processCommandLineOptions():
    # Isolate argument strings.
    optionArguments = []
    for item in sys.argv[1:]:
        if item[0] == '-':
            optionArguments.append(item)

    # Process command-line options.
    options = {}
    options['unlistedGetDeletedFlag'] = False
    options['verbose'] = False
    options['checkUsers'] = False
    for option in optionArguments:
        if option == '-u' or option == '--unlisted-get-deleted':
            options['unlistedGetDeletedFlag'] = True
        elif option == '-v' or option == '--verbose':
            options['verboseOutput'] = True
        elif option == '-c' or option == '--check-users':
            options['checkUsers'] = True
        else:  # If --help or any unrecognized option
            printHelpMessage()
            exit(EXIT_CODE_HELP_MESSAGE)


    return len(optionArguments), options


# Create an ordered set of unique elements (the Python "sets" module is deprecated).
def createUnionOfLists(listOfLists):
    itemDictionary = {}
    for eachList in listOfLists:
        for item in eachList:
            itemDictionary[item] = None  # Create dictionary key (value is unimportant)
    return itemDictionary.keys()


def main():
    # TO DO: Check that another instance of the program isn't already running.
    # pid_file = 'program.pid'
    # fp = open(pid_file, 'w')
    # try:
    #     fcntl.lockf(fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # except IOError:
    #     # another instance is running
    #     sys.exit(1)

    # Get command line options.
    optionCount, options = processCommandLineOptions()

    # Check that the user has provided the minimum number of arguments.
    if len(sys.argv) - optionCount < 3:
        printHelpMessage()
        exit(EXIT_CODE_TOO_FEW_ARGUMENTS)

    # Take destination and migrant list file from last two command-line arguments.
    destAddress = sys.argv[-2]
    userListFilename = sys.argv[-1]

    # Load lists of usernames and construct dictionaries of account data.
    srcUsers, srcAccountDict = getLocalUsers()
    destUsers, destAccountDict = getRemoteUsers(destAddress)
    listedUsers = textFileIntoLines(userListFilename)

    """
        ###################################################################
        ###########   CATEGORIZE USERS   ##################################
        ###################################################################
    """
    # Listed users found at source but not at destination get migrated.
    migratingUsers = [u for u in listedUsers if u in srcUsers and u not in destUsers]

    # Any users at destination and not at source should be marked for deletion.
    doomedUsers = [u for u in destUsers if u not in srcUsers]

    # Optionally mark for deletion users that exist at both ends but are no longer listed.
    if options['unlistedGetDeletedFlag']:
        doomedUsers += [u for u in destUsers if u in srcUsers and u not in listedUsers]

    # Update users that have changed their password.
    updatingUsers = [u for u in srcUsers if u in destUsers and
        srcAccountDict[u].password != destAccountDict[u].password]

    # Determine which listed users are missing, if any.
    missingUsers = [u for u in listedUsers if u not in srcUsers and u not in destUsers]

    # Analyze migrating users listed in the given text file.
    for username in listedUsers:
        # If username not found at source machine add them to list of missing users.
        if username not in srcUsers:
            missingUsers.append(username)

        # If username found at source but not at destination then copy user over.
        if username in srcUsers and username not in destUsers:
            migratingUsers.append(username)

    # Optionally check that if all users are accounted for.
    if options['checkUsers']:
        allUsers = createUnionOfLists([listedUsers, srcUsers, destUsers])
        handledUsers = createUnionOfLists([migratingUsers, doomedUsers, updatingUsers, missingUsers])
        ignoredUsers = [u for u in srcUsers if u not in listedUsers and u not in destUsers]
        if not options['unlistedGetDeletedFlag']:
            ignoredUsers += [u for u in srcUsers if u in destUsers and u not in listedUsers]
        else:
            ignoredUsers += [u for u in srcUsers if u in destUsers]
        unhandledUsers = [u for u in allUsers if u not in handledUsers and u not in ignoredUsers]
        if len(unhandledUsers) > 0:
            print "\nUSER CHECK FAILURE: The following users were not categorized: ",
            print unhandledUsers
            exit(EXIT_CODE_FOUND_UNCATEGORIZED_USERS)
        else:
            print "\nUSER CHECK SUCCESS"
            print "Migrate: " + usernameListToLimitedString(migratingUsers)
            print "Delete:  " + usernameListToLimitedString(doomedUsers)
            print "Update:  " + usernameListToLimitedString(updatingUsers)
            print "Missing: " + usernameListToLimitedString(missingUsers)
            print "Ignore:  " + usernameListToLimitedString(ignoredUsers)
            exit(EXIT_CODE_SUCCESS)

    """
        ###################################################################
        #########   PERFORM ACTIONS ON USERS     ##########################
        ###################################################################
    """
    # Migrate new users.
    failedUsers = []
    for username in migratingUsers:
        print "Migrating new user: " + username  # DEBUG
        result = addRemoteUser(destAddress, srcAccountDict[username])
        if result != 0:
            print "Migration of " + username + " failed with useradd exit status " + str(result) + "."
            migratingUsers.remove(username)
            failedUsers.append(username)

    # Delete users at destination if they have been marked for destruction.
    for username in doomedUsers:
        print "Deleting user: " + username  # DEBUG
        deleteRemoteUser(destAddress, username)

    # Update users who have changed their password.
    for username in updatingUsers:
        print "Updating password for user: " + username  # DEBUG
        updateRemoteUserPassword(destAddress, username, srcAccountDict[username].password)

    # Give a fuller accounting of user migration results.
    if options['verboseOutput']:
        print
        print "Verbose Migration Description"
        print "-----------------------------"
        print "Migrated: " + usernameListToLimitedString(migratingUsers)
        print "Deleted:  " + usernameListToLimitedString(doomedUsers)
        print "Updated:  " + usernameListToLimitedString(updatingUsers)
        print "Missing:  " + usernameListToLimitedString(missingUsers)
        print "Failed:   " + usernameListToLimitedString(failedUsers)

    # Give a one-line summary of the user migration results.
    print
    print "Migration Summary:",
    print str(len(migratingUsers)) + " migrated,",
    print str(len(doomedUsers)) + " deleted,",
    print str(len(updatingUsers)) + " updated,",
    print str(len(missingUsers)) + " missing,",
    print str(len(failedUsers)) + " failed migration."

main()
