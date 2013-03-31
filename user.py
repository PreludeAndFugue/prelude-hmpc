#!/usr/bin/env python

from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
import webapp2

import logging

from handler import BaseHandler
from model import User, Photo, UserComp, Competition, blob_exif
from helper import MONTHS, OPEN, MAX_EXTRA_PHOTO


class UserView(BaseHandler):
    def get(self, user_view_id):
        # logged in user
        user_id, user = self.get_user()
        # user's page
        user_view_id = int(user_view_id)
        user_view = User.get_by_id(user_view_id)
        my_page = user == user_view if user else False

        if not user_view:
            data = {
                'user': user,
                'page_title': 'Error',
                'error_msg': 'Cannot find User',
            }
            self.render('error.html', **data)
            return

        if my_page:
            photos = Photo.user_photos(user)
            need_scores = list(user.scoring_competitions())
            need_photos = self._competitions_need_photos(user)
        else:
            photos = Photo.user_photos_complete(user_view)
            need_scores = []
            need_photos = []
        extra_photos = Photo.extra_photos(user_view)

        data = {
            'page_title': 'User',
            'page_subtitle': user_view.username,
            'user': user,
            'user_view': user_view,
            'my_page': my_page,
            'need_scores': need_scores,
            'need_photos': need_photos,
            'photos': photos,
            'extra_photos': extra_photos,
            'upload_extra': (user.extra_photo_count < MAX_EXTRA_PHOTO
            if user else False),
            'max_extra_photos': MAX_EXTRA_PHOTO,
            'months': MONTHS,
            'upload_url': blobstore.create_upload_url('/upload'),
            'upload_extra_url': blobstore.create_upload_url('/upload'),
        }

        self.render('user-view.html', **data)

    def _competitions_need_photos(self, user):
        '''Return a list of all competitions for which the user can submit a
        photograph.'''
        submissions = []
        for comp in Competition.get_by_status(OPEN):
            usercomp = UserComp.get_usercomp(user, comp)
            if not usercomp:
                submissions.append(comp)
        return submissions

    def post(self):
        pass


class Upload(BaseHandler, blobstore_handlers.BlobstoreUploadHandler):
    def get(self):
        self.redirect('/')

    def post(self):
        user_id, user = self.get_user()
        #user_id, username = self.get_cookie()
        extra_photo = int(self.request.get('is_photo_extra', '0'))
        if extra_photo:
            upload_files = self.get_uploads('photo-extra-submit')
        else:
            upload_files = self.get_uploads('photo-submit')

        if not upload_files:
            data = {
                'user': user,
                'page_title': 'Upload error',
                'error': 'You forgot to select an image file.'
            }
            self.render('upload_error.html', **data)
            return

        blob_info = upload_files[0]

        if blob_info.content_type != 'image/jpeg':
            # only store jpegs - delete file otherwise
            blob_info.delete()
            data = {
                'user': user,
                'public_profile': True,
                'page_title': 'Upload error',
                'error': (
                    'You tried to upload a file which was '
                    'not a jpeg image.'
                )
            }
            self.render('upload_error.html', **data)
            return

        if extra_photo:
            if blob_info.size > 512 * 1024:
                # only store jpegs - delete file otherwise
                blob_info.delete()
                data = {
                    'user': user,
                    'public_profile': True,
                    'page_title': 'Upload error',
                    'error': (
                        'You tried to upload a file which was '
                        'larger than 512kB.'
                    )
                }
                self.render('upload_error.html', **data)
                return
            extra_data = self._extra_photo(user)
        else:
            extra_data = self._comp_photo(user)

        photo_data = {
            'user': user.key,
            'blob': blob_info.key(),
        }

        exif = blob_exif(blob_info.key())
        photo_data.update(exif)
        photo_data.update(extra_data)

        # add photo details to database
        photo = Photo(**photo_data)
        photo.put()
        logging.info('new photo: %s' % photo)

        self.redirect('/user/%d' % user_id)

    def _extra_photo(self, user):
        photo_title = self.request.get('photo-extra-title')
        month = int(self.request.get('photo-extra-month'))
        user.extra_photo_count += 1
        user.put()
        return {'month': month, 'title': photo_title}

    def _comp_photo(self, user):
        photo_title = self.request.get('photo-title')
        comp_id = int(self.request.get('comp-id'))
        comp = Competition.get_by_id(comp_id)
        usercomp = UserComp(user=user.key, comp=comp.key)
        usercomp.put()
        return {'competition': comp.key, 'title': photo_title}


class UserViewEdit(BaseHandler):
    def get(self):
        user_id, user = self.get_user()
        if not user:
            self.redirect('/')
            return

        data = {
            'page_title': 'Edit Public Profile',
            'user': user,
        }

        self.render('user-view-edit.html', **data)

    def post(self):
        user_id, user = self.get_user()
        if not user:
            self.redirect('/')
            return

        bio = self.request.get('bio')
        user.bio = bio
        user.put()

        self.redirect('/user/%d' % user_id)

routes = [
    (r'/user/(\d+)', UserView),
    (r'/upload', Upload),
    (r'/user/edit', UserViewEdit),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
