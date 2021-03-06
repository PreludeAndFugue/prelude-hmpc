import jinja2
import os
import logging
import webapp2
from webapp2_extras.securecookie import SecureCookieSerializer

from model import User
from secret_key import SECRET

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(template_dir),
    autoescape=True
)


class BaseHandler(webapp2.RequestHandler):

    def initialize(self, request, response):
        super(BaseHandler, self).initialize(request, response)
        # initialise with secret key
        self.cookie_serializer = SecureCookieSerializer(SECRET)

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
            user_cookie = self.cookie_serializer.deserialize(
                'userid',
                user_cookie
            )
            if not user_cookie:
                # invalid cookie signature
                return None, ''
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
            return None, None

        user = User.get_by_id(user_id)
        return user_id, user
