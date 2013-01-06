#!/usr/bin/env python

from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
import webapp2

import logging

from handler import BaseHandler
from model import Photo, UserComp
from helper import OPEN, ordinal


class UserPage(BaseHandler):
    def get(self):
        user_id, user = self.get_user()
        if not user:
            self.render('user_no.html', page_title='User')
            return

        #open_comps = Competition.get_by_status(OPEN)
        comps = self.get_competitions()
        open_comps = [c for c in comps if c.status == OPEN]
        open_comps_no_photos = []
        for oc in open_comps:
            usercomp = UserComp.get_usercomp(user, oc)
            if not usercomp:
                open_comps_no_photos.append(oc)

        upload_url = None
        if open_comps_no_photos:
            upload_url = blobstore.create_upload_url('/upload')

        #logging.info(open_comps)
        logging.info(open_comps_no_photos)

        photos = []
        #for p in Photo.user_photos(user):
        for p in self.get_user_photos(user_id):
            title, url, thumb, date, position, score, comp_title = p.data()
            position = '%s place' % ordinal(position) if position else ''
            score = '%d points' % score if score else ''
            photos.append((
                p.key().id(),
                title,
                url,
                thumb,
                date,
                position,
                score,
                comp_title
            ))

        #logging.info(comp_photo)

        data = {
            'user': user,
            'page_title': 'User',
            'page_subtitle': user.username,
            'upload_url': upload_url,
            'photos': photos,
            'open_comps': open_comps_no_photos,
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
        comp = self.get_competition(comp_id)
        #comp = Competition.get_by_id(comp_id)

        # add photo details to database
        photo = Photo(
            user=user,
            title=photo_title,
            blob=blob_info,
            competition=comp
        )
        photo.put()

        # users photos cache is now stale - delete
        self.delete_cache_user_photos(user_id)
        # comp photos cache is now stale - delete
        self.delete_cache_competition_photos(comp_id)

        # add UserComp record
        usercomp = UserComp(user=user, comp=comp)
        usercomp.put()

        self.redirect('/user')


routes = [
    ('/user', UserPage),
    ('/upload', Upload),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
