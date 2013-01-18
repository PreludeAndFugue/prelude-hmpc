
from google.appengine.ext import ndb
#from google.appengine.ext import db
from google.appengine.api.images import get_serving_url

import csv
import logging
import StringIO

# the maximum length of the longest dimension of on uploaded photo
MAX_SIZE = 800


class User(ndb.Model):
    username = ndb.StringProperty(required=True)
    password = ndb.StringProperty(required=True)
    email = ndb.StringProperty(required=True)
    verified = ndb.BooleanProperty(default=False)
    verify_code = ndb.StringProperty()
    admin = ndb.BooleanProperty(default=False)
    pass_reset_code = ndb.StringProperty()
    pass_reset_expire = ndb.DateTimeProperty()

    @classmethod
    def user_from_name(cls, name):
        '''Return the user from the name attribute.'''
        logging.warning('Getting user object from username: %s' % repr(name))
        query = cls.query(cls.username == name)
        return query.get()

    @classmethod
    def user_from_email(cls, email):
        '''Return the user from the email attribute.'''
        query = cls.query(cls.email == email)
        return query.get()

    @classmethod
    def user_from_reset_code(cls, reset_code):
        query = cls.query(cls.pass_reset_code == reset_code)
        return query.get()

    def __eq__(self, other):
        '''Compare to users for equality.'''
        return self.username == other.username

    def __str__(self):
        params = (self.username, self.email, self.verified, self.admin)
        return 'User(%s, %s, verified=%s, admin=%s)' % params


class Competition(ndb.Model):
    title = ndb.StringProperty(required=True)
    description = ndb.TextProperty()
    year = ndb.IntegerProperty(required=True)
    month = ndb.IntegerProperty(required=True)
    start = ndb.DateProperty(required=True)
    # the closing date for the competition
    end = ndb.DateProperty(required=True)
    finished = ndb.BooleanProperty(default=False)
    status = ndb.IntegerProperty(default=0)
    challenge = ndb.BooleanProperty(default=False)

    @classmethod
    def all(cls):
        '''Return all competitions, newest first.'''
        query = cls.query()
        query = query.order(-Competition.start)
        return query

    @classmethod
    def get_by_title_date(cls, title, month, year):
        '''Return competition based on title, month and year.'''
        query = cls.query(
            cls.title == title,
            cls.month == month,
            cls.year == year
        )
        return query.get()

    @classmethod
    def get_by_status(cls, status):
        '''Return all competitions based on their status.'''
        query = cls.query(cls.status == status)
        return query

    @classmethod
    def in_progress(cls):
        '''Return all competitions that are Open or Scoring.'''
        query = cls.query(cls.finished == False)
        query = query.order(-cls.start)
        return query

    def get_status(self):
        '''Return the status of the competition as a meaningful str.'''
        return {0: 'Open', 1: 'Scoring', 2: 'Completed'}[self.status]

    def users(self):
        '''Return a list of users in competition.'''
        query = UserComp.query(UserComp.comp_key == self.key)
        return query

    def __eq__(self, other):
        '''Compare competitions for equality.'''
        #logging.info('compare comps: %r, %r', self, other)
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


class UserComp(ndb.Model):
    '''Keep track of the users who have submitted photos to competitions.
    When a user submits a photo to a competition a record is added to this
    class. This class is used to tell if a user can submit scores to a
    competition - only when they have submitted photo to competition. And if
    they have submitted scores during the scoring phase of the competition.'''
    user_key = ndb.KeyProperty(kind=User, required=True)
    comp_key = ndb.KeyProperty(kind=Competition, required=True)
    submitted_scores = ndb.BooleanProperty(default=False)

    @classmethod
    def get_usercomp(cls, user, comp):
        '''Return details about a user's participation in a competition.'''
        query = cls.query(cls.user_key == user.key, cls.comp_key == comp.key)
        return query.get()

    @classmethod
    def all_scores_submitted(cls, comp):
        '''Have all scores been submitted for a competition.'''
        query = cls.query(cls.comp_key == comp.key)
        return all(r.submitted_scores for r in query)


class Photo(ndb.Model):
    user_key = ndb.KeyProperty(kind=User, required=True)
    comp_key = ndb.KeyProperty(kind=Competition)  # required=True)
    title = ndb.StringProperty()
    blob = ndb.BlobKeyProperty(required=True)
    upload_date = ndb.DateTimeProperty(auto_now_add=True)
    position = ndb.IntegerProperty(default=0)
    total_score = ndb.IntegerProperty(default=0)

    @classmethod
    def user_photos(cls, user, limit=None):
        '''Return all photos of a user.'''
        query = cls.query(cls.user_key == user.key)
        query = query.order(cls.upload_date)
        return query.fetch(limit=limit)

    @classmethod
    def competition_photos(cls, competition):
        '''Return all photos entered into a competition.'''
        query = cls.query(cls.comp_key == competition.key)
        query = query.order(-cls.total_score)
        return query

    @classmethod
    def competition_result(cls, competition):
        '''Return all photos entered in a competition and order by total score
        descending.'''
        query = cls.query(cls.comp_key == competition.key)
        query = query.order(-cls.total_score)
        return query

    @classmethod
    def competition_user(cls, competition, user):
        '''Return the photo entered by user into competition.'''
        query = cls.query(
            cls.comp_key == competition.key,
            cls.user_key == user.key
        )
        return query

    def scores(self):
        '''Return a collection of all the scores for this photo as Scores
        objects.'''
        query = Scores.query(Scores.photo_key == self.key)
        return query

    def data(self, size=211):
        '''Return information about photo and urls for image and thumb.'''
        title = self.title if self.title else 'Untitled'
        url = get_serving_url(self.blob, size=MAX_SIZE)
        thumb = get_serving_url(self.blob, size=size, crop=True)
        date = self.upload_date.strftime('%d %B, %Y')
        position = self.position if self.position is not None else ''
        score = self.total_score if position != '' else ''
        comp_title = self.comp_key.get().title
        return title, url, thumb, date, position, score, comp_title

    def thumb(self, size=211):
        return get_serving_url(self.blob, size=size, crop=True)

    def url(self, size=MAX_SIZE):
        return get_serving_url(self.blob, size=size)


class Comment(ndb.Model):
    photo_key = ndb.KeyProperty(kind=Photo, required=True)
    user_key = ndb.KeyProperty(kind=User, required=True)
    submit_date = ndb.DateTimeProperty(auto_now_add=True)
    text = ndb.TextProperty()

    @classmethod
    def photo_comments(cls, photo):
        query = cls.query(cls.photo_key == photo.key)
        query = query.order(cls.submit_date)
        for comment in query:
            yield (
                comment.text,
                comment.user_key.get().username,
                comment.format_date()
            )

    @classmethod
    def user_comments(cls, user):
        query = cls.query(cls.user_key == user.key)
        query = query.order(-cls.submit_date)
        return query

    @classmethod
    def recent_comments(cls, limit=5):
        query = cls.query()
        query = query.order(-cls.submit_date)
        return query.fetch(limit)

    def format_date(self):
        '''Format the stored submit date for pretty printing.'''
        return self.submit_date.strftime('%H:%M, %d-%b-%Y')


class Scores(ndb.Model):
    photo_key = ndb.KeyProperty(kind=Photo, required=True)
    user_from_key = ndb.KeyProperty(kind=User, required=True)
    score = ndb.IntegerProperty(required=True)

    @classmethod
    def photo_score(cls, photo):
        '''Return the total score for a photo.'''
        query = cls.query(cls.photo_key == photo.key)
        return sum(s.score for s in query)

    @classmethod
    def score_from_user(cls, photo, user):
        '''Return the score submitted by a user for a particular photo.'''
        query = cls.query(
            cls.photo_key == photo.key,
            cls.user_from_key == user.key
        )
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
    comps = Competition.query(Competition.finished == True)
    comps = comps.order(-Competition.start)
    for comp in comps.fetch(2):
        logging.info('recently_completed_competitions comp: %s', comp)
        # only the top three results
        photos = list(Photo.competition_photos(comp))[:3]
        results.append((comp, photos))
    return results
