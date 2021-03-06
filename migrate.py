#!/usr/bin/env python

#    Copyright : (c) Copyright 2016 by Scott Bishop (srb@vcn.bc.ca)
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

# WARNING
# As part of its normal operation, this program creates, modifies and deletes
# the linux user accounts of the destination machine.

# OPERATION
# This program takes a list of usernames and synchronizes their Linux user accounts at
# a destination machine. The program operates by the following rules:
#   (1) If a user is on the list then they will be migrated if they haven't already been.
#   (2) If a user is deleted from the source then they will be deleted at the destination, whether
#       they're on the list or not.
#   (3) If a user has changed their password, user ID or full name (gecos field) then those
#       changes will be copied to the destination, whether they're on the list or not.
#   (4) If the --unlisted-get-deleted option is used then removing a user from the list will delete
#       them at the destination.
#   (5) No local accounts or system accounts (based on UID) will be altered.

# PERFORMANCE
# This program uses hashing to avoid any nested loops and operates with O(n) efficiency
# for n users. As a rule of thumb the program will require one second per 60,000 user
# accounts analyzed, plus one second per action taken (account migrating, deleting or
# updating). Each action is performed with an individual ssh call to usermod, useradd or
# deluser.

# PORTABILITY
# To improve portability this program consists of only one file and uses only the common
# pre-installed Python libraries rather than libraries such as Paramiko or Fabric.

# Source Code Terminology
#   Entry: A line from /etc/passwd or /etc/shadow. These contain fields separated by colons.
#   Field: An item in a line from /etc/passwd or /etc/shadow.
#   User: Synonym for username.
#   Account: A data structure representing a user's data with attributes like UID and password.
#   Source: The machine that users are migrating from (currently the local machine).
#   Destination: The machine that users are migrating to (always a remote host).
#   Listed users: The users whose usernames are listed in the text file given to this program.

import commands
import fcntl
import subprocess
import sys
import datetime
import syslog

# Constants
DEFAULT_REMOTE_BACKUP_DIR = '/mnt/pymigrate/backups'
DEFAULT_SSH_PORT = 22
LOCK_FILE = "/var/run/vcn_user_data_migration.lck"
LOWEST_USER_ID, HIGHEST_USER_ID = 1000, 60000  # Inclusive range of effected users.
MOST_USERNAMES_TO_LIST = 5  # No message should dump more than this many usernames.

# Console return values
EXIT_CODE_SUCCESS = 0  # Program ran without problems.
EXIT_CODE_FAILURE_TO_OPEN_LOCAL_FILE = 1  # Program failed to open a local file.
EXIT_CODE_TOO_FEW_ARGUMENTS = 2  # Program was not given the minimum number of arguments.
EXIT_CODE_HELP_MESSAGE = 3  # Program showed help and quit without taking any actions.
EXIT_CODE_FOUND_UNCATEGORIZED_USERS = 4  # Program choked on a user it couldn't categorize.
EXIT_CODE_UNABLE_TO_BACKUP = 5  # Program failed to create backups of passwd and shadow.
EXIT_CODE_INSTANCE_ALREADY_RUNNING = 6  # Program quit because multiple instances aren't allowed.
EXIT_CODE_NOT_ROOT = 7  # Program wasn't run with root authority.
EXIT_CODE_SUB_UID_MAXED_OUT = 8  # Destination may have reached the limit of subordinate UIDs.
EXIT_CODE_UNABLE_TO_CONNECT = 9  # Destination was unreachable.

# Global variables
lockFile = None  # File handle for locking out multiple running instances (fcntl requires this to be global).
options = None  # A dictionary of command-line option values.


# An object to represent the attributes of a Linux user account.
class Account:
    # Construct an Account object from an /etc/passwd entry.
    def __init__(self, passwdEntry):
        # Pull the needed fields from the entries. The field ordering in passwd and shadow are:
        #    username:password:userID:groupID:gecos:homeDir:shell
        #    username:password:lastchanged:minimum:maximum:warn:inactive:expire
        [self.username, self.password, self.uid, self.gid, self.gecos,
            self.homeDir, self.shell] = passwdEntry.split(':')


# Create a new user account at a remote machine.
# NOTE: home directory will be forced to /home and shell to /usr/sbin/nologin
def addRemoteUser(target, account):
    # Construct and execute command to remotely add user.
    cmd = "ssh -p" + str(options['port']) + " -n " + target + " /usr/sbin/useradd -p \\''" + account.password + \
          "'\\' -u " + account.uid + " -g " + account.gid + \
          " -c \\''" + account.gecos + "'\\'" + \
          " -d /home -M -s /usr/sbin/nologin -K MAIL_DIR=/dev/null " + account.username
    status = executeCommand(cmd)
    return status


# Open and close the lock file to test for root privilege.
def checkForRootPrivilege():
    global LOCK_FILE

    try:
        testFile = open(LOCK_FILE, 'w')
        testFile.close()
    except IOError as e:
        if e[0] == 13:
            logExit(syslog.LOG_ERR, "Program must be run with root authority.",
                    EXIT_CODE_NOT_ROOT)
        else:
            logExit(syslog.LOG_ERR, "Creating " + LOCK_FILE + " triggered:\n" + str(e))


# Convert /etc/passwd and /etc/shadow entries into a list of usernames and dictionary of account info.
def constructUserDataSet(passwdEntries, shadowEntries):
    # Construct user list and preliminary user dictionary from passwd file entries.
    users, userAccountDict = [], {}
    printVerbose("Constructing list of user accounts.")
    for passwdEntry in passwdEntries:
        account = Account(passwdEntry)
        if LOWEST_USER_ID <= int(account.uid) <= HIGHEST_USER_ID:  # Ignore irregular users.
            users.append(account.username)
            userAccountDict[account.username] = account

    # Replace account password field placeholders with actual passwords from /etc/shadow entries.
    printVerbose("Reading user passwords into account data.")
    for shadowEntry in shadowEntries:
        shadowFields = shadowEntry.split(':')
        username, shadowPassword = shadowFields[0], shadowFields[1]
        if username in userAccountDict:
            userAccountDict[username].password = shadowPassword

    return users, userAccountDict


# Create a combined list with no duplicate members (the Python "sets" module is deprecated).
def createUnionOfLists(listOfLists):
    itemDictionary = {}
    for eachList in listOfLists:
        for item in eachList:
            itemDictionary[item] = None  # Create a key (the value is irrelevant).
    return itemDictionary.keys()


# Delete a user account at a remote machine.
def deleteRemoteUser(target, username):
    # Construct and execute command to remotely delete user.
    cmd = 'ssh -p' + str(options['port']) + ' -n ' + target + ' /usr/sbin/deluser -quiet ' + username
    executeCommand(cmd)


# Execute a console command and print results.
def executeCommand(command):
    status, output = commands.getstatusoutput(command)
    if status != 0:
        printLoud("WARNING: Non-zero exit code on command: " + command + "\n  " + output)
    return status


# Get a list of usernames and a dictionary of user data from local machine.
def getLocalUsers():
    return getUsers()


# Get a list of usernames and a dictionary of user data from remote machine.
def getRemoteUsers(target):
    return getUsers(target)


# Read /etc/passwd and /etc/shadow files to produce a list of the non-system usernames
# present on a system and a dictionary of Accounts keyed by username.
def getUsers(target=None):
    global options

    # Get file handles.
    if target is None:  # If no target was given then open local files.
        try:
            passwdFile = open('/etc/passwd', 'r')
            shadowFile = open('/etc/shadow', 'r')

        except IOError as e:
            logExit(syslog.LOG_ERR, "Unable to open local file.\n" +
                    str(e), EXIT_CODE_FAILURE_TO_OPEN_LOCAL_FILE)

    else:  # If a remote target was given then open remote files.
        passwdFile = subprocess.Popen(['ssh', '-p', str(options['port']), target, 'cat', '/etc/passwd'], stdout=subprocess.PIPE).stdout
        shadowFile = subprocess.Popen(['ssh', '-p', str(options['port']), target, 'cat', '/etc/shadow'], stdout=subprocess.PIPE).stdout

    # Split text files into lists of lines.
    passwdEntries = passwdFile.read().splitlines()
    shadowEntries = shadowFile.read().splitlines()

    return constructUserDataSet(passwdEntries, shadowEntries)


# Lock out execution of multiple instances.
def lockExecution():
    global lockFile, LOCK_FILE

    try:
        lockFile = open(LOCK_FILE, 'w')
        fcntl.flock(lockFile, fcntl.LOCK_EX | fcntl.LOCK_NB)

    except IOError as e:
        if e[0] == 11:
            logExit(syslog.LOG_ERR, "Execution has been locked out by another program or " +
                    "another instance of this program.", EXIT_CODE_INSTANCE_ALREADY_RUNNING)
        else:
            logExit(syslog.LOG_ERR, "Locking " + LOCK_FILE + " triggered:\n" + str(e))


# Log a message to syslog and quit. Exiting with a single message ensures that the program will never flood the syslog
# with multi-line messages that syslog can't trim to 'blah blah blah' happened 8000 times.
def logExit(priority, msg, exitCode):
    if not options['simulate']:
        syslog.syslog(priority, "Exiting because: " + msg)

    printLoud(msg)

    exit(exitCode)


# Log a message to syslog and print it to stdout unless in --quiet mode. This should be used for messages that
# won't occur every single time the program is run as that could cause syslog flooding.
def logMessage(priority, msg):
    assert priority == syslog.LOG_INFO or priority == syslog.LOG_WARNING
    if not options['simulate']:
        syslog.syslog(priority, msg)

    printLoud(msg)


def printHelpMessage():
    print """
Usage: ./migrate.py [OPTIONS]... [DESTINATION] [USER LIST FILE]

Transfer/update user accounts specified in USER LIST FILE to the DESTINATION computer and delete users at the destination that no longer exist locally. The USER LIST FILE must contain a new-line separated list of usernames. Changed passwords are the only attribute that will be propagated and this will occur regardless of whether that user is in the USER LIST FILE.

  --help                      display this message and quit
  -u, --unlisted-get-deleted  removing a user from USER LIST FILE will delete it at DESTINATION
  -v, --verbose               provide more information about actions taken
  -s, --simulate              simulate running the program, but perform no actions
  -q, --quiet                 run program without output to console
  -b, --backup-dir [PATH]     set the remote directory to store backups of /etc/shadow and /etc/passwd, by default it is /mnt/pymigrate/backups
  -p, --port [PORT NUMBER]    specify a different SSH port at the destination

Example:
    ./migrate.py root@192.168.1.257 list_of_users.txt
"""


# Print a message to console if the --quiet option is turned off.
def printLoud(msg):
    if not options['quiet']:
        print msg


# Print a message to console if the --verbose option is turn on (--quiet overrides this).
def printVerbose(msg):
    if options['verbose'] and not options['quiet']:
        print msg


# Process the command-line arguments and return a count of how many were consumed.
def processCommandLineOptions():
    global options

    # Isolate argument strings.
    optionArguments = []
    for item in sys.argv[1:]:
        if item[0] == '-':
            optionArguments.append(item)

    # Set default option values.
    options = {
        'unlistedGetDeleted': False,
        'verbose': False,
        'simulate': False,
        'quiet': False,
        'backupDir': DEFAULT_REMOTE_BACKUP_DIR,
        'port': DEFAULT_SSH_PORT
    }

    # Process command-line options.
    argsConsumed = 0
    for i in range(1, len(sys.argv) - 1):
        if sys.argv[i] == '--help':
            argsConsumed += 1
            printHelpMessage()
            exit(EXIT_CODE_HELP_MESSAGE)
        elif sys.argv[i] == '-u' or sys.argv[i] == '--unlisted-get-deleted':
            argsConsumed += 1
            options['unlistedGetDeleted'] = True
        elif sys.argv[i] == '-v' or sys.argv[i] == '--verbose':
            argsConsumed += 1
            options['verbose'] = True
        elif sys.argv[i] == '-s' or sys.argv[i] == '--simulate':
            argsConsumed += 1
            options['simulate'] = True
        elif sys.argv[i] == '-q' or sys.argv[i] == '--quiet':
            argsConsumed += 1
            options['quiet'] = True
        elif sys.argv[i] == '-b' or sys.argv[i] == '--backup-dir':
            argsConsumed += 2
            options['backupDir'] = sys.argv[i + 1]
        elif sys.argv[i] == '-p' or sys.argv[i] == '--port':
            argsConsumed += 2
            options['port'] = sys.argv[i + 1]

    return argsConsumed


# Attempt to open a local text file and convert to a list of lines.
def textFileIntoLines(filePath):
    try:
        with open(filePath, 'r') as textFile:
            textLines = textFile.read().splitlines()
    except IOError as e:
        logExit(syslog.LOG_ERR, "Unable to open local file" + filePath +
                ". " + str(e), EXIT_CODE_FAILURE_TO_OPEN_LOCAL_FILE)

    return textLines


# Propagate password, UID and gecos fields from a local account to the remote of same username.
def updateRemoteUser(target, localUserAcct):
    password = localUserAcct.password
    uid = localUserAcct.uid
    gecos = localUserAcct.gecos
    username = localUserAcct.username
    # Construct and execute command to remotely update user password, UID and gecos field.
    cmd = "ssh -p " + str(options['port']) + " -n " + target + " /usr/sbin/usermod -p \\''" + \
          password + "'\\' -u " + str(uid) + " -c \\''" + gecos + "'\\' " + username
    executeCommand(cmd)


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


"""
    ###################################################################
    ###########   START OF MAIN   #####################################
    ###################################################################
"""


def main():
    global options

    # Count and process the command-line options.
    optionCount = processCommandLineOptions()

    # Check that the user has provided the minimum number of arguments.
    if len(sys.argv) - optionCount < 3:
        printHelpMessage()
        exit(EXIT_CODE_TOO_FEW_ARGUMENTS)

    # Test that program is being run by a super user.
    checkForRootPrivilege()

    # Prevent two instances of the program from running simultaneously.
    lockExecution()

    # Take destination and migrant list file from last two command-line arguments.
    destAddress = sys.argv[-2]
    userListFilename = sys.argv[-1]

    # Test remote connection.
    command = "ssh -p " + str(options['port']) + " -o BatchMode=yes " + destAddress + " exit"
    status, output = commands.getstatusoutput(command)
    if status != 0:
        logExit(syslog.LOG_ERR, output, EXIT_CODE_UNABLE_TO_CONNECT)

    # Load lists of usernames and construct dictionaries of account data.
    listedUsers = textFileIntoLines(userListFilename)
    printVerbose("Loading local users...")
    srcUsers, srcAccountDict = getLocalUsers()
    printVerbose("Loading remote users...")
    destUsers, destAccountDict = getRemoteUsers(destAddress)

    """
        ###################################################################
        ###########   CATEGORIZE USERS   ##################################
        ###################################################################
    """
    # Construct a dictionary of the listed users to use as a hash table.
    listedDict = {}
    for userName in listedUsers:
        listedDict[userName] = True

    # Construct a list of all unique usernames.
    allUsers = createUnionOfLists([listedUsers, srcUsers, destUsers])

    # Categorize users.
    printVerbose("Categorizing users.")
    migratingUsers, doomedUsers, updatingUsers = [], [], []

    for userName in allUsers:
        # Listed users found at source but not at destination get migrated.
        if userName in listedDict and userName in srcAccountDict and userName not in destAccountDict:
            migratingUsers.append(userName)

        # Any users at destination and not at source should be marked for deletion.
        if userName in destAccountDict:
            if userName not in srcAccountDict:
                doomedUsers.append(userName)

            # Optionally mark for deletion users that exist at both ends but are no longer listed.
            elif options['unlistedGetDeleted'] and userName in destAccountDict and userName not in listedDict:
                doomedUsers.append(userName)

        # Update users that have changed their password, UID or full name (gecos).
        if userName in srcAccountDict and userName in destAccountDict:
            if srcAccountDict[userName].password != destAccountDict[userName].password or \
               srcAccountDict[userName].uid != destAccountDict[userName].uid or \
               srcAccountDict[userName].gecos != destAccountDict[userName].gecos:
                updatingUsers.append(userName)

    # Determine missing users if that information will be shown.
    missingUsers = []
    if options['verbose'] or options['simulate']:
        printLoud("Checking for listed users that are missing from source machine.")
        for userName in listedUsers:
            if userName not in srcAccountDict:
                missingUsers.append(userName)

    # Optionally run the program in simulation mode.
    if options['simulate']:
        printLoud("Determining users that aren't being changed (ignored users).")
        # Determine which users are unchanged. Start with the set of all users.
        allUsersDict = {}
        for userName in allUsers:
            allUsersDict[userName] = True

        # Mark all changed users
        for userName in migratingUsers:
            allUsersDict[userName] = False
        for userName in doomedUsers:
            allUsersDict[userName] = False
        for userName in updatingUsers:
            allUsersDict[userName] = False

        # Ignored users = all users - changed users.
        ignoredUsers = []
        for userName in allUsersDict.keys():
            if allUsersDict[userName]:
                ignoredUsers.append(userName)

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
    # Check if there are any actions to be performed.
    if not (migratingUsers or doomedUsers or updatingUsers):
        printLoud("No user changes need to be made.")
    else:
        # Backup the user files before making changes.
        printLoud("Backing up passwd and shadow to " + DEFAULT_REMOTE_BACKUP_DIR)

        # Create the backup directory at destination machine.
        executeCommand('ssh -p ' + str(options['port']) + ' -n ' + destAddress + ' mkdir -p ' + options['backupDir'])

        # Construct a filename prefix for backup files.
        timeStamp = datetime.datetime.now().strftime('%Y-%m-%d-%Hh-%Mm-%Ss')
        prefix = options['backupDir'] + '/' + 'backup_' + timeStamp

        # Attempt to backup files and quit the program if unable to.
        if executeCommand('ssh -p ' + str(options['port']) + ' -n ' + destAddress + ' cp /etc/passwd ' + prefix + '_passwd'):
            logExit(syslog.LOG_ERR, "Unable to create remote backup of /etc/passwd file.",
                    EXIT_CODE_UNABLE_TO_BACKUP)
        if executeCommand('ssh -p ' + str(options['port']) + ' -n ' + destAddress + ' cp /etc/shadow ' + prefix + '_shadow'):
            logExit(syslog.LOG_ERR, "Unable to create remote backup of /etc/shadow file.",
                    EXIT_CODE_UNABLE_TO_BACKUP)

        # Migrate new users.
        if migratingUsers:
            printLoud("Moving new users.")
        failedUsers = []
        for username in migratingUsers:
            printVerbose("    Migrating user: " + username)
            result = addRemoteUser(destAddress, srcAccountDict[username])
            # Keep track of any users that fail to migrate.
            if result != 0:
                migratingUsers.remove(username)
                failedUsers.append(username)

        # Delete users at destination if they have been marked for destruction.
        if doomedUsers:
            printLoud("Deleting users.")
        for username in doomedUsers:
            printVerbose("    Deleting user: " + username)
            deleteRemoteUser(destAddress, username)

        # Update users who have changed their password.
        if updatingUsers:
            printLoud("Updating user accounts.")
        for username in updatingUsers:
            printVerbose("    Updating user: " + username)
            updateRemoteUser(destAddress, srcAccountDict[username])

        printLoud("The following summary will be recorded in syslog:")
        if migratingUsers:
            logMessage(syslog.LOG_INFO, "Migrated users: " + usernameListToLimitedString(migratingUsers))
        if doomedUsers:
            logMessage(syslog.LOG_INFO, "Deleted users: " + usernameListToLimitedString(doomedUsers))
        if updatingUsers:
            logMessage(syslog.LOG_INFO, "Updated users: " + usernameListToLimitedString(updatingUsers))
        if failedUsers:
            logMessage(syslog.LOG_WARNING, "Failed migrations: " +
                       usernameListToLimitedString(failedUsers) + ". Maybe their group wasn't " +
                       "found at destination.")

    if missingUsers:
        printLoud("Couldn't find users: " + usernameListToLimitedString(missingUsers))

main()
