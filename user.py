#!/usr/bin/env python

from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
import webapp2

import logging

from handler import BaseHandler
from model import User, Photo, UserComp, Competition, blob_exif
from helper import OPEN, ordinal


class UserPage(BaseHandler):
    def get(self):
        user_id, user = self.get_user()
        if not user:
            self.render('user_no.html', page_title='User')
            return

        open_comps = Competition.get_by_status(OPEN)
        #comps = self.get_competitions()
        #open_comps = [c for c in comps if c.status == OPEN]
        #logging.info(open_comps)
        open_comps_no_photos = []
        for oc in open_comps:
            usercomp = UserComp.get_usercomp(user, oc)
            if not usercomp:
                open_comps_no_photos.append(oc)

        upload_url = None
        if open_comps_no_photos:
            upload_url = blobstore.create_upload_url('/upload')

        photos = []
        for p in Photo.user_photos(user):
            title, url, thumb, date, position, score, comp_title = p.data()
            position = '%s place' % ordinal(position) if position else ''
            score = '%d points' % score if score else ''
            photos.append((
                p.key.id(),
                title,
                url,
                thumb,
                date,
                position,
                score,
                comp_title
            ))

        data = {
            'user': user,
            'page_title': 'User',
            'page_subtitle': user.username,
            'upload_url': upload_url,
            'photos': photos,
            'open_comps_no_photos': open_comps_no_photos,
            'need_scores': list(user.scoring_competitions()),
        }
        self.render('user.html', **data)

    def post(self):
        # submitting a photograph - handled by Upload class
        pass


class Upload(BaseHandler, blobstore_handlers.BlobstoreUploadHandler):
    def get(self):
        self.redirect('/user')

    def post(self):
        user_id, user = self.get_user()
        #user_id, username = self.get_cookie()
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

        #logging.info('blob info %s' % dir(blob_info))
        logging.info(blob_info.kind())
        logging.info(blob_info.properties())
        logging.info(blob_info.size)

        if blob_info.content_type != 'image/jpeg':
            # only store jpegs - delete file otherwise
            blob_info.delete()
            data = {
                'user': user,
                'page_title': 'Upload error',
                'error': (
                    'You tried to upload a file which was '
                    'not a jpeg image.'
                )
            }
            self.render('upload_error.html', **data)
            return

        photo_title = self.request.get('photo-title')
        comp_id = int(self.request.get('comp-id'))
        comp = Competition.get_by_id(comp_id)

        exif = blob_exif(blob_info.key())

        # add photo details to database
        photo = Photo(
            user=user.key,
            title=photo_title,
            blob=blob_info.key(),
            competition=comp.key,
            **exif
        )
        photo.put()

        # add UserComp record
        usercomp = UserComp(user=user.key, comp=comp.key)
        usercomp.put()

        self.redirect('/user')


class UserView(BaseHandler):
    def get(self, user_view_id):
        user_id, user = self.get_user()
        user_view_id = int(user_view_id)
        user_view = User.get_by_id(user_view_id)

        if not user_view:
            data = {
                'user': user,
                'page_title': 'Error',
                'error_msg': 'Cannot find User',
            }
            self.render('error.html', **data)
            return

        photos = Photo.user_photos_complete(user_view)

        data = {
            'page_title': 'User',
            'page_subtitle': user_view.username,
            'user': user,
            'user_view': user_view,
            'photos': photos,
        }

        self.render('user-view.html', **data)


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
    (r'/user', UserPage),
    (r'/upload', Upload),
    (r'/user/(\d+)', UserView),
    (r'/user/edit', UserViewEdit),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
