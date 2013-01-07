import jinja2
import os
import logging
import webapp2
from webapp2_extras.securecookie import SecureCookieSerializer
from google.appengine.api import memcache

from model import User, Competition, Photo

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

    def render_and_cache(self, key, template, **params):
        page = self.render_str(template, **params)
        memcache.set(key, page)
        self.write(page)

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
            return None, ''

        return self.get_user_from_id(user_id)

    def get_user_from_id(self, user_id):
        '''Bypass accessing cookie since already know the user_id.'''
        key = 'user_{}'.format(user_id)
        user = memcache.get(key)

        logging.info('get_user_from_id memcached user: {}'.format(user))

        if not user:
            user = User.get_by_id(user_id)
            memcache.set(key, user)
            logging.info('get_user_from_id: memcache db access')
        return user_id, user

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

    def get_photo(self, photo_id):
        key = 'photo_{}'.format(photo_id)
        photo = memcache.get(key)
        logging.info('memcached get_photo')
        if not photo:
            photo = Photo.get_by_id(photo_id)
            memcache.set(key, photo)
            logging.info('memcached get_photo db access')
        return photo

    def get_user_photos(self, user_id):
        key = 'photos_user_{}'.format(user_id)
        photos = memcache.get(key)
        logging.info('memcached get_user_photos')
        if not photos:
            user_id, user = self.get_user_from_id(user_id)
            photos = list(Photo.user_photos(user))
            memcache.set(key, photos)
            logging.info('memcached get_user_photos db access')
        return photos

    def delete_cache_user_photos(self, user_id):
        key = 'photos_user_{}'.format(user_id)
        memcache.delete(key)

    def get_competition_photos(self, comp_id, comp=None):
        key = 'photos_comp_{}'.format(comp_id)
        photos = memcache.get(key)
        logging.info('memcached get_comp_photos')
        if not photos:
            comp = comp if comp else self.get_competition(comp_id)
            photos = list(Photo.competition_photos(comp))
            memcache.set(key, photos)
            logging.info('memcached get_comp_photos db access')
        return photos

    def delete_cache_competition_photos(self, comp_id):
        key = 'photos_comp_{}'.format(comp_id)
        memcache.delete(key)

    def get_page_user(self, user_id):
        key = 'page_user_{}'.format(user_id)
        user_page = memcache.get(key)
        return user_page, key

    def delete_cache_page_user(self, user_id):
        key = 'page_user_{}'.format(user_id)
        memcache.delete(key)

    def get_page_competitions(self, user_id=None):
        if user_id is None:
            key = 'page_competitions'
        else:
            key = 'page_competitions_user_{}'.format(user_id)
        competitions_page = memcache.get(key)
        return competitions_page, key

    def delete_cache_page_competitions(self):
        # need to delete all the competitions pages that have been cached
        memcache.delete('page_competitions')

        for user_key in User.all(keys_only=True):
            key = 'page_competitions_user_{}'.format(user_key.id())
            memcache.delete(key)
