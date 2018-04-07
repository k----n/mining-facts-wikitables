import json
import logging
import mwclient
import mwparserfromhell
from mwparserfromhell.nodes.tag import Tag
from mwparserfromhell.nodes.template import Template
from mwparserfromhell.nodes.wikilink import Wikilink

from wikitables.util import TableJSONEncoder, ftag, ustr, guess_type

log = logging.getLogger('wikitables')

ignore_attrs = [ 'group="Note"' ]

site = mwclient.Site('en.wikipedia.org')

class Field(object):
    """
    Field within a table row
    attributes:
     - raw(mwparserfromhell.nodes.Node) - Unparsed field Wikicode
     - value(str) - Parsed field value as string
    """
    def __init__(self, node):
        self.raw = node
        self.link = False
        self.value = self._read(self.raw, self.link)
        # Determie if wikilink is contained


    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return str(self.value)

    def __json__(self):
        return self.value

    def _read(self, node, link):
        def _read_parts(n):
            if hasattr(n, 'contents') and hasattr(n.contents, 'nodes'):
                for subnode in n.contents.nodes:
                    for x in _read_parts(subnode):
                        yield x
            else:
                val = self._read_part(n, link).strip(' \n')
                if val: yield ustr(val)

        joined = ' '.join(list(_read_parts(node)))
        return guess_type(joined)

    def _read_part(self, node, link):
        if isinstance(node, Template):
            if node.name == 'refn':
                log.debug('omitting refn subtext from field')
                return ''
            return self._read_template(node, link)
        if isinstance(node, Tag):
            if self._exclude_tag(node):
                return ''
            return node.contents.strip_code()
        if isinstance(node, Wikilink):
            #if node.text:
            #    return node.text
            self.link = True
            return "[" + str(node.title) + "]"
        return node

    @staticmethod
    def _exclude_tag(node):
        # exclude tag nodes with attributes in ignore_attrs
        n_attrs = [ x.strip() for x in node.attributes ]
        for a in n_attrs:
            if a in ignore_attrs:
                return True

        # exclude tag nodes without contents
        if not node.contents:
            return True

        return False

    @staticmethod
    def _read_template(node, link):
        """ Concatenate all template values having an integer param name """
        def _is_int(o):
            try:
                int(ustr(o))
                return True
            except ValueError:
                return False

        # expand the template using Wikipedia API and get the link if flag
        if node.name == 'flagicon' or node.name == 'flag' or node.name == 'flagcountry':
            name = list()
            a = mwparserfromhell.parse(site.expandtemplates(str(node)))
            links = a.filter_wikilinks()
            for d in links:
                name.append("[" + d.text.split('link=')[-1] + "]")

            return ' '.join(name)

        # currently dealing with only one specific language case        
        elif "lang" == node.name:
            vals = [ustr(p.value) for p in node.params]
            return vals[-1]

        if "formatnum" in node.name:
            return node.name.split(':')[-1]

        vals = [ ustr(p.value) for p in node.params if _is_int(p.name) ]
        return ' '.join(vals)

class Row(dict):
    """
    Single WikiTable row, mapping a field name(str) to wikitables.Field obj
    """
    def __init__(self, *args, **kwargs):
        head = args[0]
        self.raw = args[1]
        # check to see if row can be made
        row = self._read(head, self.raw)
        if row:
            super(Row, self).__init__(row)
        else:
            self.raw = False

    def json(self):
        return json.dumps(self, cls=TableJSONEncoder)

    @property
    def is_null(self):
        for k,f in self.items():
            if f["value"] != '':
                return False
        return True

    @staticmethod
    def _read(head, node):
        cols = list(node.contents.ifilter_tags(matches=ftag('th', 'td')))
        # check to see if number of cells in rows match header
        if len(head) == len([ Field(c) for c in cols ]):
            r = zip(head, [ {"value": Field(c), "link": Field(c).link} for c in cols ])
            return r
        else:
            return False

class WikiTable(object):
    """
    Parsed Wikipedia table
    attributes:
     - name(str): Table name in the format <article_name>[<table_index>]
     - head(list): List of parsed column names as strings
     - rows(list): List of <wikitables.Row> objects
    """
    def __init__(self, name, raw_table):
        self.name = ustr(name)
        self.rows = []
        self._head = []
        self._node = raw_table
        self._tr_nodes = raw_table.contents.filter_tags(matches=ftag('tr'))
        # hack to determine whether or not to return table
        self.flag = False
        self._read(raw_table)

    def json(self):
        return json.dumps(self.rows, cls=TableJSONEncoder)

    @property
    def head(self):
        return self._head

    @property
    def head_len(self):
        return len(self._head)

    @property
    def rows_len(self):
        return len(self.rows)

    @head.setter
    def head(self, val):
        if not isinstance(val, list):
            raise ValueError('table head must be provided as list')
        self._head = val
        self.rows = [ Row(self._head, tr) for tr in self._tr_nodes ]
        

    def __repr__(self):
        return "<WikiTable '%s'>" % self.name

    def _read(self, raw_table):

        # read header first
        header_nodes = self._find_header_flat()
        if not header_nodes:
            header_nodes = self._find_header_row()

        if header_nodes:
            for th in header_nodes:
                f = list()
                if hasattr(th.contents, 'nodes'):
                    for n in th.contents.nodes:
                        if isinstance(n, Wikilink):
                            f.append("[" + str(n.title) + "]")
                        else:
                            f.append(str(n))

                field_name = ' '.join(f).strip()
                self._head.append(ustr(field_name))

            # read rows
            for tr in self._tr_nodes:
                if tr.contents:
                    row = Row(self._head, tr)
                    # hack to determine whether or not to return table
                    if row.raw is False:
                        self.flag = True
                        break
                    elif not row.is_null:
                        self.rows.append(row)
        else:
            self.flag = True
                

        self._log('parsed %d rows %d cols' % (len(self.rows), len(self._head)))

    def _log(self, s):
        log.debug('%s: %s' % (self.name, s))

    def _find_header_flat(self):
        """
        Find header elements in a table, if possible. This case handles
        situations where '<th>' elements are not within a row('<tr>')
        """
        nodes = self._node.contents.filter_tags(
                    matches=ftag('th'), recursive=False)
        if not nodes:
            return
        self._log('found header outside rows (%d <th> elements)' % len(nodes))
        return nodes

    def _find_header_row(self):
        """
        Evaluate all rows and determine header position, based on
        greatest number of 'th' tagged elements
        """
        th_max = 0
        header_idx = 0
        for idx, tr in enumerate(self._tr_nodes):
            th_count = len(tr.contents.filter_tags(matches=ftag('th')))
            if th_count > th_max:
                th_max = th_count
                header_idx = idx
        
        # another hotfix hack
        if self._tr_nodes:

            self._log('found header at row %d (%d <th> elements)' % \
                        (header_idx, th_max))

            header_row = self._tr_nodes.pop(header_idx)
            return header_row.contents.filter_tags(matches=ftag('th'))
        else:
            return False
