import sys

import re
from collections import defaultdict

import pickle

sys.setrecursionlimit(10000)
with open(sys.argv[1], "rb") as fp:
    extracted_tables = pickle.load(fp)

# functions disambiguate entities using API call
import tagme

with open("tagme", 'r') as file:
    token = file.readline().strip()
    
tagme.GCUBE_TOKEN = token

def disambig(text, min_rho=None):
    annotations = tagme.annotate(text)
    a = dict()
    for x in annotations.annotations:
        if min_rho is None or x.score > min_rho:
            a[str(x.mention)] = x.entity_title
        
    return a

# check if normalzied table is empty
# https://stackoverflow.com/a/1605679
def isListEmpty(inList):
    if isinstance(inList, list): # Is a list
        return all( map(isListEmpty, inList) )
    return False # Not a list

nested_dict = lambda: defaultdict(nested_dict)
normalized_tables = nested_dict()

for k,v in extracted_tables.items():
    if type(v) is dict:
        # we've hit an article
        title = v['title']
        summary = v['extract']
        print(title)
        for k1,v1 in v.items():
            if type(v1) is dict:
                # hit a section containing table(s)                
                heading = v1["head"]
                text = v1["text"]
                                                
                # iterate through tables
                for k2,v2 in v1['table'].items():
                    # start getting our features here
                    rows_count = v2["rows_count"]
                    cols_count = v2["cols_count"]
                    if rows_count + 1 < 2 or cols_count < 2:
                        # table is too small (< 2x2) so we iterate to next table
                        # we are left with 196 tables
                        continue
                    else:
                        # get the rows  and recreate the table with only disambiguated entities
                        old_table = [[0 for x in range(cols_count)] for y in range(rows_count+1)] # add 1 for the header row
                        new_table = [[0 for x in range(cols_count)] for y in range(rows_count+1)] # add 1 for the header row

                        # map the header for the rows
                        hmap = dict()
                        # disambiguate the header
                        for ic, h in enumerate(v2["head"]):
                            entities = list()
                            e = re.findall(r'\[([^]]*)\]', h)
                            if e:
                                for l in e:
                                    if "http://" in l or "https://" in l:
                                        pass
                                    else:
                                        entities.append(l)
                            else:
                                # no links so we disambiguate with combining article title, section text & heading
                                d = disambig(title + heading + text + h, 0.1)
                                for original,entitytitle in d.items():
                                    if original in h:
                                        entities.append(entitytitle)
                            
                            hmap[h] = ic
                                              
                            old_table[0][ic] = h
                            new_table[0][ic] = list(set(entities))
                            
                        
                        for ir, v3 in enumerate(v2["rows"], 1):                            
                            # iterate through cells
                            for k4, v4 in v3.items():
                                # inside a cell
                                entities = list()
                                if v4["link"]:
                                    # extract the links
                                    e = re.findall(r'\[([^]]*)\]',v4["value"])
                                    for l in e:
                                        if "http://" in l or "https://" in l:
                                            pass
                                        else:
                                            entities.append(l)

                                # otherwise diambiguate via combining article title, section text & heading, 
                                # column header
                                # if no entities have been extracted yet
                                if not entities:
                                    d = disambig(title + heading + text + k4 + v4["value"], 0.1)
                                    for original,entitytitle in d.items():
                                        if original in v4["value"]:
                                            entities.append(entitytitle)
                                            
                                cellindex = hmap[k4]

                                old_table[ir][cellindex] = v4["value"]
                                new_table[ir][cellindex] = list(set(entities))

                        if not isListEmpty(new_table):
                            normalized_tables[title][k2]["old_table"] = old_table
                            normalized_tables[title][k2]["new_table"] = new_table
                            normalized_tables[title][k2]["section_title"] = heading
                            print(old_table)
                            print(new_table)

# save the normalized tables

# https://stackoverflow.com/a/26496899
def default_to_regular(d):
    if isinstance(d, defaultdict):
        d = {k: default_to_regular(v) for k, v in d.items()}
    return d

normalized_tables = default_to_regular(normalized_tables)

with open(sys.argv[2], "wb") as fp:
     pickle.dump(normalized_tables, fp)
