#!/usr/bin/env python

import webapp2

from handler import BaseHandler
from model import (
    Photo,
    blob_exif,
)


class Comments(BaseHandler):
    def get(self):
        user_id, user = self.get_user()

        if not user or not user.admin:
            self.redirect('/')
            return

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


class ExifData(BaseHandler):
    def get(self, photo_id=0):
        user_id, user = self.get_user()

        if not user or not user.admin:
            self.redirect('/')
            return

        photo_id = int(photo_id)
        if photo_id == 0:
            photos = list(Photo.query().fetch())
        else:
            photo = Photo.get_by_id(photo_id)
            if not photo:
                data = {
                    'user': user,
                    'page_title': 'Exif data - no such photo',
                    'message': 'no photo exists with this id',
                }
                self.render('error.html', **data)
            photos = [photo]

        results = []
        for photo in photos:
            exif = blob_exif(photo.blob)
            results.append((
                photo,
                exif,
            ))
            photo.populate(**exif)
            photo.put()

        data = {
            'user': user,
            'page_title': 'Exif data extractor',
            'photos': results,
        }

        self.render('help/exif.html', **data)


routes = [
    (r'/help/comments', Comments),
    #(r'/help/exif', ExifData),
    (r'/help/exif/(\d+)', ExifData),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
