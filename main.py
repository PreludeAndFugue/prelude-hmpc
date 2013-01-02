#!/usr/bin/env python

import webapp2

from handler import BaseHandler


class Home(BaseHandler):
    def get(self):
        #data = {
        #    'page_title': 'Home',
        #    'user': self.get_user()
        #}
        self.redirect('/competitions')
        #self.render('home.html', **data)

app = webapp2.WSGIApplication([('/', Home)], debug=True)
