#!/usr/bin/env python

import webapp2
import logging
from markupsafe import escape

from handler import BaseHandler
from model import Photo, Comment, User


class PhotoView(BaseHandler):
    def get(self, photo_id=0):
        '''View a photograph'''
        user = self.get_user()

        photo_id = int(photo_id)
        photo = Photo.get_by_id(photo_id)

        if not photo:
            data = {
                'page_title': 'Error',
                'user': user,
                'error_msg': 'Could not find photograph.'
            }
            self.render('error.html', **data)
            return

        data = {
            'page_title': 'Photo',
            'page_subtitle': photo.title,
            'user': user,
            'userid': user.key().id() if user else 0,
            'photoid': photo.key().id(),
            'url': photo.url(),
            'title': photo.title,
            'comments': Comment.photo_comments(photo)
        }
        self.render('photo.html', **data)

    def post(self, photo_id=0):
        photo_id = int(photo_id)
        user_id = self.request.get('user')
        user_id = int(user_id)
        comment = self.request.get('comment-text')
        comment = escape(comment)
        logging.info(user_id)
        logging.info(photo_id)
        logging.info(comment)

        user = User.get_by_id(user_id)
        photo = Photo.get_by_id(photo_id)
        new_comment = Comment(
            photo=photo,
            user=user,
            text=comment
        )
        new_comment.put()

        self.redirect(self.request.path)

routes = [
    (r'/photo/(\d+)', PhotoView),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
