#!/usr/bin/env python

import webapp2
import logging

from handler import BaseHandler
from model import Comment


class CommentEdit(BaseHandler):
    def get(self, comment_id=0):
        '''Edit a comment'''
        user_id, user = self.get_user()
        if not user:
            self.redirect('/')
            return

        comment_id = int(comment_id)
        comment = Comment.get_by_id(comment_id)

        error, data = self._check(user, comment)
        if error:
            self.render('error.html', **data)
            return

        data = {
            'page_title': 'Edit Comment',
            'user': user,
            'userid': user_id,
            'comment': comment,
            'photo_id': comment.photo.id(),
        }
        self.render('comment-edit.html', **data)

    def post(self, comment_id=0):
        '''Updating the comment and redirecting back to the photo page.'''
        user_id, user = self.get_user()
        if not user:
            self.redirect('/')
            return

        comment_id = int(comment_id)
        comment = Comment.get_by_id(comment_id)

        error, data = self._check(user, comment)
        if error:
            self.render('error.html', **data)

        comment_text = self.request.get('comment-text')
        photo_id = int(self.request.get('photo_id'))
        logging.info(comment_text)
        logging.info(photo_id)

        comment.text = comment_text
        comment.put()

        self.redirect('/photo/{}'.format(photo_id))

    def _check(self, user, comment):
        '''Check to make sure comment exists and the user can edit it.'''
        data = {
            'page_title': 'Error',
            'user': user,
        }
        if not comment:
            data['error_msg'] = 'Could not find comment.'
            return True, data

        if comment.user.id() != user.key.id() and not user.admin:
            data['error_msg'] = 'You cannot edit this comment.'
            return True, data

        return False, None

routes = [
    (r'/comment/edit/(\d+)', CommentEdit),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
