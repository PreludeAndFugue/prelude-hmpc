#!/usr/bin/env python

import webapp2
import logging
from google.appengine.api import mail

from handler import BaseHandler
from helper import OPEN
from model import Photo, Comment, UserComp


class PhotoView(BaseHandler):
    def get(self, photo_id=0):
        '''View a photograph'''
        user_id, user = self.get_user()

        photo_id = int(photo_id)
        photo = Photo.get_by_id(photo_id)

        logging.info('exif data: %s' % photo.exif())

        if not photo:
            data = {
                'page_title': 'Error',
                'user': user,
                'error_msg': 'Could not find photograph.'
            }
            self.render('error.html', **data)
            return

        open_comp = photo.competition.get().status == OPEN
        # is this a photo of the logged-in user - a user can always view
        # their own photos
        user_photo = photo.user == user.key if user else False

        if open_comp and not user_photo:
            msg = (
                'You cannot view pictures in competitions which are still '
                'open to submissions.'
            )
            data = {
                'page_title': 'Cannot view picture',
                'user': user,
                'error_msg': msg
            }
            self.render('error.html', **data)
            return

        data = {
            'page_title': 'Photo',
            'page_subtitle': photo.title,
            'user': user,
            'userid': user_id,
            'photoid': photo_id,
            'comp_closed': photo.position != 0,
            'url': photo.url(),
            'title': photo.title,
            'comments': list(Comment.photo_comments(photo))
        }
        data.update(photo.exif())
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

        logging.info(photo_id)

        photo = Photo.get_by_id(photo_id)
        new_comment = Comment(
            photo=photo.key,
            user=user.key,
            text=comment
        )
        new_comment.put()

        # send an email to the photographer, letting them know of the new
        # comment
        photo_user = photo.user.get()
        to = '{} <{}>'.format(photo_user.username, photo_user.email)
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


class PhotoDelete(BaseHandler):
    '''Delete photographs.

    Only when the photograph belongs to an open competition. The photograph
    can be deleted by the owner or an administrator.

    Items to delete
    ---------------
    photo
    UserComp record

    Shouldn't be any comments to delete for a photo in an open competition.
    '''
    def get(self, photo_id):
        photo_id = int(photo_id)
        data, error = self._check(photo_id)

        if error:
            self.render('error.html', **data)
            return

        self.render('photo-delete.html', **data)

    def post(self, photo_id):
        photo_id = int(photo_id)
        data, error = self._check(photo_id)

        if error:
            self.render('error.html', **data)
            return

        # delete photo here
        #user = data['user']
        comp = data['comp']
        photo = data['photo']
        photo_user = photo.user.get()
        user_comp = UserComp.get_usercomp(photo_user, comp)

        photo.key.delete()
        user_comp.key.delete()

        referrer = str(self.request.get('referrer'))
        self.redirect(referrer)

    def _check(self, photo_id):
        '''Helper method which checks the proper permissions for deleting the
        photograph.'''
        user_id, user = self.get_user()
        if not user:
            self.redirect('/')

        referrer = self.request.referrer
        data = {
            'page_title': 'Delete Photograph',
            'user': user,
            'referrer': referrer if referrer else '/',
        }

        photo = Photo.get_by_id(photo_id)
        if not photo:
            data['error_msg'] = "Photograph doesn't exist."
            return data, True

        comp = photo.competition.get()
        if comp.status != OPEN:
            error_msg = "Can only delete a photograph from an open competition."
            data['error_msg'] = error_msg
            return data, True

        photo_user = photo.user.id()
        if not user.admin and user_id != photo_user:
            error_msg = "You don't have permission to delete this photograph."
            data['error_msg'] = error_msg
            return data, True

        # no errors
        data['photo'] = photo
        data['url'] = photo.url(400)
        data['title'] = photo.title
        data['comp'] = comp
        return data, False

routes = [
    (r'/photo/(\d+)', PhotoView),
    (r'/photo/delete/(\d+)', PhotoDelete)
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
