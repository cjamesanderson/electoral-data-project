from __future__ import print_function
import csv
import xlrd
import sqlite3

# Map for party codes that changed over the years
PARTY_MAP = {'C': 'CRV', 'D': 'DEM', 'ENE': 'ENI', 'GRE': 'GRN', 'I': 'IND',
             'LIB': 'LBT', 'LU': 'LBU', 'NL': 'NLP', 'NA': 'NPA', 'NS': 'NSP',
             'NSF': 'NSP', 'NAF': 'NPA', 'NON': 'NPA', 'NNE': 'NPA', 'N': 'NPA',
             'UN': 'NPA', 'O': 'OTH', 'OP': 'OTH', 'FSL': 'SLF', 'PAF': 'PFP',
             'PC': 'PET', 'PCN': 'PET', 'PC': 'PAC', 'R': 'REP', 'SUS': 'SOC'}

def make_db(dbname):
    """
    make_db: create an empty database structure for storing election data
    :param dbname: name to give database file
    :rtype None:
    """
    sql_stmt = '''CREATE TABLE result
                   (result_id INT PRIMARY KEY,
                    state_abv TEXT,
                    state TEXT,
                    district TEXT,
                    cand_first_name TEXT,
                    cand_last_name TEXT,
                    cand_name TEXT,
                    party TEXT,
                    general_votes INT,
                    general_percent FLOAT,
                    general_unopposed BOOL,
                    general_winner BOOL,
                    incumbent BOOL,
                    year INT)'''
    curs = sqlite3.connect(dbname).cursor()
    curs.execute(sql_stmt)
    curs.connection.commit()
    curs.connection.close()
    
def import_xl(dbname, fname, sheet_name, year):
    """
    import_xl: import data from Excel (.xls) spreadsheet to SQlite3 database
    :param dbname: sqlite3 database name
    :param fname: .xls filename
    :param sheet_name: name of sheet inside Excel workbook
    :param year: election year
    """
    rows = xlrd.open_workbook(fname).sheet_by_name(sheet_name).get_rows()
    # Skip column labels
    rows.next()
    adds = list()
    for row in rows:
    # Check for general election votes/percentages and not vote total row
        if 0 not in (row[15].ctype, row[16].ctype) and row[9].ctype == 0:
            # Columns switched in 2012
            if len(row[1].value) == 2:
                state_abv = row[1].value
                state = row[2].value
            else:
                state_abv = row[2].value
                state = row[1].value
            # Dismiss unexpired term results
            d = unicode(row[3].value).strip().split('.')[0]
            if 'FULL TERM' in d or d == 'SFULL':
                district = row[3].value.split()[0]
            elif ('UNEXPIRED' in d) or ('*' in d) or (d == 'SUN'):
                continue
            # Also ignore write-in totals for all districts
            elif d == 'H':
                continue
            elif d.isdigit() or d.lower() == 's':
                district = d
            else:
                print(row)
                print(d)
                raise ValueError
                
            # If cell is occupied then incumbent = 
            incumbent = (row[5].ctype != 0)
            cand_first_name = row[6].value.strip()
            cand_last_name = row[7].value.strip()
            cand_name = row[8].value.strip()
            try:
                party = PARTY_MAP[row[10].value.strip()]
            except KeyError:
                party = row[10].value.strip()
            # ctype 2 = float
            if row[15].ctype == 2:
                general_votes = row[15].value
                general_percent = row[16].value
                general_unopposed = False
            # ctype 1 = Unicode string
            elif row[15].ctype == 1:
                if row[15].value.strip().lower() == 'unopposed':
                    general_votes = None
                    general_percent = None
                    general_unopposed = True
                elif row[15].value == '#':
                    # Skip candidates who withdrew after primary
                    continue
                else:
                    print(row)
                    print(str(row[15].value), str(row[16].value))
                    raise ValueError
            # Winner indicators not recorded before 2012
            if year >= 2012:
                general_winner = (row[21].ctype != 0)
            else:
                general_winner = False
            adds += [[state_abv, state, district, incumbent, cand_first_name,
                    cand_last_name, cand_name, party, general_votes,
                    general_percent, general_unopposed, general_winner, year]]
    sql_stmt = '''INSERT INTO result (state_abv, state, district, incumbent,
                                        cand_first_name, cand_last_name,
                                        cand_name, party, general_votes,
                                        general_percent, general_unopposed,
                                        general_winner, year) 
                                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)'''
    curs = sqlite3.connect(dbname).cursor()
    curs.executemany(sql_stmt, adds)
    curs.connection.commit()
    curs.connection.close()
    
def import_all_leg_data(dbname):
    """
    import_all_leg_data: convenience function for rebuilding congressional DB
    :param dbname: sqlite3 database filename
    :rtype None:
    """
    import_xl(dbname, '2004congresults.xls', '2004 US HOUSE & SENATE RESULTS', 2004)
    import_xl(dbname, 'results06.xls', '2006 US House & Senate Results', 2006)
    import_xl(dbname, '2008congresults.xls', '2008 House and Senate Results', 2008)
    import_xl(dbname, 'results10.xls', '2010 US House & Senate Results', 2010)
    import_xl(dbname, '2012congresults.xls', '2012 US House & Senate Results', 2012)
    import_xl(dbname, 'results14.xls', '2014 US House Results by State', 2014)
    
def import_to_db(dbname, fname, seat, year):
    """
    import_to_db: import data from CSV to SQlite 3 database
    :param dbname: sqlite3 database name
    :param fname: CSV filename
    """
    assert seat in ('house', 'senate', 'mixed', 'president')
    with open(fname) as f:
        csv_reader = csv.reader(f, delimiter=':')
        # Skip column labels
        csv_reader.next()
        adds = list()
        for line in csv_reader:
            # Check for general election votes/percentages and not vote total row
            if line[15] and line[16] and not line[9]:
                state_abv = unicode(line[1], errors='replace')
                state = unicode(line[2], errors='replace')
                try:
                    if seat == 'house':
                        district = int(line[3])
                    elif seat == 'senate':
                        district = 'S'
                    elif seat == 'mixed':
                        # NOTE: DEVELOPMENT ABANDONED HERE IN FAVOR OF IMPORT_XL
                        pass
                except ValueError:
                    # Dismiss unexpired term results
                    if 'FULL TERM' in line[3]:
                        district = int(line[3].split()[0])
                    elif 'UNEXPIRED' in line[3]:
                        continue
                    # Also ignore write-in totals for all districts
                    elif line[3] == 'H':
                        continue
                    else:
                        print(line)
                        raise ValueError
                    
                incumbent = (len(line[5]) > 0)
                cand_first_name = unicode(line[6], errors='replace')
                cand_last_name = unicode(line[7], errors='replace')
                cand_name = unicode(line[8], errors='replace')
                party = unicode(line[10], errors='replace')
                try:
                    general_votes = int(''.join(line[15].split(',')))
                    general_percent = float(line[16][:-1])
                    general_unopposed = False
                except ValueError:
                    if line[15].lower() == 'unopposed':
                        general_votes = None
                        general_percent = None
                        general_unopposed = True
                    elif line[15] == '#':
                        # Skip candidates who withdrew after primary
                        continue
                    else:
                        print(line)
                        print(str(line[15]), str(line[16]))
                        raise ValueError
                general_winner = (len(line[21]) > 0)
                adds += [[state_abv, state, district, incumbent, cand_first_name,
                        cand_last_name, cand_name, party, general_votes, seat,
                        general_percent, general_unopposed, general_winner, year]]
    sql_stmt = '''INSERT INTO result (state_abv, state, district, incumbent,
                                        cand_first_name, cand_last_name,
                                        cand_name, party, general_votes, seat,
                                        general_percent, general_unopposed,
                                        general_winner, year) 
                                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
    curs = sqlite3.connect(dbname).cursor()
    curs.executemany(sql_stmt, adds)
    curs.connection.commit()
    curs.connection.close()