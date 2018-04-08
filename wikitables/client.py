import logging
import requests

log = logging.getLogger(__name__)

class ArticleNotFound(RuntimeError):
    """ Article query returned no results """

class Client(requests.Session):
    """ Mediawiki API client """

    def __init__(self, lang="en"):
        super(Client, self).__init__()
        self.base_url = 'https://' + lang + '.wikipedia.org/w/api.php'

    def fetch_wikidata(self, title, method='GET'):
        """ Query for page by wikidata entity """
        params = { 'prop': 'pageprops',
                   'format': 'json',
                   'action': 'query',
                   'titles': title,
                   'redirects': 1,
                   'ppprop': 'wikibase_item' }    

        r = self.request(method, self.base_url, params=params)
        r.raise_for_status()
        pages = r.json()["query"]["pages"]
        # use key from first result in 'pages' array
        pageid = list(pages.keys())[0]
        if pageid == '-1':
            raise ArticleNotFound('no matching articles returned') 

        return pages[pageid]["pageprops"]["wikibase_item"]
    

    def fetch_page(self, title, method='GET'):
        """ Query for page by title """
        params = { 'prop': 'revisions',
                   'format': 'json',
                   'action': 'query',
                   'titles': title,
                   'rvprop': 'content' }
        r = self.request(method, self.base_url, params=params)
        r.raise_for_status()
        pages = r.json()["query"]["pages"]
        # use key from first result in 'pages' array
        pageid = list(pages.keys())[0]
        if pageid == '-1':
            raise ArticleNotFound('no matching articles returned')

        return pages[pageid]

    def fetch_extract(self, title, method='GET'):
        # Retrieve content summary
        params = { 'prop': 'extracts',
           'format': 'json',
           'action': 'query',
           'explaintext': '',
           'titles': title,
           'exintro': '' }
        r = self.request(method, self.base_url, params=params)
        r.raise_for_status()
        pages = r.json()["query"]["pages"]
        # use key from first result in 'pages' array
        pageid = list(pages.keys())[0]
        if pageid == '-1':
            raise ArticleNotFound('no matching articles returned')

        return pages[pageid]['extract']
