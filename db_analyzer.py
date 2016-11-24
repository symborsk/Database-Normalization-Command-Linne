import sys
import sqlite3
import itertools
import copy

# References
#   1: http://stackoverflow.com/questions/10648490/removing-first-appearance-of-word-from-a-string
#       Used to get the actual table name


tables = dict()

# Method to get a database to normalize from user
def getDB():
	while True:
		# Get a filename
		print("Welcome to the Database Normalizer Program.\nPlease enter the name of the database you would like to normalize:")
		dbName = raw_input(">> ")

		# Attempt to connect to DB
		try:
			global conn
			global cursor
			conn = sqlite3.connect(dbName)
			cursor = conn.cursor()
			return
		except:
			print("Entered an invalid file name")

# Method to populate tables & schemas variables
def getInfo():
	# Get data for all tables in DB
	sql = "SELECT * FROM SQLITE_MASTER WHERE type='table'"
	cursor.execute(sql)

	# Loop over all tables to add table and schema
	for result in cursor.fetchall():
		if result[1][0:6]=="Input_":
			name = result[1].replace('Input_', "", 1) # Reference 1
			
			# Dont read the FD tables
			if name.split("_")[0].lower() == "fds":
				continue
			sql = result[4]
			cols = sql.split('(')[1].split(')')[0]
			lines = list()
			types = dict()
			for line in cols.split(','):
				lines.append(line.strip().split()[0])
				types[line.strip().split()[0]] = line.strip().split()[1]
			tables[name] = dict()
			tables[name][0] = lines
			tables[name][2] = types

# Method to populate dependancies dictionary
def getDependancies():
	for name in tables:
		# Get all dependancies
		sql = "SELECT * FROM {}".format("Input_FDs_" + name)
		cursor.execute(sql)

		# Add all dependancies
		tmpdict = dict()
		for result in cursor.fetchall():
			lhs = tuple(sorted(result[0].split(',')))
			rhs = set(sorted(result[1].split(',')))
			tmpdict[lhs] = rhs

		tables[name][1] = tmpdict

# Method to get the closure of rhs set
def getClosure(closure, lhs, dependancies):
	# Initialize the closure if necessary & determine length
	if (closure==None):
		closure = set(lhs)
	length = len(closure)

	# Loop through all LHS and see if we can append to closure
	for dep in dependancies:
		if closure.issuperset(dep) and not closure.issuperset(dependancies[dep]):
			closure = set(sorted(closure.union(dependancies[dep])))

	# Recurse if necessary
	if len(closure)==length:
		return closure
	else:
		return getClosure(closure, lhs, dependancies)

def getKeys(table):
	superkeys = list()
	# Try all possible combinations of columns to create superkeys
	for i in range(0, len(tables[table][0]), 1):
		for j in list(itertools.combinations(tables[table][0], i+1)):
			if (len(getClosure(None, j, tables[table][1]))==len(tables[table][0])):
				superkeys.append(j)

	# 1st instance in superkeys will always have min length
	minLength = len(superkeys[0])
	result = list()
	for key in superkeys:
		if len(key)==minLength:
			result.append(key)
	return result

def isSuperKey(key, dependancies, schema):
	a = getClosure(None, key, dependancies)
	return len(a)==len(schema)


# Checks if the given table is in BCNF format
def checkBCNF(dependancies, schema):
	for dep in dependancies:
		if not set(dep).issuperset(dependancies) and not isSuperKey(dep, dependancies, schema):
			return False

	return True

def getInvalidTable(decomp):
	for table in decomp:
		if not checkBCNF(decomp[table][0], decomp[table][1]):
			return table
	return -1

# Returns the first invalid FD in the table
def getInvalidFD(table, dependancies, schema):
	# Ideally we first want to remove FDs which don't impact other FDs
	for dep in dependancies:
		if not set(dep).issuperset(dependancies[dep]) and not isSuperKey(dep, dependancies, schema) and not dependancies[dep] in dependancies.keys():
			return dep, dependancies[dep]

	# Get any invalid FD
	for dep in dependancies:
		if not set(dep).issuperset(dependancies[dep]) and not isSuperKey(dep, dependancies, schema):
			return dep, dependancies[dep]

	return -1, -1

def getFDs(newschema, dependancies):
	newfds = dict()
	for dep in dependancies:
		curr = set(dep).union(dependancies[dep])
		if curr.issubset(newschema):
			newfds[tuple(copy.deepcopy(dep))] = copy.deepcopy(dependancies[dep])
	return newfds

def updateFDs(schema, dependancies):
	for dep in dependancies.keys():
		curr = set(dep).union(dependancies[dep])
		val = dependancies.pop(dep)
		if not curr.intersection(schema)==set():
			# Re add necessary parts
			dep = set(dep).intersection(schema)
			val = set(val).intersection(schema)
			if not dep==set() and not val==set():
				dependancies[tuple(dep)] = val

def decompBCNF(table):
	decomp = dict()
	decomp[table] = [copy.deepcopy(tables[table][1]), copy.deepcopy(tables[table][0])]
	
	while True:
		currTable = getInvalidTable(decomp)
		# Finished case
		if currTable==-1:
			# Handle initial table then return
			newname = table+"_"+"".join(decomp[table][1])
			decomp[newname] = decomp.pop(table)
			showDecomp(decomp)
			checkPreservation(tables[table][1], decomp)
			return 

		currFDs = decomp[currTable][0]
		currSchema = decomp[currTable][1]

		lhs, rhs = getInvalidFD(currTable, currFDs, currSchema)
		newschema = set(lhs).union(rhs)
		currSchema = set(currSchema).difference(rhs)

		newfds = getFDs(newschema, currFDs)
		updateFDs(currSchema, currFDs)
		newname = table + "_" + "".join(newschema)
		decomp[currTable] = [currFDs, currSchema]
		decomp[newname] = [newfds, newschema]

def checkPreservation(dependancies, decomp):
	tempFDs = dict()
	preserved = True
	for table in decomp:
		for lhs in decomp[table][0]:
			try:
				tempFDs[lhs] += decomp[table][0][lhs]
			except KeyError:
				tempFDs[lhs] = decomp[table][0][lhs]

	if checkEquivalency(dependancies, tempFDs):
		print "Dependancy was preserved."
	else:
		print "Dependancy was not preserved."

def showDecomp(decomp):
	for key in decomp:
		print "Table ", key
		print "Schema ", "".join(decomp[key][1])
		for dep in decomp[key][0]:
				print "".join(dep), " --> ", "".join(decomp[key][0][dep])
		print " "

def userCheckEquivalency():
	set1 = getInput("Please enter a comma separated list of tables for the first set:")
	set2 = getInput("Please enter a comma separated list of tables for the second set:")

	set1 = set([x.strip() for x in set1.split(",")])
	fds1 = dict()
	vals1 = set()
	set2 = set([x.strip() for x in set2.split(",")])
	fds2 = dict()
	vals2 = set()

	for table1 in set1:
		addFDs(table1, fds1)

	for table2 in set2:
		addFDs(table2, fds2)

	if checkEquivalency(fds1, fds2):
		print "The two sets are equivalent."
	else:
		print "The two sets are not equivalent."

def checkEquivalency(fds1, fds2):
	vals1 = set()
	for key in fds1:
		vals1 = vals1.union(key)
		vals1 = vals1.union(fds1[key])

	vals2 = set()
	for key in fds2:
		vals2 = vals2.union(key)
		vals2 = vals2.union(fds2[key])

	if not vals1==vals2:
		return False

	else:
		for i in range(1, len(vals1)+1):
			for val in itertools.combinations(vals1, i):
				if not getClosure(None, val, fds1)==getClosure(None, val, fds2):
					return False

	# If all elements have the same closure in both sets then they both entail each other & are equivalent
	return True


def addFDs(table, inputdict):
	sql = "SELECT * FROM {}".format(table)
	cursor.execute(sql)
	results = cursor.fetchall()

	for result in results:
		key = tuple([x.strip() for x in result[0].split(',')])
		val = [x.strip() for x in result[1].split(',')]
		inputdict[key] = val

def getInput(str):
	print str
	sel = raw_input(">>")
	if sel.lower()==".exit":
		quit()
	print ""
	return sel


def applicationMenu():
	print "\nWelcome to the Database Analyzer Program"

	# Attempt to connect to an inputted db
	try:
		global conn
		global cursor
		if sys.argv[1][-3:] == ".db":
			conn = sqlite3.connect(sys.argv[1])
			cursor = conn.cursor()
		else:
			getDB()
	# No input provided
	except IndexError:
		getDB()

	# Gather info on Input_ & Input_FDs tables
	getInfo()
	getDependancies()

	# Handle all user input until they exit
	while True:
		print "\nWhat would you like to do?\nPress '.exit' at any time to quit."
		options = {"3. Get closure of an attribute",
			"2. Check set equivalency",
			"\n1. Normalize a database"}
		sel = getInput("\n".join(options))
		# Normalization
		if sel=='1':
			# Loop until user provides proper input
			waiting = True
			while waiting:
				sel = getInput("\nHow would you like to normalize? \n1. BCNF \n2. 3NF")
				if sel=='1':
					decompBCNF(getInput("Please enter a table name:"))
					waiting = False
				elif sel=='2':
					print "Johns stuff"
				else:
					print "Please make a valid selection."
		# Outward facing set equivalency check
		elif sel=='2':
			userCheckEquivalency()
		elif sel=='3':
			table = getInput("Please enter the name of the dependancy table:")
			atts = [x.strip() for x in getInput("Please enter a comma separated list of attributes:").split(',')]
			fds = dict()
			addFDs(table, fds)
			closure = getClosure(None, atts, fds)
			resultstr = "".join(atts) + "+ = "+ "".join(closure)
			print resultstr
		else:
			print "Please make a valid selection."


applicationMenu()
