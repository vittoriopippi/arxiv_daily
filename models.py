from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import os
import datetime

ARXIV_CATEGORIES =  ['cs.AI', 'cs.AR', 'cs.CC', 'cs.CE', 'cs.CG', 'cs.CL', 'cs.CR', 'cs.CV', 'cs.CY', 
                    'cs.DB', 'cs.DC', 'cs.DL', 'cs.DM', 'cs.DS', 'cs.ET', 'cs.FL', 'cs.GL', 'cs.GR', 
                    'cs.GT', 'cs.HC', 'cs.IR', 'cs.IT', 'cs.LG', 'cs.LO', 'cs.MA', 'cs.MM', 'cs.MS', 
                    'cs.NA', 'cs.NE', 'cs.NI', 'cs.OH', 'cs.OS', 'cs.PF', 'cs.PL', 'cs.RO', 'cs.SC', 
                    'cs.SD', 'cs.SE', 'cs.SI', 'cs.SY', 'econ.EM', 'econ.GN', 'econ.TH', 'eess.AS', 
                    'eess.IV', 'eess.SP', 'eess.SY', 'math.AC', 'math.AG', 'math.AP', 'math.AT', 'math.CA', 
                    'math.CO', 'math.CT', 'math.CV', 'math.DG', 'math.DS', 'math.FA', 'math.GM', 'math.GN', 
                    'math.GR', 'math.GT', 'math.HO', 'math.IT', 'math.KT', 'math.LO', 'math.MG', 'math.MP', 
                    'math.NA', 'math.NT', 'math.OA', 'math.OC', 'math.PR', 'math.QA', 'math.RA', 'math.RT', 
                    'math.SG', 'math.SP', 'math.ST', 'astro-ph.CO', 'astro-ph.EP', 'astro-ph.GA', 
                    'astro-ph.HE', 'astro-ph.IM', 'astro-ph.SR', 'cond-mat.dis-nn', 'cond-mat.mes-hall', 
                    'cond-mat.mtrl-sci', 'cond-mat.other', 'cond-mat.quant-gas', 'cond-mat.soft', 
                    'cond-mat.stat-mech', 'cond-mat.str-el', 'cond-mat.supr-con', 'nlin.AO', 'nlin.CD', 
                    'nlin.CG', 'nlin.PS', 'nlin.SI', 'physics.acc-ph', 'physics.ao-ph', 'physics.app-ph', 
                    'physics.atm-clus', 'physics.atom-ph', 'physics.bio-ph', 'physics.chem-ph', 
                    'physics.class-ph', 'physics.comp-ph', 'physics.data-an', 'physics.ed-ph', 
                    'physics.flu-dyn', 'physics.gen-ph', 'physics.geo-ph', 'physics.hist-ph', 
                    'physics.ins-det', 'physics.med-ph', 'physics.optics', 'physics.plasm-ph', 
                    'physics.pop-ph', 'physics.soc-ph', 'physics.space-ph', 'q-bio.BM', 'q-bio.CB', 
                    'q-bio.GN', 'q-bio.MN', 'q-bio.NC', 'q-bio.OT', 'q-bio.PE', 'q-bio.QM', 'q-bio.SC', 
                    'q-bio.TO', 'q-fin.CP', 'q-fin.EC', 'q-fin.GN', 'q-fin.MF', 'q-fin.PM', 'q-fin.PR', 
                    'q-fin.RM', 'q-fin.ST', 'q-fin.TR', 'stat.AP', 'stat.CO', 'stat.ME', 'stat.ML', 
                    'stat.OT', 'stat.TH']

db_name = 'bot.sqlite'

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_name}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

preferences = db.Table('preferences',
    db.Column('category_tag', db.String(20), db.ForeignKey('category.tag')),
    db.Column('user_chat_id', db.Integer, db.ForeignKey('user.chat_id'))
)

message_articles = db.Table('message_articles',
    db.Column('message_id', db.Integer, db.ForeignKey('message.id')),
    db.Column('article_id', db.Integer, db.ForeignKey('article.id'))
)

author_article = db.Table('author_article',
    db.Column('author_name', db.String(64), db.ForeignKey('author.name')),
    db.Column('article_id', db.String(64), db.ForeignKey('article.id'))
)

article_category = db.Table('article_category',
    db.Column('article_id', db.String(64), db.ForeignKey('article.id')),
    db.Column('category_tag', db.String(20), db.ForeignKey('category.tag'))
)

class User(db.Model):
    chat_id = db.Column(db.Integer, primary_key=True)
    preferences = db.relationship('Category', secondary=preferences, lazy='subquery', backref=db.backref('preferite_of', lazy=True))
    messages = db.relationship('Message', backref='user', lazy=True)
    
    def new_articles(self, days=1):
        current_time = datetime.datetime.utcnow()
        upper_bound = current_time - datetime.timedelta(days=days)
        lower_bound = current_time - datetime.timedelta(days=days - 1)
        articles = []
        for cat in self.preferences:
            query = Article.query.filter(Article.categories.any(Category.tag == cat.tag))
            query = query.filter(Article.published.between(upper_bound, lower_bound))
            articles += query.all()
        return articles

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_chat_id = db.Column(db.Integer, db.ForeignKey('user.chat_id'), nullable=False)
    articles = db.relationship('Article', secondary=message_articles, lazy='subquery', backref=db.backref('messages', lazy=True))
    index = db.Column(db.Integer, nullable=False, default=0)
    expanded = db.Column(db.Boolean, nullable=False, default=False)
    
    def to_txt(self, max_len=300):
        if len(self.articles) == 0: return self.__no_articles()
        assert len(self.articles) > 0
        
        index = self.index % len(self.articles)
        article = sorted(self.articles)[index]
        template = "\[{}/{}] Pub: {}\n*{}*\n_{}_\n\n{}\n\n[{}]({})"
        summary = article.summary if self.expanded else article.summary[:max_len] + '...'
        authors_to_print = article.authors if self.expanded else article.authors[:5]
        authors = ', '.join([a.name for a in authors_to_print])
        return template.format(
            index + 1,
            len(self.articles),
            datetime.datetime.strftime(article.published, "%d/%m/%Y %H:%M"),
            article.title,
            authors,
            summary,
            article.id, article.id
        )
        
    def __no_articles(self):
        return 'No articles today'
    
    def exec_op(self, op):
        if op == 'next':
            self.index += 1
        elif op == 'prev':
            self.index -= 1
        elif op == 'exp':
            self.expanded = not self.expanded
        else:
            raise ValueError
        db.session.commit()

class Article(db.Model):
    id = db.Column(db.String(64), primary_key=True)
    updated = db.Column(db.DateTime, nullable=False)
    published = db.Column(db.DateTime, nullable=False)
    title = db.Column(db.String, nullable=False, default='')
    summary = db.Column(db.String, nullable=False, default='')
    authors = db.relationship('Author', secondary=author_article, lazy='subquery', backref=db.backref('articles', lazy=True))
    categories = db.relationship('Category', secondary=article_category, lazy='subquery', backref=db.backref('articles', lazy=True))
    arxiv_primary_category = db.Column(db.String(20), db.ForeignKey('category.tag'))
    
    def __lt__(self, other):
        assert isinstance(other, Article)
        return self.published < other.published

class Author(db.Model):
    name = db.Column(db.String(64), primary_key=True)

class Category(db.Model):
    tag = db.Column(db.String(32), primary_key=True)
    
def get_or_create(session, model, commit=False, **kwargs):
    with session.no_autoflush:
        instance = session.query(model).filter_by(**kwargs).first()
        if instance:
            return instance
        else:
            instance = model(**kwargs)
            session.add(instance)
            if commit: session.commit()
            return instance

def exists(session, model, **kwargs):
    return session.query(model).filter_by(**kwargs).first() is not None
    
if not os.path.exists(db_name):
    db.create_all()
    
    # Add all categories
    for cat in ARXIV_CATEGORIES:
        db.session.add(Category(tag=cat))
    db.session.commit()

if __name__ == '__main__':
    from datetime import datetime
    user1 = User(chat_id='12341234')
    
    art1 = Article(id='543423', title='', summary='')
    art1.updated = datetime.now()
    art1.published = datetime.now()
    art1.arxiv_primary_category = Category.query.first().tag
    
    art2 = Article(id='541423', title='', summary='')
    art2.updated = datetime.now()
    art2.published = datetime.now()
    art2.arxiv_primary_category = Category.query.first().tag
    
    msg = Message(id=1, user_chat_id=user1.chat_id)
    msg.articles.append(art1)
    msg.articles.append(art2)
    
    user1.messages.append(msg)
    
    db.session.add(user1)
    db.session.add(art2)
    db.session.add(art1)
    db.session.add(msg)
    
    db.session.commit()
