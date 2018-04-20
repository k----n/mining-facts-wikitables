from wikitables import *
import mwclient
import mwparserfromhell as mwp
import logging
from collections import defaultdict
nested_dict = lambda: defaultdict(nested_dict)

import string
import random

articles = list()
site = mwclient.Site('en.wikipedia.org')


# import the saved articles
import pickle
with open("articles.txt", "rb") as fp:
    articles = set(pickle.load(fp))

# # add more articles

new_articles = set()
count = 0
tdict = nested_dict()

for letter in string.ascii_lowercase:
    counter = 0
    while (counter!=50):
        for page in site.allpages(filterredir='nonredirects', prefix=letter+random.choice(string.ascii_lowercase)):
            if page.name not in articles:
                tables = mwp.parse(page.text()).filter_tags(matches=ftag('table'))
                if tables:
                    t = import_tables(page.name)
                    if t:
                        print(page.name)
                        tdict[str(count)] = t
                        new_articles.add(page.name)
                        counter+=1
                        count+=1
                        break


new_articles = sorted(list(new_articles))
len(new_articles)

# save the extracted tables
# import pickle

# https://stackoverflow.com/a/26496899
def default_to_regular(d):
    if isinstance(d, defaultdict):
        d = {k: default_to_regular(v) for k, v in d.items()}
    return d

# t = default_to_regular(t)

# with open("tables.txt", "wb") as fp:
#      pickle.dump(t, fp)

tdict = default_to_regular(tdict)

with open("new_tables.txt", "wb") as fp:
     pickle.dump(tdict, fp)