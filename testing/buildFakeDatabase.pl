#!/usr/bin/env perl

my $user_data = "user-data";

# Create fake user data.
#my @user_array = ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', 'v');
#$user_array[13] = "o"

    # Record some values


# Convert fake user data to value strings that can be written to database.
#@the_data = join('	',@user_array);
#$user_string = join('	',@user_array);

#print "@user_array\n";
#print "$user_string\n";

# Create the database and file handle (userDB).
dbmopen(%userDict, "$user_data", 0666) or die("Cannot open user database: $user_data");

# Create some fake users.
$userDict{'volunteer7'} = "0	1	2	3	4	5	6	7	8	9	10	11	12	v";
$userDict{'user12'} = "0	1	2	3	4	5	6	7	8	9	10	11	12	p";
$userDict{'user13'} = "0	1	2	3	4	5	6	7	8	9	10	11	12	n";

# Write the fake user data to the database.
#$userDB{'volunteer7'} = $user_string;

dbmclose(%userDict);




