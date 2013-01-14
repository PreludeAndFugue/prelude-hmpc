
from google.appengine.ext import db
from google.appengine.ext import blobstore
from google.appengine.api.images import get_serving_url

import csv
import logging
import StringIO

# the maximum length of the longest dimension of on uploaded photo
MAX_SIZE = 800


class User(db.Model):
    username = db.StringProperty(required=True)
    password = db.StringProperty(required=True)
    email = db.StringProperty(required=True)
    verified = db.BooleanProperty(default=False)
    verify_code = db.StringProperty()
    admin = db.BooleanProperty(default=False)

    @classmethod
    def user_from_name(cls, name):
        '''Return the user from the name attribute.'''
        logging.warning('Getting user object from username: %s' % repr(name))
        query = cls.all()
        query.filter('username = ', name)
        return query.get()

    @classmethod
    def user_from_email(cls, email):
        '''Return the user from the email attribute.'''
        query = cls.all()
        query.filter('email = ', email)
        return query.get()

    def __eq__(self, other):
        '''Compare to users for equality.'''
        return self.username == other.username

    def __str__(self):
        params = (self.username, self.email, self.verified, self.admin)
        return 'User(%s, %s, verified=%s, admin=%s)' % params


class Competition(db.Model):
    title = db.StringProperty(required=True)
    description = db.TextProperty()
    year = db.IntegerProperty(required=True)
    month = db.IntegerProperty(required=True)
    start = db.DateProperty(required=True)
    # the closing date for the competition
    end = db.DateProperty(required=True)
    finished = db.BooleanProperty(default=False)
    status = db.IntegerProperty(default=0)
    challenge = db.BooleanProperty(default=False)

    @classmethod
    def get_by_title_date(cls, title, month, year):
        '''Return competition based on title, month and year.'''
        query = cls.all()
        query.filter('title = ', title)
        query.filter('month = ', month)
        query.filter('year = ', year)
        return query.get()

    @classmethod
    def get_by_status(cls, status):
        '''Return all competitions based on their status.'''
        query = cls.all()
        query.filter('status = ', status)
        return query.run()

    @classmethod
    def in_progress(cls):
        '''Return all competitions that are Open or Scoring.'''
        query = Competition.all()
        query.filter('finished = ', False)
        query.order('-start')
        return query.run()

    def get_status(self):
        '''Return the status of the competition as a meaningful str.'''
        return {0: 'Open', 1: 'Scoring', 2: 'Completed'}[self.status]

    def users(self):
        '''Return a list of users in competition.'''
        query = UserComp.all()
        query.filter('comp = ', self)
        return query.run()

    def __eq__(self, other):
        '''Compare competitions for equality.'''
        return (
            self.title == other.title
            and self.year == other.year
            and self.month == other.month
        )

    def __str__(self):
        return 'Competition({}, {}-{}, status={})'.format(
            self.title,
            self.month,
            self.year,
            self.status
        )

    def __repr__(self):
        return self.__str__()


class UserComp(db.Model):
    '''Keep track of the users who have submitted photos to competitions.
    When a user submits a photo to a competition a record is added to this
    class. This class is used to tell if a user can submit scores to a
    competition - only when they have submitted photo to competition. And if
    they have submitted scores during the scoring phase of the competition.'''
    user = db.ReferenceProperty(reference_class=User, required=True)
    comp = db.ReferenceProperty(reference_class=Competition, required=True)
    submitted_scores = db.BooleanProperty(default=False)

    @classmethod
    def get_usercomp(cls, user, comp):
        '''Return details about a user's participation in a competition.'''
        query = cls.all()
        query.filter('user = ', user)
        query.filter('comp = ', comp)
        return query.get()

    @classmethod
    def all_scores_submitted(cls, comp):
        '''Have all scores been submitted for a competition.'''
        query = cls.all()
        query.filter('comp = ', comp)
        return all(r.submitted_scores for r in query.run())


class Photo(db.Model):
    user = db.ReferenceProperty(reference_class=User, required=True)
    competition = db.ReferenceProperty(reference_class=Competition)  # required=True)
    title = db.StringProperty()
    blob = blobstore.BlobReferenceProperty(required=True)
    upload_date = db.DateTimeProperty(auto_now_add=True)
    position = db.IntegerProperty(default=0)
    total_score = db.IntegerProperty(default=0)

    @classmethod
    def user_photos(cls, user, limit=None):
        '''Return all photos of a user.'''
        query = cls.all()
        query.filter('user = ', user)
        query.order('upload_date')
        return query.run(limit=limit)

    @classmethod
    def competition_photos(cls, competition):
        '''Return all photos entered into a competition.'''
        query = cls.all()
        query.filter('competition = ', competition)
        query.order('-total_score')
        return query.run()

    @classmethod
    def competition_result(cls, competition):
        '''Return all photos entered in a competition and order by total score
        descending.'''
        query = cls.all()
        query.filter('competition = ', competition)
        query.order('-total_score')
        return query.run()

    @classmethod
    def competition_user(cls, competition, user):
        '''Return the photo entered by user into competition.'''
        query = cls.all()
        query.filter('competition = ', competition)
        query.filter('user = ', user)
        return query.get()

    def scores(self):
        '''Return a collection of all the scores for this photo as Scores
        objects.'''
        query = Scores.all()
        query.filter('photo = ', self)
        return query.run()

    def data(self, size=211):
        '''Return information about photo and urls for image and thumb.'''
        title = self.title if self.title else 'Untitled'
        url = get_serving_url(self.blob, size=MAX_SIZE)
        thumb = get_serving_url(self.blob, size=size, crop=True)
        date = self.upload_date.strftime('%d %B, %Y')
        position = self.position if self.position is not None else ''
        score = self.total_score if position != '' else ''
        comp_title = self.competition.title
        return title, url, thumb, date, position, score, comp_title

    def thumb(self, size=211):
        return get_serving_url(self.blob, size=size, crop=True)

    def url(self, size=MAX_SIZE):
        return get_serving_url(self.blob, size=size)


class Comment(db.Model):
    photo = db.ReferenceProperty(reference_class=Photo, required=True)
    user = db.ReferenceProperty(reference_class=User, required=True)
    submit_date = db.DateTimeProperty(auto_now_add=True)
    text = db.TextProperty()

    @classmethod
    def photo_comments(cls, photo):
        query = cls.all()
        query.filter('photo = ', photo)
        query.order('submit_date')
        return query.run()

    @classmethod
    def user_comments(cls, user):
        query = cls.all()
        query.filter('user = ', user)
        query.order('-submit_date')
        return query.run()

    @classmethod
    def recent_comments(cls, limit=5):
        query = cls.all()
        query.order('-submit_date')
        return query.fetch(limit)

    def format_date(self):
        '''Format the stored submit date for pretty printing.'''
        return self.submit_date.strftime('%H:%M, %d-%b-%Y')


class Scores(db.Model):
    photo = db.ReferenceProperty(reference_class=Photo, required=True)
    user_from = db.ReferenceProperty(reference_class=User, required=True)
    score = db.IntegerProperty(required=True)

    @classmethod
    def photo_score(cls, photo):
        '''Return the total score for a photo.'''
        query = cls.all()
        query.filter('photo = ', photo)
        return sum(s.score for s in query)

    @classmethod
    def score_from_user(cls, photo, user):
        '''Return the score submitted by a user for a particular photo.'''
        query = cls.all()
        query.filter('photo = ', photo)
        query.filter('user_from = ', user)
        return query.get()


# some functions that don't really fit in any particular model

def user_scores(user):
    scores = []
    for photo in Photo.user_photos(user, limit=None):
        photo_score = sum(Scores.photo_scores(photo))
        scores.append((photo, photo_score))
    return scores


def csv_scores(comp):
    '''Create a csv file for all the scores for a competition.'''
    photos = list(Photo.competition_photos(comp))
    photos.sort(key=lambda p: p.user.username)

    buf = StringIO.StringIO()
    fieldnames = ['Recipient'] + [p.user.username for p in photos]
    data = csv.DictWriter(buf, fieldnames=fieldnames)

    data.writerow(dict((n, n) for n in fieldnames))

    for photo in photos:
        row = {}
        row['Recipient'] = photo.user.username
        for score in photo.scores():
            row[score.user_from.username] = score.score
        data.writerow(row)

    return buf.getvalue()


def recently_completed_competitions():
    results = []
    comps = Competition.all()
    comps.filter('finished = ', True)
    comps.order('-start')
    for comp in comps.fetch(2):
        # only the top three results
        photos = list(Photo.competition_photos(comp))[:3]
        results.append((comp, photos))
    return results
