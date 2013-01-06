import jinja2
import os
import logging
import webapp2
from webapp2_extras.securecookie import SecureCookieSerializer
from google.appengine.api import memcache

from model import User, Competition

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir),
                               autoescape=True)


class BaseHandler(webapp2.RequestHandler):

    def initialize(self, request, response):
        super(BaseHandler, self).initialize(request, response)
        # initialise with secret key
        secret_key = 'atubetcd483cehbte09otu4'
        self.cookie_serializer = SecureCookieSerializer(secret_key)

    def write(self, *args, **kwgs):
        self.response.out.write(*args, **kwgs)

    def render_str(self, template, **params):
        t = env.get_template(template)
        return t.render(**params)

    def render(self, template, **params):
        self.write(self.render_str(template, **params))

    def get_cookie(self):
        user_cookie = self.request.cookies.get('userid')
        if user_cookie:
            user_cookie = self.cookie_serializer.deserialize('userid', user_cookie)
            user_id, username = user_cookie.split('|')
            user_id = int(user_id)
            return user_id, username
        else:
            return None, ''

    def get_user(self):
        user_id, username = self.get_cookie()
        logging.info('get_user -> {}, {}'.format(user_id, username))
        if not user_id:
            # no logged in user cookie
            return None

        key = 'user_{}'.format(user_id)
        user = memcache.get(key)

        logging.info('get_user memcached user: {}'.format(user))

        if not user:
            user = User.get_by_id(user_id)
            memcache.set(key, user)

            logging.info('get_user: memcache access database')

        return user

    def get_competitions(self):
        key = 'all_comps'
        all_comps = memcache.get(key)

        logging.info('memcached get_competitions')

        if not all_comps:
            all_comps = list(Competition.all().order('-start').run())
            memcache.set(key, all_comps)
            logging.info('memcached get_competitions database access')

        return all_comps

    def delete_cache_competitions(self):
        memcache.delete('all_comps')

    def get_competition(self, comp_id):
        key = 'comp_{}'.format(comp_id)
        comp = memcache.get(key)
        logging.info('memcached get_competition')
        if not comp:
            comp = Competition.get_by_id(comp_id)
            memcache.set(key, comp)
            logging.info('memcached get_competition database access')
        return comp

    def set_competition(self, comp):
        key = 'comp_{}'.format(comp.key().id())
        memcache.set(key, comp)
