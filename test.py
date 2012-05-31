#!/usr/bin/env python

from datetime import date
import jinja2
import webapp2
import os
from webapp2_extras.security import generate_password_hash

from handler import BaseHandler
from model import Competition, User, Photo

class Test(BaseHandler):
    def get(self):
        user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')
            return

        self.render('_admin.html')

    def post(self):
        self._create_users()
        self._create_competition()
        self.redirect('/')

    def _create_users(self):
        data = (
            # username, email, password, verified, admin
            #('foo', 'foo@foo.com', 'foo', True, True),
            ('bar', 'bar@bar.com', 'bar', True, False),
            ('baz', 'baz@baz.com', 'baz', True, False)
        )
        for name, email, password, verified, admin in data:
            hash_pass = generate_password_hash(password)
            user = User(username=name, email=email, password=hash_pass,
                verified=verified, admin=admin)
            user.put()

    def _create_competition(self):
        comp = Competition(title='May photographs', year=2012, month=5,
                start=date(2012, 5, 1), end=date(2012, 5, 31))
        comp.put()

    def _upload_photos(self):


app = webapp2.WSGIApplication([('/_admin', Test)],
                              debug=True)