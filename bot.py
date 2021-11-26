import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardButton, InlineKeyboardMarkup
import time
import json
import os
import sys
import arxiv
import schedule
from models import db, Category, User, Message
import models
from datetime import datetime

class Bot:
    filename = 'data.json'
    token = None

    def __init__(self):
        self.load()
        self.bot = telepot.Bot(self.token)
        MessageLoop(self.bot, {
            'chat':self.handle_message,
            'callback_query':self.handle_callback_query
            }).run_as_thread()
    
    def handle_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        # if chat_id not in self.people: self.people[chat_id] = User(chat_id)
        print(content_type, chat_type, chat_id, msg['from']['username'])
        
        if content_type == 'text' and msg['text'].startswith('/'):
            func_name = msg['text'].split()[0][1:]
            func = getattr(self, f'cmd_{func_name}', self.cmd_help)
            func(msg)
        else:
            self.cmd_help(msg)
        
    def cmd_help(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        self.bot.sendMessage(chat_id, 'Use command /set followed by the categories that you are interested for separated by spaces.\nExample: "/set cs.CV cs.AI"')
    
    def cmd_feed(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        user = models.get_or_create(db.session, User, commit=True, chat_id=chat_id)
        days = 1
        try: 
            days = int(msg['text'].split()[1])
            assert days > 0
        except:
            pass
        self.notify_user(user, days=days)
        
    def cmd_start(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        user = models.get_or_create(db.session, User, commit=True, chat_id=chat_id)
        self.cmd_help(msg)
        
    def cmd_notify_all(self, msg):
        self.notify_all()
    
    def cmd_set(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        user = models.get_or_create(db.session, User, chat_id=chat_id)
        user.preferences.clear()
        
        str_categories = msg['text'].split()[1:]
        for cat in str_categories:
            if models.exists(db.session, Category, tag=cat):
                user.preferences.append(Category.query.filter_by(tag=cat).first())
            else:
                self.bot.sendMessage(chat_id, f'`{cat}` category not found', parse_mode='Markdown')
        db.session.commit()
        txt_categories = ", ".join([f'`{p.tag}`' for p in user.preferences])
        self.bot.sendMessage(chat_id, f'Your preferences: {txt_categories}', parse_mode='Markdown')
        
    def handle_callback_query(self, msg):
        query_id, from_id, query_data = telepot.glance(msg, flavor='callback_query')
        msg_id, operation = query_data.split('_')
        msg_id = int(msg_id)
        
        if models.exists(db.session, Message, id=msg_id):
            message = Message.query.filter_by(id=msg_id).first()
            message.exec_op(operation)
            
            assert from_id == message.user.chat_id
            self.bot.editMessageText(
                (message.user.chat_id, msg_id), message.to_txt(),
                parse_mode='Markdown', reply_markup=self.__msg_markdown(msg_id))
        db.session.commit()
        
    def __msg_markdown(self, msg_id):
        message = Message.query.filter_by(id=msg_id).first()
        if len(message.articles) == 0:
            return InlineKeyboardMarkup(inline_keyboard=[])
        elif len(message.articles) == 1:
            return InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(text='expand', callback_data=f'{msg_id}_exp'),
                        ]]
                    )
        else:
            return InlineKeyboardMarkup(
                    inline_keyboard=[[
                        InlineKeyboardButton(text='<<', callback_data=f'{msg_id}_prev'),
                        InlineKeyboardButton(text='expand', callback_data=f'{msg_id}_exp'),
                        InlineKeyboardButton(text='>>', callback_data=f'{msg_id}_next'),
                        ]]
                    )
    
    def notify_all(self):
        print('Notify all...')
        used_cat = Category.query.filter(Category.preferite_of != None).all()
        arxiv.Search(used_cat)
        
        for user in User.query.all():
            self.notify_user(user)
            
    def notify_user(self, user, days=1):
        assert isinstance(user, User)
        articles = user.new_articles(days)
            
        message = Message()
        message.user_chat_id = user.chat_id
        for art in articles: message.articles.append(art)
        message.index = 0
        
        message_info = self.bot.sendMessage(user.chat_id, 'Loading...')
        message.id = int(telepot.message_identifier(message_info)[1])
        
        db.session.add(message)
        db.session.commit()
        self.bot.editMessageText((user.chat_id, message.id), message.to_txt(), parse_mode='Markdown',
                                    reply_markup=self.__msg_markdown(message.id))
        
    def save(self):
        db.session.commit()

    def load(self):
        if os.path.exists(self.filename):
            with open(self.filename) as json_file:
                data = json.load(json_file)
                self.token = data['token']
        else:
            print('No "data.json" file found. I\'ve created the file, but you need to insert the telegram token.' )
            with open(self.filename, 'w') as outfile:
                json.dump({'token': 'insert_token_here'}, outfile)
            sys.exit(1)

if __name__ == '__main__':
    try:
        alfred = Bot()
        
        schedule.every().day.at("08:30").do(alfred.notify_all)
        # alfred.notify_all()
        # schedule.every().minute.do(alfred.notify_all)

        print('listening...')
        while True:
            schedule.run_pending()
            time.sleep(30)
            time_of_next_run = schedule.next_run()
            time_now = datetime.now()
            time_remaining = time_of_next_run - time_now
            print(f'Next notification in: {time_remaining}')
    except KeyboardInterrupt:
        alfred.save()
    except telepot.exception.TelegramError:
        print('Another instance of the same bot is running')
    except Exception as e:
        print(e)
