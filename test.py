#!/usr/bin/env python

from datetime import date
from glob import glob
from google.appengine.api import files
from google.appengine.ext.blobstore import delete as delete_blob
import os
import webapp2
from webapp2_extras.security import generate_password_hash

from handler import BaseHandler
from model import Competition, User, Photo, UserComp, Scores

class Test(BaseHandler):
    def get(self):
        user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')
            return

        self.render('_admin.html')

    def post(self):
        delete = self.request.get('delete')

        if not delete:
            users = self._create_users()
            comp = self._create_competition()
            self._upload_photos(users, comp)
        else:
            self._delete_all()
        self.redirect('/')

    def _create_users(self):
        data = (
            # username, email, password, verified, admin
            ('foo1', 'foo@foo.com', 'foo1', True, True),
            ('bar', 'bar@bar.com', 'bar', True, False),
            ('baz', 'baz@baz.com', 'baz', True, False)
        )
        users = []
        for name, email, password, verified, admin in data:
            hash_pass = generate_password_hash(password)
            user = User(username=name, email=email, password=hash_pass,
                verified=verified, admin=admin)
            user.put()
            users.append(user)
        return users

    def _create_competition(self):
        comp = Competition(title='May photographs', year=2012, month=5,
                start=date(2012, 5, 1), end=date(2012, 5, 31))
        comp.put()
        return comp

    def _upload_photos(self, users, comp):
        d = os.getcwd()
        d = os.path.join(d, 'test', '*.jpg')
        photos = glob(d)

        for user, photo_path in zip(users, photos):
            file_name = files.blobstore.create(mime_type='application/jpeg')
            with files.open(file_name, 'a') as f:
                f.write(open(photo_path, 'rb').read())
            files.finalize(file_name)
            blob_key = files.blobstore.get_blob_key(file_name)

            photo = Photo(user=user, competition=comp, blob=blob_key)
            photo.put()
            user_comp = UserComp(user=user, comp=comp)
            user_comp.put()

    def _delete_all(self):
        for base in (Competition, UserComp, Scores):
            for item in base.all():
                item.delete()
        for photo in Photo.all():
            delete_blob(photo.blob.key())
            photo.delete()
        for user in User.gql('WHERE username != :1', 'foo'):
            user.delete()


app = webapp2.WSGIApplication([('/_admin', Test)],
                              debug=True)