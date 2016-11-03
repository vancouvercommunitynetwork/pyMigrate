#!/usr/bin/env perl

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

use Fcntl ':flock'; # Import LOCK_* constants

# This is where user database files and lock file are stored.
$user_data = "/usr/local/database/user-data";
$database_lock_file = "/usr/local/database/lock-file";
$pymigrate_lock_file = "/var/run/vcn_user_data_migration.lck";

# Check that the program received the correct number of command-line arguments.
if (@ARGV != 1) {
    print "Usage: ./fetch-usernames.pl [USERNAME LIST FILE]\n\n";
    print "This script will open $user_data and create a new-line separated text file ";
    print "listing all users with PPP access. It will not run simultaneously with another ";
    print "instance of itself or an instance of pyMigrate (migrate.py)\n\n";
    print "Example:\n";
    print "    ./fetch-usernames.pl list_of_users.txt\n";
    exit;
}

# Take the user text file path from the command-line arguments.
my $text_file_path = $ARGV[0];

# Lock the user database and lock out simultaneous execution with pyMigrate.
open(pymigrate_lock_handle, "> $pymigrate_lock_file");
$pymigrate_not_running = flock(pymigrate_lock_handle, LOCK_EX | LOCK_NB);
open(database_lock_handle, "> /usr/local/database/lock-file");
$database_unlocked = flock(database_lock_handle, LOCK_EX | LOCK_NB);
if ($database_unlocked == 0 or $pymigrate_not_running == 0) {
    close(pymigrate_lock_handle);
    close(database_lock_handle);
    if ($pymigrate_not_running == 0) {
        print "ERROR: Unable to run while pyMigrate execution lock is active. Another ";
        print "instance of this program or an instance of migrate.py is currently running.\n";
    }
    if ($database_unlocked == 0) {
        print "ERROR: Unable to lock user database for exclusive access.\n";
    }
    exit;
}
print(pymigrate_lock_handle $$);
print(database_lock_handle $$);

# Open the database as a hash (dictionary).
dbmopen(%userDB, "$user_data", undef) or die("Cannot open user database: $user_data");

# Open the user list text file.
open(my $output_file, '>', $text_file_path) or die "Could not write to file:'$output_filename' $!";

# For each (key, value) pair in the database.
foreach $key (keys %userDB) {
    # Extract the user type from the dictionary.
    $user_string = $userDB{$key};
    @user_array = split(/	/,$user_string);
    $user_type = $user_array[13];

    # Add username to text file if they are of type o, p or v.
    if ($user_type eq "o" or $user_type eq "p" or $user_type eq "v") {
        print $output_file "$key\n";
    }
}

# Close the user list text file and close the database.
close $output_file;
dbmclose(%userDB);

# Unlock the user list text file and user database.
flock(pymigrate_lock_handle, LOCK_UN);
close(pymigrate_lock_handle);
flock(database_lock_handle, LOCK_UN);
close(database_lock_handle);
