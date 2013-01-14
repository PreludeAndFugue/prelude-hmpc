#!/usr/bin/env python

import webapp2
import logging
from google.appengine.api import mail
#from markupsafe import escape

from handler import BaseHandler
from model import Photo, Comment


class PhotoView(BaseHandler):
    def get(self, photo_id=0):
        '''View a photograph'''
        user_id, user = self.get_user()

        photo_id = int(photo_id)
        #photo = Photo.get_by_id(photo_id)
        photo = self.get_photo(photo_id)

        if not photo:
            data = {
                'page_title': 'Error',
                'user': user,
                'error_msg': 'Could not find photograph.'
            }
            self.render('error.html', **data)
            return

        #logging.info(dir(Comment.photo_comments(photo)))

        data = {
            'page_title': 'Photo',
            'page_subtitle': photo.title,
            'user': user,
            'userid': user_id,
            'photoid': photo_id,
            'comp_closed': photo.position is not None,
            'url': photo.url(),
            'title': photo.title,
            'comments': list(Comment.photo_comments(photo))
        }
        self.render('photo.html', **data)

    def post(self, photo_id=0):
        '''Adding a new comment to a photo.'''
        user_id, user = self.get_user()
        if not user:
            self.redirect('/')
            return

        photo_id = int(photo_id)
        comment = self.request.get('comment-text')
        #comment = escape(comment)

        logging.info(user_id)
        logging.info(photo_id)
        logging.info(comment)

        photo = Photo.get_by_id(photo_id)
        new_comment = Comment(
            photo=photo,
            user=user,
            text=comment
        )
        new_comment.put()

        # need to clear cache of recent comments
        self.delete_cache_recent_comments()

        # send an email to the photographer, letting them know of the new
        # comment
        to = '{} <{}>'.format(photo.user.username, photo.user.email)
        subject = 'HMPC: New photograph comment'
        body = (
            'You have received a new comment on one of your photographs.'
            '\n\n'
            'From: {}\n\n'
            '{}'  # comment
            '\n\n'
            "The following link will take you to your photograph's page.\n"
            'http://prelude-hmpc.appspot.com/photo/{}'
        )
        body = body.format(user.username, comment, photo_id)
        logging.info(body)
        mail.send_mail('gdrummondk@gmail.com', to, subject, body)

        self.redirect(self.request.path)

routes = [
    (r'/photo/(\d+)', PhotoView),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
