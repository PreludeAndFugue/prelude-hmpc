
from google.appengine.ext import db
from google.appengine.ext import blobstore
from google.appengine.api.images import get_serving_url

# the maximum length of the longest dimension of on uploaded photo
MAX_SIZE = 800

class User(db.Model):
    username = db.StringProperty(required=True)
    password = db.StringProperty(required=True)
    email = db.StringProperty(required=True)
    verified = db.BooleanProperty(default=False)
    verify_code=db.StringProperty()
    admin = db.BooleanProperty(default=False)

    @classmethod
    def user_from_name(cls, name):
        '''Return the user from the name attribute.'''
        query = cls.gql('WHERE username = :name', name=name)
        return query.get()

    def __eq__(self, other):
        '''Compare to users for equality.'''
        return self.username == other.username

    def __str__(self):
        return 'User(%s, %s, verified=%s, admin=%s)' % (self.username, self.email,
                self.verified, self.admin)

class Competition(db.Model):
    title = db.StringProperty(required=True)
    year = db.IntegerProperty(required=True)
    month = db.IntegerProperty(required=True)
    start = db.DateProperty(required=True)
    # the closing date for the competition
    end = db.DateProperty(required=True)
    finished = db.BooleanProperty(default=False)
    status = db.IntegerProperty(default=0)

    @classmethod
    def get_by_date(cls, month, year):
        '''Return competition based on its month and year.'''
        query = cls.gql('WHERE month = :1 AND year = :2', month, year)
        return query.get()

    def get_status(self):
        '''Return the status of the competition as a meaningful str.'''
        return {0: 'Open', 1: 'Scoring', 2: 'Completed'}[self.status]

    def __eq__(self, other):
        '''Compare competitions for equality.'''
        return self.year == other.year and self.month == other.month

class UserComp(db.Model):
    '''Keep track of the users who have submitted photos to competitions.
    When a user submits a photo to a competition a record is added to this
    class. This class is used to tell if a user can submit scores to a competition -
    only when they have submitted photo to competition. And if they have submitted
    scores during the scoring phase of the competition.'''
    user = db.ReferenceProperty(reference_class=User, required=True)
    comp = db.ReferenceProperty(reference_class=Competition, required=True)
    submitted_scores = db.BooleanProperty(default=False)

    @classmethod
    def get_usercomp(cls, user, comp):
        '''Return details about a user's participation in a competition.'''
        query = cls.gql('WHERE user = :1 AND comp = :2', user, comp)
        return query.get()

    @classmethod
    def all_scores_submitted(cls, comp):
        '''Have all scores been submitted for a competition.'''
        query = cls.all()
        query.filter('comp = ', comp)
        return all(r.submitted_scores for r in query.run())

class Photo(db.Model):
    user = db.ReferenceProperty(reference_class=User, required=True)
    competition = db.ReferenceProperty(reference_class=Competition) #, required=True)
    title = db.StringProperty()
    blob = blobstore.BlobReferenceProperty(required=True)
    upload_date = db.DateTimeProperty(auto_now_add=True)
    position = db.IntegerProperty(default=None)
    total_score = db.IntegerProperty(default=None)

    @classmethod
    def user_photos(cls, user, limit=6):
        '''Return all photos of a user.'''
        query = cls.gql('WHERE user = :user ORDER BY upload_date DESC', user=user)
        if limit is not None:
            return query.run(limit=limit)
        else:
            return query.run()

    @classmethod
    def competition_photos(cls, competition):
        '''Return all photos entered into a competition.'''
        query = cls.gql('WHERE competition = :c', c=competition)
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
        query = cls.gql('WHERE competition = :c AND user = :u', c=competition, u=user)
        return query.get()

    def data(self, size=288):
        '''Return information about photo and urls for image and thumb.'''
        title = self.title if self.title else 'Untitled'
        url = get_serving_url(self.blob, size=MAX_SIZE)
        thumb = get_serving_url(self.blob, size=size, crop=True)
        date = self.upload_date.strftime('%d %B, %Y')
        return title, url, thumb, date

class Scores(db.Model):
    photo = db.ReferenceProperty(reference_class=Photo, required=True)
    user_from = db.ReferenceProperty(reference_class=User, required=True)
    score = db.IntegerProperty(required=True)

    @classmethod
    def photo_score(cls, photo):
        '''Return the total score for a photo.'''
        query = cls.gql('WHERE photo = :photo', photo=photo)
        return sum(s.score for s in query)

    @classmethod
    def scores_from_user(cls, user, comp):
        '''Return all scores submitted by a user for a particular competition.'''
        query = cls.gql('WHERE user_from = :1 AND photo.competition = :2', user, comp)
        return query.run()

    @classmethod
    def score_from_user(cls, photo, user):
        '''Return the score submitted by a user for a particular photo.'''
        query = cls.gql('WHERE photo = :1 AND user_from = :2', photo, user)
        return query.get()

# some functions that don't really fit in any particular model

def user_scores(user):
    scores = []
    for photo in Photo.user_photos(user, limit=None):
        photo_score = sum(Scores.photo_scores(photo))
        scores.append((photo, photo_score))
    return scores
