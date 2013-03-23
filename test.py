#!/usr/bin/env python

'''Creating test data.'''

from datetime import date
from itertools import product
from glob import glob
from google.appengine.api import files
from google.appengine.ext.blobstore import delete as delete_blob
import os
from random import randint
import webapp2
from webapp2_extras.security import generate_password_hash

import logging

from handler import BaseHandler
from model import Competition, User, Photo, UserComp, Scores, Comment


class Test(BaseHandler):
    def get(self):
        user_id, user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')
            return

        self.render('_admin.html')

    def post(self):
        delete = self.request.get('delete')

        if not delete:
            users = self._create_users()
            comps = self._create_competitions()
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
            user = User(
                username=name,
                email=email,
                password=hash_pass,
                verified=verified,
                admin=admin
            )
            user.put()
            users.append(user)
        return users

    def _create_competitions(self):
        comp1 = Competition(
            title='May photographs',
            description='',
            year=2012,
            month=5,
            start=date(2012, 5, 1),
            end=date(2012, 5, 31),
            finished=True,
            status=2
        )
        comp1.put()
        comp2 = Competition(
            title='June photographs',
            description='',
            year=2012,
            month=6,
            start=date(2012, 6, 1),
            end=date(2012, 6, 30),
            finished=False,
            status=1
        )
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
            file_name = files.blobstore.create(mime_type='image/jpeg')
            with files.open(file_name, 'a') as f:
                f.write(open(photo_path, 'rb').read())
            files.finalize(file_name)
            blob_key = files.blobstore.get_blob_key(file_name)

            photo = Photo(
                user=user.key,
                competition=comp.key,
                blob=blob_key,
                title=title
            )
            photo.put()
            p.append(photo)
            user_comp = UserComp(user=user.key, comp=comp.key)
            if comp == comp1:
                user_comp.submitted_scores = True
            user_comp.put()
        return p

    def _create_scores(self, users, comps, photos):
        # the first of the two competitions is complete
        comp = comps[0]
        comp_photos = [p for p in photos if p.competition == comp.key]
        logging.info(comp)
        logging.info(photos)
        logging.info(comp_photos)
        scores = []
        for photo, user in product(comp_photos, users):
            if photo.user.get() == user:
                continue
            score = Scores(
                photo=photo.key,
                user_from=user.key,
                score=randint(1, 10)
            )
            logging.info(score)
            score_key = score.put()
            logging.info(score_key)
            scores.append(score)

        # calculate total scores
        results = []
        for photo in comp_photos:
            logging.info(photo)
            total_score = 0
            for score in scores:
                if score.photo == photo.key:
                    total_score += score.score
            logging.info('total score: %s' % total_score)
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
        for base in (Competition, UserComp, Scores, Comment):
            for item in base.query():
                item.key.delete()
        for photo in Photo.query():
            delete_blob(photo.blob)
            photo.key.delete()
        for user in User.gql('WHERE username != :1', 'test'):
            user.key.delete()


app = webapp2.WSGIApplication([('/_admin', Test)], debug=True)
