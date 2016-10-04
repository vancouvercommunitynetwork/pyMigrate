#!/usr/bin/env python
#
# TO DO
# Make it test the ssh connection and halt if unable to connect. You'll want something like:
#   ssh -o BatchMode=yes root2@192.168.20.45 exit
#   but you'll also need to add timeout functionality so it won't sit forever if the destination doesn't exist.
# Change the program to prepend root@ to the destination address if no user is given (then update the helper scripts).
# Capture the error that comes from lacking root authority to create the lock file.

# Error Modes to Cover:
#   Bad connection:
#      Host is reachable but SSH server isn't running.
#      No route to host: a remote machine can't be found on the network.
#      No SSH pre-authorization for remote machine.
#      SSH pre-authorization for remote machine exists but lacks root privilege.
#   Insufficient local privilege. No root access on local machine.
#   Bad input file:
#       The specified file doesn't exist.
#       The specified file is empty.
#       The specified file is binary and possibly huge.

# Source Code Terminology
#   Entry: A line from /etc/passwd or /etc/shadow containing. These contain fields separated by colons.
#   Field: An item in a line from /etc/passwd or /etc/shadow.
#   User: Synonym for username.
#   Account: A data structure representing a user's data with attributes like UID and password.
#   Source: The machine that users are migrating from (currently the local machine).
#   Destination: The machine that users are migrating to (always a remote host).
#   Listed users: The users whose usernames are listed in the text file given to this program.

# Intentions
#   The program should not alter system accounts (1001 < uid < 60000).
#   The program should not alter user accounts on the machine it is run from.
#   The program should not alter the text file it is given (the one listing users to be migrated).

# Performance Specs
#   0.4 secs to process 100 users when no actions were necessary.
#   13m17s to migrate 1000 users (avg 0.8secs/user).
#   0.6 secs to process 1000 users when no actions were necessary.
#   21m27s to delete 1000 users (avg 1.3secs/user).


import commands
import fcntl
import subprocess
import sys

# Constants
LOWEST_USER_ID, HIGHEST_USER_ID = 1001, 60000  # Inclusive range of effected users.
MOST_USERNAMES_TO_LIST = 5  # No message should dump more than this many usernames.
EXIT_CODE_SUCCESS = 0
EXIT_CODE_FAILURE_TO_OPEN_LOCAL_FILE = 1
EXIT_CODE_TOO_FEW_ARGUMENTS = 2
EXIT_CODE_HELP_MESSAGE = 3
EXIT_CODE_FOUND_UNCATEGORIZED_USERS = 4

# File handle for locking out multiple running instances (fcntl requires this to be global).
lockFile = None


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
        if LOWEST_USER_ID <= int(account.uid) <= HIGHEST_USER_ID:  # Ignore irregular users.
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
    cmd = "ssh -n " + target + " /usr/sbin/useradd -p '\"" + \
          account.password + "\"' -u " + account.uid + " -g " + account.gid
    if account.gecos != "":
        cmd += " -c '\"" + account.gecos + "\"'"
    cmd += " -d /home -M -s /usr/sbin/nologin -K MAIL_DIR=/dev/null " + account.username
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
Usage: ./migrate.py [OPTIONS]... [DESTINATION] [USER LIST FILE]

Transfer/update user accounts specified in USER LIST FILE to the DESTINATION computer and delete users at the destination that no longer exist locally. The USER LIST FILE must contain a new-line separated list of usernames. Changed passwords are the only attribute that will be propagated and this will occur regardless of whether that user is in the USER LIST FILE.

  --help                      display this message and quit
  -u, --unlisted-get-deleted  removing a user from USER LIST FILE will delete it at DESTINATION
  -v, --verbose               provide more information about actions taken
  -s, --simulate              simulate running the program, but perform no actions

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

    # Set default option values.
    options = {
        'unlistedGetDeleted': False,
        'verbose': False,
        'simulate': False
    }

    # Process command-line options.
    for option in optionArguments:
        if option == '-u' or option == '--unlisted-get-deleted':
            options['unlistedGetDeleted'] = True
        elif option == '-v' or option == '--verbose':
            options['verbose'] = True
        elif option == '-s' or option == '--simulate':
            options['simulate'] = True
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


def lockExecution():
    global lockFile
    LOCK_FILE = "/var/run/vcn_user_data_migration.lck"
    lockFile = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lockFile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print "ERROR: Another instance is already running."
        sys.exit(1)


"""
    ###################################################################
    ###########   START OF MAIN   #####################################
    ###################################################################
"""


def main():
    # Prevent another instance of the program from running simultaneously.
    lockExecution()

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
    if options['unlistedGetDeleted']:
        doomedUsers += [u for u in destUsers if u in srcUsers and u not in listedUsers]

    # Update users that have changed their password.
    updatingUsers = [u for u in srcUsers if u in destUsers and u not in doomedUsers and
                     srcAccountDict[u].password != destAccountDict[u].password]

    # Determine which listed users are missing, if any.
    missingUsers = [u for u in listedUsers if u not in srcUsers and u not in destUsers]

    # Optionally run the program in simulation mode.
    if options['simulate']:
        # Determine all the users for whom no action is taken.
        ignoredUsers = [u for u in srcUsers if u not in listedUsers and u not in destUsers]
        if not options['unlistedGetDeleted']:
            ignoredUsers += [u for u in srcUsers if u not in listedUsers and u in destUsers and u not in updatingUsers]
        ignoredUsers += [u for u in listedUsers if u in srcUsers and u in destUsers and u not in updatingUsers]

        # Show simulation results and quit.
        print "Simulated User Categorization"
        print "-----------------------------"
        print "  Migrate:   " + usernameListToLimitedString(migratingUsers)
        print "  Delete:    " + usernameListToLimitedString(doomedUsers)
        print "  Update:    " + usernameListToLimitedString(updatingUsers)
        print "  Missing:   " + usernameListToLimitedString(missingUsers)
        print "  Ignore:    " + usernameListToLimitedString(ignoredUsers)
        exit(EXIT_CODE_SUCCESS)

    """
        ###################################################################
        #########   PERFORM ACTIONS ON USERS     ##########################
        ###################################################################
    """
    # Migrate new users.
    failedUsers = []
    for username in migratingUsers:
        if options['verbose']:
            print "Migrating new user: " + username
        result = addRemoteUser(destAddress, srcAccountDict[username])
        if result != 0:
            print "Migration of " + username + " failed with useradd exit status " + str(result) + "."
            migratingUsers.remove(username)
            failedUsers.append(username)

    # Delete users at destination if they have been marked for destruction.
    for username in doomedUsers:
        if options['verbose']:
            print "Deleting user: " + username
        deleteRemoteUser(destAddress, username)

    # Update users who have changed their password.
    for username in updatingUsers:
        if options['verbose']:
            print "Updating password for user: " + username
        updateRemoteUserPassword(destAddress, username, srcAccountDict[username].password)

    # Give a fuller accounting of user migration results.
    if options['verbose']:
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
