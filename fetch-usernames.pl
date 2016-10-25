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


my $user_data = "user-data.junk";
my $output_filename = 'userList.txt';

# Open the database.
dbmopen(%userDB, "$user_data", 0666) or die("Cannot open user database: $user_data");

# Open the user list text file.
open(my $outfile, '>', $output_filename) or die "Could not write to file:'$output_filename' $!";

# For each (key, value) pair in the database.
foreach $key (keys %userDB) {
    print $db{$key};
#    split the value by tabs into an array of fields.
#    if field #13 of value is 'p', 'v', 'o' or 'l'
#    then print the username to the output file
#  EXAMPLE OF ACCESSING THE VALUE: delete $db{$key};

}

# Close the user list text file and the user database.
close $outfile;
dbmclose(%userDB);


##########################################################
# COPYPASTA GARBAGE                                      #
##########################################################

#sub get_info {
##my %hash_handle2;
#local($temp);
#    print "Opening database file $user_data\n";
#    dbmopen(%hash_handle, "$user_data", undef) || die("Cannot open user database: $user_data");
#    $temp = $hash_handle{$the_login};
#    @user_array = split(/	/,$temp);
#    dbmclose(%hash_handle);
#}
#
##sub add_entry {
##
##}
#
#&get_info;
#print "Data: $user_array\n";
#
#
##use strict;
##use warnings;
#
#my $output_filename = 'report.txt';
#open(my $outfile, '>', $output_filename) or die "Could not write to file:'$output_filename' $!";
#print $outfile "My dfgergergnerated by perl\n";
#print $outfile "My dfgergergnerated by perl\n";
#close $outfile;
#print "done\n";
#
#
##use strict ;
##use BerkeleyDB ;
#
#    dbmopen(%hash_handle, "$user_data", undef) || die("Cannot open user database: $user_data");
#    my $filename = "tree" ;
#    unlink $filename ;
#    my %h ;
#    tie %h, 'BerkeleyDB::Btree',
#                -Filename   => $filename,
#                -Flags      => DB_CREATE
#      or die "Cannot open $filename: $! $BerkeleyDB::Error\n" ;
#
#    # Add a key/value pair to the file
#    $h{'Wall'} = 'Larry' ;
#    $h{'Smith'} = 'John' ;
#    $h{'mouse'} = 'mickey' ;
#    $h{'duck'}  = 'donald' ;
#
#    # Delete
#    delete $h{"duck"} ;
#
#    # Cycle through the keys printing them in order.
#    # Note it is not necessary to sort the keys as
#    # the btree will have kept them in order automatically.
#    foreach (keys %h)
#      { print "$_\n" }
#
#    untie %h ;
