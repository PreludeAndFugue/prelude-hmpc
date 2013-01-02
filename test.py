#!/usr/bin/env python

from datetime import date
from itertools import product
from glob import glob
from google.appengine.api import files
from google.appengine.ext.blobstore import delete as delete_blob
import os
from random import randint
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
            comps = self._create_competition()
            photos = self._upload_photos(users, comps)
            self._create_scores(users, comps, photos)
        else:
            self._delete_all()
        self.redirect('/')

    def _create_users(self):
        data = (
            # username, email, password, verified, admin
            ('foo', 'foo@foo.com', 'foo', True, True),
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
        comp1 = Competition(title='May photographs', year=2012, month=5,
                start=date(2012, 5, 1), end=date(2012, 5, 31))
        comp1.status = 2
        comp1.put()
        comp2 = Competition(title='June photographs', year=2012, month=6,
                start=date(2012, 6, 1), end=date(2012, 6, 30))
        comp2.status = 1
        comp2.put()
        return (comp1, comp2)

    def _upload_photos(self, users, comps):
        d = os.getcwd()
        d = os.path.join(d, 'test', '*.jpg')
        photos = glob(d)
        titles = ('Mars', 'Finnish Flag', 'Hospital in the distance', '', '', '')
        comp1 = comps[0]

        # collect Photo instances here
        p = []
        all_data = zip(product(users, comps), photos, titles)
        for (user, comp), photo_path, title in all_data:
            file_name = files.blobstore.create(mime_type='application/jpeg')
            with files.open(file_name, 'a') as f:
                f.write(open(photo_path, 'rb').read())
            files.finalize(file_name)
            blob_key = files.blobstore.get_blob_key(file_name)

            photo = Photo(
                user=user,
                competition=comp,
                blob=blob_key,
                title=title
            )
            photo.put()
            p.append(photo)
            user_comp = UserComp(user=user, comp=comp)
            if comp == comp1:
                user_comp.submitted_scores = True
            user_comp.put()
        return p

    def _create_scores(self, users, comps, photos):
        # the first of the two competitions is complete
        comp = comps[0]
        scores = []
        for photo, user in product(photos, users):
            if photo.competition != comp or photo.user == user:
                continue
            score = Scores(photo=photo, user_from=user, score=randint(1, 10))
            score.put()
            scores.append(score)

        # calculate total scores
        results = []
        for photo in Photo.competition_photos(comp):
            total_score = Scores.photo_score(photo)
            results.append((total_score, photo))
        results.sort(reverse=True)

        # calculate positions
        position = 1
        prev_score = 1000000
        for i, (score, photo) in enumerate(results, start=1):
            if score != prev_score:
                position = i
            #full_results.append((position, score, photo))
            photo.position = position
            photo.total_score = score
            photo.put()
            prev_score = score

    def _delete_all(self):
        for base in (Competition, UserComp, Scores):
            for item in base.all():
                item.delete()
        for photo in Photo.all():
            delete_blob(photo.blob.key())
            photo.delete()
        for user in User.gql('WHERE username != :1', 'test'):
            user.delete()


app = webapp2.WSGIApplication([('/_admin', Test)], debug=True)
