import pickle
import sys
sys.setrecursionlimit(10000)

def loadDict(d):
    with open(d, "rb") as fp:
        n = pickle.load(fp)
    return n

# set up SPARQL endpoint for wikidata
from SPARQLWrapper import SPARQLWrapper, JSON
sparql = SPARQLWrapper("https://query.wikidata.org/sparql")

def getPredicates(subject,obj, number = False):
    if number:
        # we do a different query and return only the non-inverse
        sparql.setQuery("""SELECT * WHERE
        {
             %s ?p %s .
             FILTER(STRSTARTS(str(?p), "http://www.wikidata.org/prop/direct/"))
             SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
        }""" % (subject, obj))
        
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        
        predicates = list()

        for row in results["results"]["bindings"]:
            if row["p"]["type"] == "uri":
                predicates.append(row["p"]["value"])

        return predicates
    
    sparql.setQuery("""SELECT DISTINCT ?p1 ?p2
    {
         {%s ?p1 %s 
         FILTER(STRSTARTS(str(?p1), "http://www.wikidata.org/prop/direct/"))} 
         UNION {%s ?p2 %s
         FILTER(STRSTARTS(str(?p2), "http://www.wikidata.org/prop/direct/"))}
         SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
    }""" % (subject, obj, obj, subject))
    
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    
    predicates_so = list()
    predicates_os = list()
    
    for row in results["results"]["bindings"]:
        try:
            if row["p1"]["type"] == "uri":
                predicates_so.append(row["p1"]["value"])
            if row["p2"]["type"] == "uri":
                predicates_os.append(row["p2"]["value"])
        except:
            pass

    return predicates_so, predicates_os

# resolve Wikidata entity from title

from wikitables.client import Client

client = Client("en")

def getWikidata(title):
    return client.fetch_wikidata(title)

def retrieveExtract(article):
    return client.fetch_extract(article)

import simplemediawiki 

wiki = simplemediawiki.MediaWiki('https://www.wikidata.org/w/api.php')

def findWDTitle(string, amount = None):
    results = wiki.call({'action': 'wbsearchentities', 'search': string, 'type': 'property', 'language': 'en', 'limit': 10})

    return results['search'][0]['label']

# functions entitiy relatedness using API call
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

import re
def find_number(string):
    return re.findall('\d+', string)

import itertools
from collections import defaultdict
nested_dict = lambda: defaultdict(nested_dict)

def flatten(l):
    return list(itertools.chain.from_iterable(l))

def getSOPred(string1, string2, fnt, section_entities, title):
    e1 = string1.replace("'",'"')
    e2 = string2.replace("'",'"')
    n1 = False
    n2  = False
    predicates_so = set()
    predicates_os = set()
    if string1 not in fnt and string1 not in section_entities and string1 != title:
        # not an actual entity; double quote
        e1 = "'" + e1 + "'"
        n1 = True
    else:
        # must catch exception because forgot to parse out deadlinks
        try:
            e1 = "wd:" + getWikidata(e1)
        except:
            e1 = "'" + e1 + "'"
            n1 = True
    if string2 not in fnt and string2 not in section_entities and string2 != title:
        # not an actual entity; double quote
        e2 = "'" + e2 + "'"
        n2 = True
    else:
        # must catch exception because forgot to parse out deadlinks
        try:
            e2 = "wd:" + getWikidata(e2)
        except:
            e2 = "'" + e2 + "'"
            n2 = True

    if n1 and n2:
        return set(), set()

    if not n1 and not n2:
        pred1, pred2 = getPredicates(e1,e2)

        if pred1:
            # e1 ?p e2
            for p1 in pred1:
                predicates_so.add(p1)
        if pred2:
            # e2 ?p e1
            for p1 in pred2:
                predicates_os.add(p1)

    elif n1 and not n2:
        pred = getPredicates(e2,e1,True)
        if pred:
            for p1 in pred:
                predicates_os.add(p1)

    elif not n1 and n2:
        pred = getPredicates(e1,e2,True)
        if pred:
            # e1 ?p e2
            for p1 in pred:
                predicates_so.add(p1)
    
    return predicates_so, predicates_os

# Predicate/ Column Features
# (+) 12 Max of dice coeffient and jaro-winkler distance
from pyjarowinkler import distance

def dice_coefficient(a,b):
    if not len(a) or not len(b): return 0.0
    """ quick case for true duplicates """
    if a == b: return 1.0
    """ if a != b, and a or b are single chars, then they can't possibly match """
    if len(a) == 1 or len(b) == 1: return 0.0
    
    """ use python list comprehension, preferred over list.append() """
    a_bigram_list = [a[i:i+2] for i in range(len(a)-1)]
    b_bigram_list = [b[i:i+2] for i in range(len(b)-1)]
    
    a_bigram_list.sort()
    b_bigram_list.sort()
    
    # assignments to save function calls
    lena = len(a_bigram_list)
    lenb = len(b_bigram_list)
    # initialize match counters
    matches = i = j = 0
    while (i < lena and j < lenb):
        if a_bigram_list[i] == b_bigram_list[j]:
            matches += 2
            i += 1
            j += 1
        elif a_bigram_list[i] < b_bigram_list[j]:
            i += 1
        else:
            j += 1
    
    score = float(matches)/float(lena + lenb)
    return score

def getfeature12(string1, string2):
    return max(distance.get_jaro_distance(string1, string2, winkler=True, scaling=0.1),\
              dice_coefficient(string1, string2))


tables = loadDict(sys.argv[1])

import csv

file1 = sys.argv[2]
#filegold = sys.argv[3]

for k,v in tables.items():
    print(k)
    for k1,v1 in v.items():
# for v in range(1):
#     print(k)
#     for k1,v1 in tables.items():
        # hit table
        old_table = v1["old_table"]
        new_table = v1["new_table"]
        section_title = v1["section_title"]

        len_rows = len(old_table)
        len_cols = len(old_table[0])

        temp_table = [[0 for y in range(len_cols)] for x in range(len_rows)]

        # populate temp table (copy of new table) with values from original table if it hasn't been disambiguated
        # also generate all possible positions
        positions = nested_dict()
        for x in range(len_rows):
            for y in range(len_cols):
                if not new_table[x][y]:
                    # try to make the obj a number
                    try:
                        n = find_number(old_table[x][y])
                    except:
                        n = []
                    if n:
                        temp_table[x][y] = [str(n[0])]
                    else:
                        temp_table[x][y] = [str(old_table[x][y]).replace("'",'"')]
                else:
                    temp_table[x][y] = new_table[x][y]
                    
                len_cell = len(temp_table[x][y]) # how many elements are inside cell                
                
                cell_indices = list(itertools.product([y],list(range(len_cell))))
  
                if x > 0: # skip the header
                    for ci in cell_indices:
                        positions[x][ci] = temp_table[x][ci[0]][ci[1]]     
                        
        section_entities = list()
        d = disambig(k + retrieveExtract(k) + section_title, 0.1)
        for original, entitytitle in d.items():
            if original in section_title:
                section_entities.append(entitytitle)
                
        if section_entities:
            # make up pos for section
            for ise, se in enumerate(section_entities):
                positions["section"][(ise, "section")] = se
        
        # created new temp_table
        # generate all relations based on pos
        relations = list()
        halfrelations = list() # only generate half to reduce SPARQL queries
        fullpositions = list() # we keep a list of the positions inside the table
                               # to create the cartesian producst later
        for row, pos in positions.items():
            if row != "section" or row != "article":
                fullpos = list(itertools.product([row], pos.keys()))
                fullpositions+=fullpos
                relations+=list(itertools.permutations(fullpos,2))
                halfrelations+=list(itertools.combinations(fullpos,2))
                
        # generate relations between section title and entities inside table
        fullpos = list(itertools.product(["section"], positions["section"].keys()))
        relations+=list(itertools.product(fullpos, fullpositions))
        halfrelations+=list(itertools.product(fullpos, fullpositions))
        relations+=list(itertools.product(fullpositions, fullpos))
        
        # generate relations between article title and entities inside table
        fullpos = [("article", (k, "article"))]
        relations+=list(itertools.product(fullpos, fullpositions))
        halfrelations+=list(itertools.product(fullpos, fullpositions))
        relations+=list(itertools.product(fullpositions, fullpos))      
        
            
        resolved_relations = defaultdict(list)
        resolved_halfrelations = defaultdict(list)
        for r in relations:
            if r[0][0] == "article":
                subject = r[0][1][0]
            elif r[0][0] == "section":
                subject = section_entities[r[0][1][0]]
            else:
                subject = temp_table[r[0][0]][r[0][1][0]][r[0][1][1]]
                
            if r[1][0] == "article":
                obj = r[1][1][0]
            elif r[1][0] == "section":
                obj = section_entities[r[1][1][0]]
            else:
                obj = temp_table[r[1][0]][r[1][1][0]][r[1][1][1]]
                
            resolved_relations[(subject,obj)].append(r)
            
        for r in halfrelations:
            if r[0][0] == "article":
                subject = r[0][1][0]
            elif r[0][0] == "section":
                subject = section_entities[r[0][1][0]]
            else:
                subject = temp_table[r[0][0]][r[0][1][0]][r[0][1][1]]
                
            if r[1][0] == "article":
                obj = r[1][1][0]
            elif r[1][0] == "section":
                obj = section_entities[r[1][1][0]]
            else:
                obj = temp_table[r[1][0]][r[1][1][0]][r[1][1][1]]
                
            resolved_halfrelations[(subject,obj)].append(r)

        # use half relations to find predicates
        predicates = defaultdict(list)
        for hr in resolved_halfrelations.keys():
            # get all the rows to flatten
            rows = list()
            fnt = list()
            for pos in resolved_halfrelations[hr]:
                if isinstance(pos[0][0],int):
                    rows.append(pos[0][0])
                if isinstance(pos[1][0],int):
                    rows.append(pos[1][0])
            for r in rows:
                fnt+=flatten([new_table[r]])
                                
            try:                    
                soPred, osPred = getSOPred(hr[0], hr[1], fnt, section_entities, k)
            except:
                continue
                        
            if soPred:
                predicates[(hr[0],hr[1])]+=soPred
            if osPred:
                predicates[(hr[1],hr[0])]+=osPred

        if predicates:
            print(predicates)
            # extract features and write to csv
            feature1 = len(temp_table) - 1 # do not count header
            feature2 = len(temp_table[0])
            feature3 = len(relations)

            lp = list()
            for x in predicates.keys():
                lp+=resolved_relations[x]
            feature4 = len(relations) - len(lp)

            uniquepotential = set(relations) - set(lp)
            feature5 = len(uniquepotential)

            # extract feature 6 when writing specific relations

            allsubjects = defaultdict(int)
            allobjects = defaultdict(int)
            for r in resolved_relations.keys():
                factor = len(resolved_relations[r])
                allsubjects[r[0]]+=factor
                allobjects[r[1]]+=factor

#             feature7 = (len(allsubjects.keys()) / sum(allsubjects.values())) / (len(allobjects.keys()) / sum(allobjects.values()))
            feature7 = (len(allsubjects.keys()) / sum(allsubjects.values())) # it will be the same for objects since we try all combinations

             # write the gold standard triples

            to_write = set()


#                     print(subject,wdtitle,obj)
#                     print(ip)

            # features 6,8,9,10,11,12,13
            for pk, pv in predicates.items(): 
                print(pk,pv)
                subject = pk[0]
                obj = pk[1]
                subjectFlag = False
                objFlag = False
                for ip in pv:
                    for rr in resolved_relations[pk]:
                        if rr[0][0] == "article":
                            subjectFlag = True
                        elif rr[0][0] == "section":
                            subjectFlag = True

                        if rr[1][0] == "article":
                            objFlag = True
                        elif rr[1][0] == "section":
                            objFlag = True

                        try:
                            relatedness = tagme.relatedness_title((subject, obj)).relatedness[0].rel
                        except:
                            relatedness = 0
                        if relatedness:
                            feature6 = float(relatedness)
                        else:
                            feature6 = 0

                        # feature 8 and 10
                        if subjectFlag:
                            if rr[0][1] == "article":
                                feature8 = 1
                                feature10 = len(k)
                            else:
                                feature8 = len(section_entities)
                                feature10 = len(section_title)
                            subj_header = subject
                        else:
                            feature8 = len(temp_table[rr[0][0]][rr[0][1][0]])
                            feature10 = len(old_table[rr[0][0]][rr[0][1][0]])

                            subj_header = old_table[0][rr[0][1][0]]

                        # feature 9 and 11
                        if objFlag:
                            if rr[1][1] == "article":
                                feature9 = 1
                                feature11 = len(k)
                            else:
                                feature9 = len(section_entities)
                                feature11 = len(section_title)
                            obj_header = obj

                        else:
                            feature9 = len(temp_table[rr[1][0]][rr[1][1][0]])
                            feature11 = len(old_table[rr[1][0]][rr[1][1][0]])

                            obj_header = old_table[0][rr[1][1][0]]


                        # feature 12
                        wdtitle = findWDTitle(ip)
                        feature12 = max(getfeature12(subj_header,wdtitle),getfeature12(obj_header,wdtitle))

                        # feature 13
                        feature13 = len(resolved_relations[(subject,obj)])

                        print(subject,wdtitle,obj)

                        to_write.add((feature1,feature2,feature3,feature4,feature5,\
                                                    feature6,feature7,feature8,feature9,feature10,\
                                                    feature11,feature12,feature13,ip,subject,wdtitle,obj,1))            
            
            
                potentialrows = set(range(1,len_rows))
                subject_col = list()
                object_col = list()

                for ir in resolved_relations[pk]:
                    potentialrows = potentialrows - set([ir[0][0]])
                    if ir[0][0] != "section" and ir[0][0] != "article":
                        subject_col.append(ir[0][1][0])
                    if ir[1][0] != "section" and ir[1][0] != "article":
                        object_col.append(ir[1][1][0])
                    if ir[0][0] == "section" or ir[0][0] == "article":
                        subject_col.append(ir[0][1])
                    if ir[1][0] == "section" or ir[1][0] == "article":
                        object_col.append(ir[1][1])
                      
                potential_subjects = set()
                potential_objects = set()
                
                for row in potentialrows:
                    # use uniquepotential in the future
                    for sc in set(subject_col):
                        potential_subjects = potential_subjects.union(set([(row, xsc)\
                                                                           for xsc in positions[row].keys()\
                                                                           if xsc[0]]))
                        try:
                            if sc[1] == "article" or sc[1] == "section":
                                potential_objects.add(sc)    
                        except:
                            pass

                    for oc in set(object_col):
                        potential_objects = potential_objects.union(set([(row, xoc)\
                                                                         for xoc in positions[row].keys()\
                                                                         if xoc[0]])) 
                        try:                        
                            if oc[1] == "article" or oc[1] == "section":
                                potential_objects.add(oc)
                        except:
                            pass

                    # generate cartesian product between potential subjects and potential columns
                    combos = list(itertools.product(potential_subjects, potential_objects))
                    
                    # print(combos)
                    for cc in combos:
                        
                        subjectFlag = False
                        objFlag = False
                        
                        try:
                            if not new_table[cc[0][0]][cc[0][1][0]] and not new_table[cc[1][0]][cc[1][1][0]]:
                                continue
                        except:
                            # check to see if entity is from title or subsection
                            if cc[0][1] == "article":
                                subject = k
                                subjectFlag = True
                            elif cc[0][1] == "section":
                                subject = section_entities[cc[0][0]]
                                subjectFlag = True
                            else:
                                subject = temp_table[cc[0][0]][cc[0][1][0]][cc[0][1][1]]

                            if cc[1][1] == "article":
                                obj = k
                                objFlag = True
                            elif cc[1][1] == "section":
                                obj = section_entities[cc[1][0]]
                                objFlag = True
                            else:                            
                                obj = temp_table[cc[1][0]][cc[1][1][0]][cc[1][1][1]]

                            if subject != obj and subject!='' and obj!='':
                                try:
                                    relatedness = tagme.relatedness_title((subject, obj)).relatedness[0].rel
                                except:
                                    relatedness = 0
                                if relatedness:
                                    feature6 = float(relatedness)
                                else:
                                    feature6 = 0

                                # feature 8 and 10
                                if subjectFlag:
                                    if cc[0][1] == "article":
                                        feature8 = 1
                                        feature10 = len(k)
                                    else:
                                        feature8 = len(section_entities)
                                        feature10 = len(section_title)
                                    subj_header = subject
                                else:
                                    feature8 = len(temp_table[cc[0][0]][cc[0][1][0]])
                                    feature10 = len(old_table[cc[0][0]][cc[0][1][0]])

                                    subj_header = old_table[0][cc[0][1][0]]

                                # feature 9 and 11
                                if objFlag:
                                    if cc[1][1] == "article":
                                        feature9 = 1
                                        feature11 = len(k)
                                    else:
                                        feature9 = len(section_entities)
                                        feature11 = len(section_title)
                                    obj_header = obj

                                else:
                                    feature9 = len(temp_table[cc[1][0]][cc[1][1][0]])
                                    feature11 = len(old_table[cc[1][0]][cc[1][1][0]])

                                    obj_header = old_table[0][cc[1][1][0]]


                                # feature 12
                                wdtitle = findWDTitle(pv[0].split('/')[-1])
                                feature12 = max(getfeature12(subj_header,wdtitle),getfeature12(obj_header,wdtitle))

                                # feature 13
                                feature13 = len(resolved_relations[(subject,obj)])

                                print(subject,wdtitle,obj)
                                
                                for ip in pv:
                                    if (feature1,feature2,feature3,feature4,feature5,\
                                                        feature6,feature7,feature8,feature9,feature10,\
                                                        feature11,feature12,feature13,ip,subject,wdtitle,obj,1) not in to_write:
                                        to_write.add((feature1,feature2,feature3,feature4,feature5,\
                                                        feature6,feature7,feature8,feature9,feature10,\
                                                        feature11,feature12,feature13,ip,subject,wdtitle,obj))
            
            with open(file, 'a', newline='') as csvfile:
                spamwriter = csv.writer(csvfile, delimiter=',')                                 
                for twc in to_write:
                    spamwriter.writerow(twc)
                
#                                 with open(file, 'a', newline='') as csvfile:
#                                     spamwriter = csv.writer(csvfile, delimiter=',')
#                                     spamwriter.writerow([feature1,feature2,feature3,feature4,feature5,\
#                                                         feature6,feature7,feature8,feature9,feature10,\
#                                                         feature11,feature12,feature13,pv[0],subject,wdtitle,obj])
        
        