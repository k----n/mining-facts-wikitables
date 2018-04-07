import logging
import mwparserfromhell as mwp

from collections import defaultdict

from wikitables.util import ftag
from wikitables.client import Client
from wikitables.models import WikiTable

log = logging.getLogger('wikitables')
nested_dict = lambda: defaultdict(nested_dict)

def import_tables(article, lang="en"):
    client = Client(lang)
    page = client.fetch_page(article)
    body = page['revisions'][0]['*']
    extract = client.fetch_extract(article)
    parsed_body = mwp.parse(body, skip_style_tags=True)

    tables_info = nested_dict()

    tables_info['title'] = page['title']
    tables_info['extract'] = extract

    ## get sections
    sections = parsed_body.get_sections(include_lead = False, include_headings = True, flat = True)

    print(page['title'])
    section_count = 0
    for idx, s in enumerate(sections):
        t = s.filter_tags(matches=ftag('table'))
        if t:
            head = mwp.parse(s.filter_headings()[0])
            tables_info[section_count]["head"] = head.strip_code()
            s.remove(head)
            table_count = 0
            for i,x in enumerate(t):
                nested = mwp.parse(x).filter_tags(matches=ftag('table'))
                if not nested:
                    name = '{}|Table {}'.format(page['title'],table_count)
                    wt = WikiTable(name, x)
                    if not wt.flag:
                        tables_info[section_count]["table"][table_count] = wt
                        table_count+=1
                    s.remove(x)
            tables_info[section_count]["text"] = s.strip_code()
            section_count+=1

    return tables_info
