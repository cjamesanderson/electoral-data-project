# Hackish scrapers for converting nightmarish US election data to CSV

from __future__ import print_function
import csv
import states
STATES = [state.upper() for state in states.STATES]

MISC_FLAGS = ['write-in', 'scattering', 'blank', 'void']

def scrape_2014(fname):
    """
    Scrape election data from plain text and write to csv;
    Tailored for 2014 election data
    :param fname: name of file contianing plain text data from OCR
    :output: '[fname].csv'
    :rtype: None
    """
    party_flags = scrape_parties(fname)
    with open(fname, 'r') as f:
        csv_file = open(fname.split('.')[0]+'.csv', 'w')
        csv_writer = csv.writer(csv_file, lineterminator='\n')
        state = None
        get_votes = False  # True when vote totals are in next line
        at_large = False # At Large Reps show up on the line below
        for line in f:
            l_list = line.split()
            if l_list[0].upper() in STATES:
                state = l_list[0]
                #district = 1
            elif ' '.join(l_list[:2]) in STATES:
                state = ' '.join(l_list[:2])
                #district = 1
            elif l_list[0].upper() == 'ENATOR':
                # Senate results
                for ii in range(len(l_list)):
                    # Find period seperators 
                    if len(l_list[ii]) > 30:
                        party = l_list[ii-1].lower().strip()
                        if party == 'write-in':
                            candidate = 'write-in'
                        else:
                            candidate = parse_name(l_list, ii-2)
                        votes = int(''.join(l_list[ii+1].split(',')).strip())
                        csv_writer.writerow([state, -1, candidate, party, votes])
            elif (l_list[0].upper() == 'EPRESENTATIVE' and len(l_list) == 1):
                # Also applies to funky page continuations like California
                at_large = True
            elif (l_list[0].upper() == 'EPRESENTATIVE' and len(l_list) > 2) or\
                  (l_list[0].endswith('.') and l_list[0][:-1].isdigit()) or\
                  at_large:
                #if at_large and district==1:
                #    district = 0
                #else:
                    #print((state, str(district)), end='')
                candidates, parties, district = house_candidate_line(line, party_flags)
                if len(candidates) == 1 and state.upper() != 'FLORIDA':
                    # Unapposed candidates print on a single line
                    try:
                        votes = int(''.join(l_list[-1].split(',')))
                        csv_writer.writerow([state, district, candidates[0], parties[0], votes])
                        #district += 1
                    except ValueError:
                        # Will fail if OCR just skipped a line
                        #print('ValueError on vote scrape:')
                        #print(state, district, l_list)
                        #return
                        get_votes = True
                else:
                    get_votes = True
                at_large = False
            elif get_votes:
                if l_list[0][0].isdigit():
                    try:
                        votes = [int(''.join(ii.split(','))) for ii in l_list]
                    except ValueError:
                        if state.upper() == 'FLORIDA':
                            # Unapposed candidates in Florida
                            votes = [-1]
                        else:
                            print('ValueError on vote scrape:')
                            print(state, district, l_list)
                            return
                    # Write rep district data
                    num_rows = len(candidates)
                    for row in zip([state]*num_rows, [district]*num_rows, candidates, parties, votes):
                        csv_writer.writerow(row)
                    get_votes = False
                    #district += 1
                else:
                    # OCR inserted extra line break in candidate line
                    cont = parse_candidates(l_list)
                    candidates += cont[0]
                    parties += cont[1]
        csv_file.close()

def scrape_parties(fname):
    """
    Scrape an OCR file for a (hopefully comprehensive) list of party names
    """
    parties = list()
    with open(fname, 'r') as f:
        for line in f:
            l_list = line.split()
            # Locate candidate lines
            if (l_list[0] == 'EPRESENTATIVE') or \
               ('.' in l_list[0] and l_list[0][-1].isdigit()):
                   for ii in range(len(l_list)):
                       # Locate period spacers
                       if len(l_list[ii]) > 1 and len(set(l_list[ii].strip())) == 1:
                           parties += [l_list[ii-1].strip().lower()]
    return list(set(parties))

def house_candidate_line(line, party_flags):
    res_parties = list()
    res_candidates = list()
    district = 0
    l_list = line.split()
    if len(l_list) == 1:
        # Junk data
        return (res_parties, res_candidates, district)
    # Remove junk preceding district number
    err_temp = list()
    while True:
        try:
            if not l_list[0].strip()[:-1].isdigit():
                err_temp += [l_list.pop(0)]
                if err_temp[-1] == 'LARGE':
                    district = 0
                    break
            else:
                district = int(l_list.pop(0)[:-1])
                break
        except IndexError:
            print('IndexError:')
            print(err_temp)
            print(line)
            raise IndexError
            
    temp = list()
    candidate = None
    party = None
    while l_list:
        item = l_list.pop(0)
        # Find period seperators
        if len(set(item.strip())) > 1:
            temp += [item]
        else:
            temp_str = ' '.join(temp)
            comma_split = temp_str.split(',')
            # Check if write-in
            if len(comma_split) == 1:
                for flag in MISC_FLAGS:
                    if flag in comma_split[0].lower():
                        party = candidate = comma_split[0]
                        break
                else:
                    # Assume same candidate on multiple party tickets
                    party = comma_split[0]
            else:
                # Check if the first item is party name
                for flag in party_flags:
                    if flag in comma_split[0]:
                        # Assume these are additional parties for previous candidate
                        party = ','.join(comma_split)
                        break
                else:
                    # Assume first item is candidate's name
                    candidate = comma_split.pop(0)
                    # Check for suffix
                    if comma_split[0].lower().strip() in  ('sr.', 'jr.'):
                        candidate += ',' + comma_split.pop(0)
                    # Assume and remain items are party name(s)
                    party = ','.join(comma_split)
            temp = list()
            res_candidates += [candidate]
            res_parties += [party.strip().lower()]
    return (res_candidates, res_parties, district)
                
def parse_candidates(l_list):
    candidates = list()
    parties = list()
    for ii in range(len(l_list)):
        # Find period seperators
        if len(l_list[ii]) > 30:
            jj = ii-1
            parse_party = list()
            while True:
                if (',' not in l_list[jj]) and (len(l_list[jj]) < 30):
                    parse_party.insert(0, l_list[jj])
                    jj -= 1
                else:
                    break
            party = ' '.join(parse_party)
            parties += [party]
            if 'write-in' in party.lower():
                candidates += [party]
            else:
                # Parse candidate name
                candidates += [parse_name(l_list, ii-2)]
    return (candidates, parties)
            
def parse_name(line, index):
    candidate = list()
    while True:
        if len(line[index]) > 30:
            break
        elif line[index].strip()[0].isdigit():
            break
        elif line[index].strip() in ('ENATOR', 'LARGE'):
            break
        elif line[index].strip().endswith(','):
            candidate.insert(0, line[index].strip()[:-1])
        else:
            candidate.insert(0, line[index].strip())
        index -= 1
    return ' '.join(candidate)