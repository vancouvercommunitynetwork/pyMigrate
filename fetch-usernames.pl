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

if (@ARGV != 2) {
    print "Usage: ./fetch-usernames.pl [USER DATABASE] [USERNAME LIST FILE]\n\n";
    print "Given the name of a user database (minus the .pag or .dir extensions) this program ";
    print "will write a new-line separated text file listing all users with PPP access.\n\n";
    exit;
}

my $user_data = $ARGV[0];
my $output_filename = $ARGV[1];

# Open the database as a hash (dictionary).
dbmopen(%userDB, "$user_data", undef) or die("Cannot open user database: $user_data");

# Open the user list text file.
open(my $output_file, '>', $output_filename) or die "Could not write to file:'$output_filename' $!";

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
