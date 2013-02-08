
from google.appengine.ext import ndb
#from google.appengine.ext import db
from google.appengine.api.images import get_serving_url
import markdown

from calendar import month_name
import csv
import logging
import StringIO

from helper import SCORING

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

    def scoring_competitions(self):
        '''Return a list of competitions for which the user must submit
        scores.'''
        user_comps = UserComp.query().filter(UserComp.user == self.key)
        for user_comp in user_comps:
            if not user_comp.submitted_scores:
                comp = user_comp.comp.get()
                if comp.status == SCORING:
                    yield (
                        comp.key.id(),
                        comp.title,
                        month_name[comp.month],
                        comp.year
                    )

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
        query = UserComp.query(UserComp.comp == self.key)
        return query

    #@ndb.transactional(xg=True)
    def delete(self):
        '''Delete a competition.

        Items to delete UserComps, Photos, Comments, Scores
        '''
        all_keys = []
        for usercomp in self.users():
            all_keys.append(usercomp.key)
        for photo in Photo.competition_photos(self):
            all_keys.append(photo.key)
            for comment in photo.comments():
                all_keys.append(comment.key)
            for score in photo.scores():
                all_keys.append(score.key)
        all_keys.append(self.key)

        logging.info(all_keys)
        ndb.delete_multi(all_keys)

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
    user = ndb.KeyProperty(kind=User, required=True)
    comp = ndb.KeyProperty(kind=Competition, required=True)
    submitted_scores = ndb.BooleanProperty(default=False)

    @classmethod
    def get_usercomp(cls, user, comp):
        '''Return details about a user's participation in a competition.'''
        query = cls.query(cls.user == user.key, cls.comp == comp.key)
        return query.get()

    @classmethod
    def all_scores_submitted(cls, comp):
        '''Have all scores been submitted for a competition.'''
        query = cls.query(cls.comp == comp.key)
        return all(r.submitted_scores for r in query)

    def __str__(self):
        return 'UserComp({}, {})'.format(self.comp.get(), self.user.get())


class Photo(ndb.Model):
    user = ndb.KeyProperty(kind=User, required=True)
    competition = ndb.KeyProperty(kind=Competition)  # required=True)
    title = ndb.StringProperty()
    blob = ndb.BlobKeyProperty(required=True)
    upload_date = ndb.DateTimeProperty(auto_now_add=True)
    position = ndb.IntegerProperty(default=0)
    total_score = ndb.IntegerProperty(default=0)

    @classmethod
    def user_photos(cls, user, limit=None):
        '''Return all photos of a user.'''
        query = cls.query(cls.user == user.key)
        query = query.order(cls.upload_date)
        return query.fetch(limit=limit)

    @classmethod
    def competition_photos(cls, competition):
        '''Return all photos entered into a competition.'''
        query = cls.query(cls.competition == competition.key)
        query = query.order(-cls.total_score)
        return query

    @classmethod
    def competition_result(cls, competition):
        '''Return all photos entered in a competition and order by total score
        descending.'''
        query = cls.query(cls.competition == competition.key)
        query = query.order(-cls.total_score)
        return query

    @classmethod
    def competition_user(cls, competition, user):
        '''Return the photo entered by user into competition.'''
        query = cls.query(
            cls.competition == competition.key,
            cls.user == user.key
        )
        return query.get()

    def scores(self):
        '''Return a collection of all the scores for this photo as Scores
        objects.'''
        query = Scores.query(Scores.photo == self.key)
        return query

    def data(self, size=211):
        '''Return information about photo and urls for image and thumb.'''
        title = self.title if self.title else 'Untitled'
        url = get_serving_url(self.blob, size=MAX_SIZE)
        thumb = get_serving_url(self.blob, size=size, crop=True)
        date = self.upload_date.strftime('%d %B, %Y')
        position = self.position if self.position is not None else ''
        score = self.total_score if position != '' else ''
        comp_title = self.competition.get().title
        return title, url, thumb, date, position, score, comp_title

    def thumb(self, size=211):
        return get_serving_url(self.blob, size=size, crop=True)

    def url(self, size=MAX_SIZE):
        return get_serving_url(self.blob, size=size)

    def comments(self):
        query = Comment.query(Comment.photo == self.key)
        return query

    def __str__(self):
        return 'Photo(id={}, compid={})'.format(
            self.key.id(),
            self.competition.id()
        )

    def __repr__(self):
        return self.__str__()


class Comment(ndb.Model):
    photo = ndb.KeyProperty(kind=Photo, required=True)
    user = ndb.KeyProperty(kind=User, required=True)
    submit_date = ndb.DateTimeProperty(auto_now_add=True)
    text = ndb.TextProperty()

    @classmethod
    def photo_comments(cls, photo):
        query = cls.query(cls.photo == photo.key)
        query = query.order(cls.submit_date)
        for comment in query:
            text = markdown.markdown(
                comment.text,
                output_format='html5',
                safe_mode='replace',
            )
            yield (
                comment.key.id(),
                text,
                comment.user.get().username,
                comment.user.id(),
                comment.format_date()
            )

    @classmethod
    def user_comments(cls, user):
        query = cls.query(cls.user == user.key)
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


class Note(ndb.Model):
    user = ndb.KeyProperty(kind=User, required=True)
    submit_date = ndb.DateTimeProperty(auto_now_add=True)
    title = ndb.StringProperty()
    text = ndb.TextProperty()

    @classmethod
    def user_notes(cls, user):
        query = cls.query(cls.user == user.key)
        query = query.order(-cls.submit_date)
        return query

    @classmethod
    def recent_notes(cls, limit=4, offset=0):
        query = cls.query()
        query = query.order(-cls.submit_date)
        for note in query.fetch(limit, offset=offset):
            text = markdown.markdown(
                note.text,
                output_format='html5',
                safe_mode='replace',
            )
            yield (
                note.key.id(),
                note.title,
                text,
                note.user.get().username,
                note.user.id(),
                note.format_date()
            )

    def format_date(self):
        '''Format the stored submit date for pretty printing.'''
        return self.submit_date.strftime('%H:%M, %d-%b-%Y')


class Scores(ndb.Model):
    photo = ndb.KeyProperty(kind=Photo, required=True)
    user_from = ndb.KeyProperty(kind=User, required=True)
    score = ndb.IntegerProperty(required=True)

    @classmethod
    def photo_score(cls, photo):
        '''Return the total score for a photo.'''
        query = cls.query(cls.photo == photo.key)
        #scores = [s.score for s in query]
        #logging.info(scores)
        #return sum(scores)
        return sum(s.score for s in query)

    @classmethod
    def score_from_user(cls, photo, user):
        '''Return the score submitted by a user for a particular photo.'''
        query = cls.query(
            cls.photo == photo.key,
            cls.user_from == user.key
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
    photos.sort(key=lambda p: p.user.get().username)

    buf = StringIO.StringIO()
    fieldnames = ['Recipient'] + [p.user.get().username for p in photos]
    data = csv.DictWriter(buf, fieldnames=fieldnames)

    data.writerow(dict((n, n) for n in fieldnames))

    for photo in photos:
        row = {}
        row['Recipient'] = photo.user.get().username
        for score in photo.scores():
            row[score.user_from.get().username] = score.score
        data.writerow(row)

    return buf.getvalue()


def recently_completed_competitions():
    results = []
    comps = Competition.query(Competition.finished == True)
    comps = comps.order(-Competition.start)
    for comp in comps.fetch(2):
        logging.info('recently_completed_competitions comp: %s', comp)
        # only the top three results
        photos = list(
            photo for photo in Photo.competition_photos(comp)
            if photo.position <= 3
        )
        results.append((comp, photos))
    return results
