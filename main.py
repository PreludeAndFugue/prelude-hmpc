#!/usr/bin/env python

from random import shuffle
import webapp2

from handler import BaseHandler
from helper import MONTHS
from model import Photo, Competition


class Home(BaseHandler):
    def get(self):
        user_id, user = self.get_user()
        data = {
            'page_title': 'Monthly Photographs 2013',
            'photos': self.random_images(4),
            'user': user,
            'competitions': self.competitions_in_progress()
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
            photos.append((i, key.id(), photo.url(size=800), title, user))
        return photos

    def competitions_in_progress(self):
        competition_data = []
        for comp in Competition.in_progress():
            competition_data.append((
                comp.key().id(),
                comp.title,
                comp.description,
                comp.year,
                MONTHS[comp.month],
                comp.get_status()
            ))
        return competition_data

app = webapp2.WSGIApplication([('/', Home)], debug=True)
