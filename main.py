#!/usr/bin/env python

import jinja2
import webapp2
import os

from handler import BaseHandler
from model import Competition, User, Photo

class Home(BaseHandler):
    def get(self):
        data = {
            'page_title': 'Home',
            'user': self.get_user()
        }
        self.render('home.html', **data)

app = webapp2.WSGIApplication([('/', Home)],
                              debug=True)
