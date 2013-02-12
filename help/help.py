#!/usr/bin/env python

import logging
import webapp2

from handler import BaseHandler
from model import (
    Photo,
    Competition,
    Comment,
    Note,
    recently_completed_competitions,
)


class Comments(BaseHandler):
    def get(self):
        user_id, user = self.get_user()

        if not user or not user.admin:
            self.redirect('/')

        photos = list(Photo.query().fetch())
        for photo in photos:
            comment_count = len(list(photo.comments()))
            photo.comment_count = comment_count
            photo.put()

        data = {
            'user': user,
            'page_title': 'Helps',
            'photos': photos,
        }

        self.render('help/comments.html', **data)


routes = [
    (r'/help/comments', Comments),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
