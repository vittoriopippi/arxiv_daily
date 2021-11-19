import requests
import xmltodict
from datetime import datetime, date, timedelta
import time
import json
from models import db, Article, Category, Author, User, get_or_create

def lazy_get(url):
    for t in [1, 2, 4, 8, 16, 32, 64]:
        try:
            print(f'  Request...                                     ', end='\r')
            response = requests.get(url)
            assert response.status_code == 200
            print(f'                                                 ', end='\r')
            return response
        except (AssertionError, requests.exceptions.ConnectionError, ConnectionError) as e:
            for i in range(t):
                print(f'  Request failed, waiting {t - i} seconds...    ', end='\r')
                time.sleep(1)
            print(' ' * 64, end='\r')
    raise ConnectionAbortedError

class Search:
    base_url = 'http://export.arxiv.org/api/query?search_query={}&start={}&max_results={}&sortBy=submittedDate&sortOrder=descending'
    articles = []
    datetime_fstring = '%Y-%m-%dT%H:%M:%SZ'

    def __init__(self, categories_to_load, days=1, results_per_query=50):
        assert all([isinstance(cat, Category) for cat in categories_to_load])
        self.categories = '+OR+'.join([f'cat:{cat.tag}' for cat in categories_to_load])
        self.results_per_query = results_per_query
        self.load_last(days)

    def load_last(self, days=1):
        self.articles = []
        from_date = date.today() - timedelta(days=days)
        for s in range(0, 1000, self.results_per_query):
            url = self.base_url.format(
                self.categories, s, self.results_per_query)
            response = lazy_get(url)
            res_dict = xmltodict.parse(response.content)
            if 'entry' not in res_dict['feed']: break
            
            for data in res_dict['feed']['entry']:
                if db.session.query(Article).filter_by(id=data['id']).first(): continue
                art = Article()
                art.id = data['id']
                art.updated = datetime.strptime(data['updated'], self.datetime_fstring)
                art.published = datetime.strptime(data['published'], self.datetime_fstring)
                art.title = data['title'].replace('\n', '').replace('  ', ' ')
                art.summary = data['summary'].replace('\n', ' ')
                
                data['author'] = data['author'] if isinstance(data['author'], list) else [data['author'], ]
                data['author'] = list(dict.fromkeys([a['name'] for a in data['author']]))
                authors = [get_or_create(db.session, Author, name=a) for a in data['author']]
                for author in authors: art.authors.append(author)
                
                
                art.arxiv_primary_category = get_or_create(db.session, Category, tag=data['arxiv:primary_category']['@term']).tag
                data['category'] = data['category'] if isinstance(data['category'], list) else [data['category'], ]
                categories = [get_or_create(db.session, Category, tag=c['@term']) for c in data['category']]
                for cat in categories: art.categories.append(cat)
                
                db.session.add(art)
                db.session.commit()
                self.articles.append(art)
            # db.session.commit()
                
            if not all([art.published.date() >= from_date for art in self.articles]):
                break
            time.sleep(3)
        return self.articles

if __name__ == '__main__':
    a = Search(['cs.AI', 'cs.CV'], results_per_query=50)
    print(a.results('cs.AI'))
    pass
