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


from bsddb import db                   # the Berkeley db data base

filename = 'user-data'


def makeFakeDatabase():
    # Get an instance of BerkeleyDB
    userDB = db.DB()
    # Create a database with a Hash access method
    # 	There are also, B+tree and Recno access methods
    userDB.open(filename, None, db.DB_HASH, db.DB_CREATE)

    # Populate the database with tab-separated fields.
    userDB.put("srb", "0	1	2	3	4	5	6	7	8	9	10	11	12	v")
    userDB.put("user12", "0	1	2	3	4	5	6	7	8	9	10	11	12	p")
    userDB.put("user13", "0	1	2	3	4	5	6	7	8	9	10	11	12	n")

    # Close database
    userDB.close()


def dumpDatabase():
    # Open database.
    userDB = db.DB()
    userDB.open(filename, None, db.DB_HASH, db.DB_DIRTY_READ)

    # Get database cursor and print database contents.
    cursor = userDB.cursor()
    record = cursor.first()
    while record:
        username, userString = record
        user_array = userString.split('\t')
        print username, user_array[13]
        record = cursor.next()
    userDB.close()


dumpDatabase()
