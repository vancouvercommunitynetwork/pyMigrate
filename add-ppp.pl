#!/usr/local/bin/perl

#    Copyright : (c) Copyright 1998 by Jason Currell (currell@vcn.bc.ca)
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 1, or (at your option)
#    any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

# This is where all user database files are stored:
$user_data = "/usr/local/database/user-data";
$lock_file = "/usr/local/database/lock-file";
$access_list = "/usr/local/database/access-list";
$validation_log = "/usr/local/database/validation-log";
$id_seen = "";
#         ----------------------------------------------------
#         |                                                  |
#         |  V a l i d a t e     U s e r s    P r o g r a m  |
#         |                                                  |
#         ----------------------------------------------------
# 
# This program can only be run by anyone who has their login id listed in
# the "access-list" file.  What it does is asks for a login to validate.
# The program then search's through the user database and prints out the
# users address, phone number, etc...  If they are already validated it
# says so and goes on to the next id.  If not then it asks if we want to
# validate them.  If you say yes then it adds a line to the to-be-added
# file and it also fills the validated field in the user database.


#-------------------------------------------------------------------------
#                         H a s     A c c e s s
#-------------------------------------------------------------------------
# Checks to see if the user running the validation program has validation
# access.  All validators are listed in the file $data_dir/access-list.
# If you are not listed in that file then you can't run the program.

sub has_access {
local($ACCESS);
local($validator) = 0;
local($current_line,$pass_entry,$processes_real_login);

   @pass_entry = getpwuid($<);
   unless (@pass_entry) { die "Got null password entry" }
   $processes_real_login = $pass_entry[0];
   
   open(ACCESS, "$access_list") or die "Cannot open access list: $!";
   while ($current_line = <ACCESS>) {
      chop($current_line);

      if ($processes_real_login eq $current_line) {
         $validator = 1;
      }

   }
   close(ACCESS);

   return $validator;
}

#-------------------------------------------------------------------------
#                           L o c k   D a t a b a s e
#-------------------------------------------------------------------------
sub lock_database {
# Because DBM files do not lock properly we had to hack a file locking
# scheme.  Essentially what we do is create a file called lock-file in the 
# same directory as the dbm files.  We do nothing to the dbm files until
# we lock the 'lock-file'. 
local($is_unlocked);

   open(LOCK_FILE, "> $lock_file");
   $is_unlocked = flock(LOCK_FILE, 2);

   while ($is_unlocked == 0) {
      close(LOCK_FILE);
      sleep 2;

      # Now try and unlock it one more time.
      open(LOCK_FILE, "> $lock_file");
      $is_unlocked = flock(LOCK_FILE, 2);
   }
   print(LOCK_FILE $$);
}


#-------------------------------------------------------------------------
#                         U n l o c k   D a t a b a s e
#-------------------------------------------------------------------------
sub unlock_database {
# Just unlocks lock-file and closes it.
   flock(LOCK_FILE, 8);
   close(LOCK_FILE);
}


#-------------------------------------------------------------------------
#                          G e t    L o g i n
#-------------------------------------------------------------------------
# This procedure is a loop which continually asks the user for a login
# to validate or they can enter 'q' to quit.  The loop will continue
# until it finds a record in $USERS{login id} which exists or until the
# users enters 'q'.
sub get_login {
local(%USERS);
local($data_record,$temp);
local($not_good_login) = 1;

   print("");
   while ($not_good_login) {

      print("\nPPP Service Registration\n");
      print("------------------------\n\n\n");
      print("Enter a login id or 'q' to quit: ");
      $the_login = <STDIN>;
      chop($the_login);

      # exit the program in the user enters 'q'
      if ($the_login eq 'q') {
         print("\nGood Bye...\n\n");
         exit 0;
      }

      dbmopen(%USERS, "$user_data", undef) || die("Can not open user database");
      $data_record = $USERS{$the_login};
      @data_record_array = split(/	/,$data_record);
      dbmclose(%USERS);

      if ($data_record eq "") {
         print("\nThis login does not exist in our databases.\n");
         print("\nPress <RETURN> to continue...");
         $temp = <STDIN>;
         print("");
      }
      else {
         if ($data_record_array[12] eq "") {
            print("\nThis login must be validated before PPP services can be added.\n");
            print("\nPress <RETURN> to continue...");
            $temp = <STDIN>;
            print("");
         }
         else {
            $not_good_login = 0;
         }
      }


   }
}

#-------------------------------------------------------------------------
#                           g e t      i n f o  
#-------------------------------------------------------------------------
# This procedure gets user info for $the_login from the database and
# puts it into the arrays @user_array and @user_array2.
sub get_info {
local(%USERS);
local($temp);

   dbmopen(%USERS, "$user_data", undef) || die("Can not open user database");
   $temp = $USERS{$the_login};
   @user_array = split(/	/,$temp);
   dbmclose(%USERS);
}



#-------------------------------------------------------------------------
#                         p r i n t     i n f o 
#-------------------------------------------------------------------------
# Prints out the information on the user so the validator will know
# whether or not to validate them.
sub print_info {
local($time_array,$the_date,$month,$day,$year);

   print("");
   print("\nUSER INFO FOR LOGIN ID: (",$the_login,")\n");
   @time_array = localtime($user_array[11]);
   $month = $time_array[4];
   $day = $time_array[3];
   if ($time_array[5] >= 100) {
      $year = substr($time_array[5],1);
   }
   else {
      $year = $time_array[5];
   }
 
   $month = $month + 1;
   $the_date = join('/',$month,$day,$year);
   print("Account registered on (m/d/y): ",$the_date);

   print("\n--------------------------------------");

   print("\n	Name:		",$user_array[0]);
   print("\n	Address #1:	",$user_array[2]);
   print("\n	Address #2:	",$user_array[3]);
   print("\n	City:		",$user_array[4]);
   print("\n	Province:	",$user_array[5]);
   print("\n	Postal Code:	",$user_array[6]);
   print("\n	Country:	",$user_array[7]);

   # If the user is not an Organization then print out day and
   # evening phone number.
   if ($user_array[13] eq 'n') {
      print("\n	Day Phone:	",$user_array[8]);
      print("\n	Evening Phone:	",$user_array[9]);
   }
   else {
      print("\n	Phone:		",$user_array[8]);
   }

   print("\n	Fax:		",$user_array[10]);

   # If the user is an Organization then print out the contact info.
   if ($user_array[13] eq 'y') {
      print("\n	Contact Name:	",$user_array[1]);
      print("\n	Contact Phone:	",$user_array[9]);
   }

   print("\n	GID:		",$user_array[16]);
   print("\n	Shell:		",$user_array[17]);
   if ($user_array[18] ne "") {
      print("\n	URL:		",$user_array[18],$the_login);
   }
}

#-------------------------------------------------------------------------
#                          G e t     A n s w e r
#-------------------------------------------------------------------------
# Asks the user if they want to validate and forces them to input
# either 'p' - give ppp or n - change to normal account;
sub get_answer {
   local($the_input);
   local($got_answer) = 0;
   local(@id_type) = ("Drivers License","Cheque","Care Card","Utility Bill",
	"Permanent Resident Card","BC ID","Citizenship","Passport");

   local($reg_name) = $user_array[0];
   if ($user_array[13] eq "y" || $user_array[13] eq "o") {
      $reg_name = $user_array[1]; 
   }


   print("\n\nPress \'a\' to add ");
   print("OR \'r\' to remove PPP services \nPress \'c\' to cancel:");

   while ($got_answer == 0) {
      $the_input = <STDIN>;
      chop($the_input);

      if ($the_input eq "a") {
         $got_answer = 1;
	     print("\nAcceptable Picture ID types:\n");
  	     print("(1) Phoned                       - (6) Photo ID Card\n");
         print("(2) Cheque in their name         - (7) Citizenship\n");
         print("(3) Care Card + other photoID    - (8) Passport\n");
         print("(4) Utility Bill + other photoID\n"); 
         print("(5) Permanent Resident Card\n");
         print("Enter ID type the user has presented (1-8):");

         $got_answer = 0;
         while ($got_answer == 0) {
            $the_input = <STDIN>;
            chop($the_input);
        
            if ($the_input =~ m/^[1-8]$/) {
               $got_answer=1;
               $id_seen = "$id_type[$the_input - 1]";
            }
            else {
               print("Please answer with 1-8:");
            }
         }

         print("Enter First and Last name (no middle name) on $id_seen:");
         $got_answer = 0;
         while ($got_answer == 0) {
            my $name = <STDIN>;
            chop($name);
            print("\nName on $id_seen :  $name\n");

            print("Is this correct? (y/n):");
            $the_input = <STDIN>;
            chop($the_input);

            if ($the_input eq "y") {
               $got_answer = 0;
               print("\nRegistration name:  $reg_name\n");
               print("$id_seen name:  $name\n");
               print("Do the names match (y/n)?");

               while ($got_answer == 0) {
                  $the_input = <STDIN>;
                  chop($the_input);
                  if ($the_input eq "y") {
                     $id_seen .= ":$name";
                     $got_answer = 1;
                     $the_input = "a";
                  }
                  elsif ($the_input eq "n") {
                     print("\nCANNOT GIVE PPP ACCESS: \nTell the user they must ");
                     print("re-register online, using ");
                     print("the same name as on their ID\n");
                     $the_input = "c";
                     $got_answer = 1;
                  }
                  else {
                     print("Please answer \'y\' or \'n\'\n");
                  }
               }
            }
            elsif ($the_input eq "n") {
               $the_input = "c";
               $got_answer = 1;
               return $the_input;
            }
            else {
               print("Please answer \'y\' or \'n\'\n");
            }
         }
      }
      elsif ($the_input eq "r" || $the_input eq "c") {
         $got_answer = 1;
      }
      else {
            print("Please enter 'a', 'r' or 'c'.\n");
      }
   }
   return $the_input;
}


#-------------------------------------------------------------------------
#                       A d d    L o g    E n t r y
#-------------------------------------------------------------------------
# This procedure unlocks the validation_log file and add's an entry into
# it.
sub add_log_entry {
local($the_login,$added) = @_;
local($TO_ADD,$is_unlocked,$validation_time,$pass_entry,$validator);
local(@time_array) = localtime();

   # This locks the file so that we can add to it.

   $validation_time = (Sun,Mon,Tue,Wed,Thu,Fri,Sat)[$time_array[6]];
   $validation_time .= " ".(Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec)[$time_array[4]];
   $validation_time .= " ".$time_array[3]."/".($time_array[5]+1900);
   $validation_time .= " ".$time_array[2].":".$time_array[1].":".$time_array[0];;
   @pass_entry = getpwuid($<);
   $validator = $pass_entry[0]; 

   open(TO_ADD, ">> $validation_log");
   $is_unlocked = flock(TO_ADD, 2);
   while ($is_unlocked == 0) {
      close(TO_ADD);
      sleep 2;
   
      # Now try and unlock it one more time.
      open(TO_ADD, ">> $validation_log");
      $is_unlocked = flock(TO_ADD, 2);
   }
   # Adds the login of the validator,who's validated and when,ID seen.
   print(TO_ADD $validator,":",$the_login,":",$validation_time,":",$added,":$id_seen","\n");
      
   # Unlocks the file for another process to use.
   flock(TO_ADD, 8);
   close(TO_ADD);
}


#-------------------------------------------------------------------------
#                      V a l i d a t e      U s e r
#-------------------------------------------------------------------------
# This procedure locks the database enters the 'p' or 'o' for ppp account
# unlocks the database and closes it.
sub validate_user {
local(%USERS);

   if ($user_array[13] eq "n") {
      $user_array[13] = "p";
      print("PPP services have been added to the account.\n");
   }
   elsif ($user_array[13] eq "p") {
      print("This account already has PPP services enabled.\n");
   }
   elsif ($user_array[13] eq "v") {
      print("This account already has PPP services enabled.\n");
   }
   elsif ($user_array[13] eq "y") {
      $user_array[13] = "o";
      print("PPP services have been added to the account.\n");
   }
   elsif ($user_array[13] eq "o") {
      print("This account already has PPP services enabled.\n");
   }
   elsif ($user_array[13] eq "l") {
      print("This account already has PPP services enabled.\n");
   }
   else {
      print("There is a problem with this account.  E-mail\n");
      print("sys-admin\@vcn.bc.ca and inform them of the problem.\n");
   }

   $the_data = join('	',@user_array);

   &lock_database;
   dbmopen(%USERS, "$user_data", undef) || die("Can not open user database");

   $USERS{$the_login} = $the_data;

   dbmclose(%USERS);
   &unlock_database;   

   &add_log_entry($the_login,"PPP-ADDED");
}

#-------------------------------------------------------------------------
#                      U n v a l i d a t e      U s e r
#-------------------------------------------------------------------------
# This procedure locks the database enters the 'p' or 'o' for ppp account
# unlocks the database and closes it.
sub unvalidate_user {
local(%USERS);

   if ($user_array[13] eq "n") {
      print("This account does not have PPP services yet.\n");
   }
   elsif ($user_array[13] eq "p") {
      $user_array[13] = "n";
      print("PPP services have been disabled.\n");
   }
   elsif ($user_array[13] eq "v") {
      print("This is a volunteer account contact sys-admin\@vcn.bc.ca to\n");
      print("remove PPP services from this account.\n");
   }
   elsif ($user_array[13] eq "y") {
      print("This account doesn't have PPP services yet.\n");
   }
   elsif ($user_array[13] eq "o") {
      $user_array[13] = "y";
      print("PPP services have been disabled.\n");
   }
   elsif ($user_array[13] eq "l") {
      print("This is a Langara account.  Can not remove PPP.\n");
   }
   else {
      print("There is something wrong with the account.  Contact\n");
      print("sys-admin\@vcn.bc.ca to get it fixed.\n");
   }
   $the_data = join('	',@user_array);
   &lock_database;
   dbmopen(%USERS, "$user_data", undef) || die("Can not open user database");
   $USERS{$the_login} = $the_data;
   dbmclose(%USERS);
   &unlock_database;   
   &add_log_entry($the_login,"PPP-REMOVED");
}

sub time_check {
   local(@curr_time) = localtime();
  
   if ($curr_time[6] == 0 || $curr_time[6] == 6) {
      print("\nValidation is only available Mon - Fri, 8AM - 5PM\n");
      return 0;
   } 
   elsif ($curr_time[2] < 8 || $curr_time[2] > 21) {
      print("\nValidation is only available Mon - Fri, 8AM - 5PM\n");
      return 0;
   }
   else {
      return 1;
   }
   return 0;
}

#-------------------------------------------------------------------------
#                         M a i n    P r o g r a m
#-------------------------------------------------------------------------
if (&has_access == 0) {
   print("\n\nSorry, validation access denied.\n\n");
   exit 0;
}

# Loop ends with an exit statement &get_login.  When the user is asked to
# enter another login id.  If they enter q instead then the program exits.
while (1) {

   if(&time_check == 0) {
      exit 0; 
   }

   # Runs a continuous loop which get's $the_login from the user.  If the
   # login doesn't exist then it will ask for another.  If the user enters
   # 'q' instead of a login id, the program exits.
   &get_login;

   # Gets the info for $the_login
   &get_info;

   # Print's $the_login's information
   &print_info;

   # Ask if they want to validate this user.
   $answer = &get_answer;
   if ($answer eq "a") {
      &validate_user;
	  if ($the_login) {
		$ENV{'PATH'} = '/bin:/usr/bin';
		delete @ENV{'IFS', 'CDPATH', 'ENV', 'BASH_ENV'};
		system "/usr/local/vcn/block-send/unblock-send", $the_login;
	  }
	  #print "Dialup Access will take effect after 6pm.\n";
	  exit 0;
   }
   elsif ($answer eq "r") {
      &unvalidate_user;
	  if ($the_login) {
		$ENV{'PATH'} = '/bin:/usr/bin';
		delete @ENV{'IFS', 'CDPATH', 'ENV', 'BASH_ENV'};
		system "/usr/local/vcn/block-send/block-send", $the_login;
	  }
	  exit 0;
   }
   elsif ($answer eq "c") {
      print("Cancelled\n");
	  exit 0;
   }
   else {
      print("!!! Invalid option.  Nothing has been done.");
   }

   #print("Press <RETURN> to continue...");
   #$continue_var = <STDIN>;
   
   # Clear the id_seen variable
   $id_seen = "";
}
