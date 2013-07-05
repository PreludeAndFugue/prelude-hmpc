#!/usr/bin/env python

'''Photos: viewing, deleting and exporting data from the model.'''

import webapp2
import logging
from google.appengine.api import mail
from google.appengine.runtime.apiproxy_errors import OverQuotaError

from handler import BaseHandler
from helper import OPEN, COMPLETED
from model import Photo, Comment, UserComp, csv_photos


class PhotoView(BaseHandler):
    def get(self, photo_id=0):
        '''View a photograph'''
        user_id, user = self.get_user()

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

        can_view = self._can_view_photo(photo, user)
        if not can_view:
            msg = (
                'You cannot view pictures in competitions which are not '
                'finished.'
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
            'can_comment': self._can_comment(user, photo),
            'delete_my_photo': self._can_delete(user, photo),
            'url': photo.url(),
            'title': photo.title,
            'comments': list(Comment.photo_comments(photo))
        }
        data.update(photo.exif())
        self.render('photo.html', **data)

    def _can_view_photo(self, photo, user):
        '''Check to see if the photo can be viewed.'''
        # all extra photos can be viewed
        if not photo.competition:
            return True
        # all photos in completed competitons can be viewed
        if photo.competition.get().status == COMPLETED:
            return True
        # a user can view all their own photos at any time
        if user and photo.user == user.key:
            return True
        return False

    def _can_comment(self, user, photo):
        if not user:
            return False
        comp = photo.competition
        if comp is None:
            return True
        if comp.get().status == COMPLETED:
            return True
        return False

    def _can_delete(self, user, photo):
        '''A user can delete their own extra photos.'''
        if not user:
            return False
        extra_photo = photo.competition is None
        if not extra_photo:
            return False
        my_photo = photo.user == user.key
        if not my_photo and not user.admin:
            return False
        return True

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

        # keep track of the total number of comments
        photo.comment_count += 1
        photo.put()

        # send an email to the photographer and commentators, letting them
        # know of the new comment
        to = self._email_addresses(photo)
        logging.info('New comment. email addresses: %s' % ', '.join(to))
        body = (
            'Someone has made a comment on a photograph.'
            '\n\n'
            'From: {}\n\n'
            '{}'  # comment
            '\n\n'
            "The following link will take you to the photograph's page.\n"
            'http://prelude-hmpc.appspot.com/photo/{}'
        )
        body = body.format(user.username, comment, photo_id)

        try:
            email = mail.EmailMessage(
                sender='HMPC Bot <gdrummondk@gmail.com>',
                subject='HMPC: New photograph comment',
                bcc=to,
                body=body
            )
            email.send()
        except OverQuotaError, msg:
            logging.error(msg)
            # send a message to admin (me) then I can forward to users
            new_body = body + '\n\nSend to:\n' + ', '.join(to)
            mail.send_mail_to_admins(
                sender='HMPC Bot <gdrummondk@gmail.com>',
                subject='HMPC: New photograph comment (over quota)',
                body=new_body
            )

        self.redirect(self.request.path)

    def _email_addresses(self, photo):
        '''Return a list of email addresses for everyone who has made
        a comment for a photo.'''
        addresses = []
        for commentator in photo.commentators():
            addresses.append(commentator.email)
        return addresses


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

        photo = data['photo']
        photo.delete()

        referrer = str(self.request.get('referrer'))
        if 'photo' in referrer:
            # This photo is being deleted by the user from the photo page. So
            # should redirect them back to their own user page.
            referrer = '/user/%s' % data['userid']
        self.redirect(referrer)

    def _check(self, photo_id):
        '''Helper method which checks the proper permissions for deleting the
        photograph.

        Return
        ------
        data : dict
            Data to be passed to the template.
        error : boolean
            True if user has permission to delete the photo
        '''
        user_id, user = self.get_user()
        if not user:
            self.redirect('/')

        referrer = self.request.referrer
        data = {
            'page_title': 'Delete Photograph',
            'userid': user_id,
            'user': user,
            'referrer': referrer if referrer else '/',
        }

        photo = Photo.get_by_id(photo_id)
        if not photo:
            data['error_msg'] = "Photograph doesn't exist."
            return data, True

        my_photo = user_id == photo.user.id()
        extra_photo = photo.competition is None

        if not extra_photo:
            comp = photo.competition.get()
            if comp.status != OPEN:
                error_msg = "Can only delete a photograph from an open competition."
                data['error_msg'] = error_msg
                return data, True
        else:
            comp = None

        #photo_user = photo.user.id()
        #if not user.admin and user_id != photo_user:
        if not self._user_permission(user, extra_photo, my_photo):
            error_msg = "You don't have permission to delete this photograph."
            data['error_msg'] = error_msg
            return data, True

        # no errors
        data['photo'] = photo
        data['url'] = photo.url(400)
        data['title'] = photo.title
        data['comp'] = comp
        return data, False

    def _user_permission(self, user, extra_photo, my_photo):
        '''Does the user have permission to delete this photo.'''
        # can delete an extra photo if it's your photo
        logging.info('extra: %s, my_photo: %s, admin: %s' %
                    (extra_photo, my_photo, user.admin))
        if user.admin:
            return True
        if extra_photo and my_photo:
            return True
        return False


class PhotoCSV(BaseHandler):
    '''Create a CSV file of all the data in the Photo model.'''
    def get(self):
        user_id, user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')
            return

        logging.info('User: %s downloading photo data' % user.username)
        self.response.content_type = 'text/csv'
        self.write(csv_photos())


routes = [
    (r'/photo/(\d+)', PhotoView),
    (r'/photo/delete/(\d+)', PhotoDelete),
    (r'/photo/photos.csv', PhotoCSV)
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
