#!/usr/bin/env python

from random import shuffle
import webapp2

from handler import BaseHandler
from model import Photo


class Home(BaseHandler):
    def get(self):
        user = self.get_user()
        data = {
            'page_title': 'Monthly Photographs 2013',
            'photos': self.random_images(4),
            'user': user
        }
        self.render('home.html', **data)

    def random_images(self, number=3):
        photo_keys = list(Photo.all(keys_only=True))
        shuffle(photo_keys)
        photos = []
        for i, key in enumerate(photo_keys[:number]):
            photo = Photo.get(key)
            title = photo.title
            if not title:
                title = 'Untitled'
            user = photo.user.username
            photos.append((i, key.id(), photo.url(size=1600), title, user))
        return photos

app = webapp2.WSGIApplication([('/', Home)], debug=True)
