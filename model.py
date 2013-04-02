
from google.appengine.ext import blobstore
from google.appengine.ext import ndb
#from google.appengine.ext import db
from google.appengine.api.images import Image, get_serving_url
import markdown

import csv
import datetime
import logging
import StringIO

from helper import COMPLETED, SCORING, ordinal, MONTHS

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
    bio = ndb.TextProperty(default='')
    extra_photo_count = ndb.IntegerProperty(default=0)

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
                    yield comp

    def bio_markdown(self):
        return markdown.markdown(
            self.bio if self.bio else "*...no details...*",
            output_format='html5',
            safe_mode='replace',
        )

    def __eq__(self, other):
        '''Compare to users for equality.'''
        return self.key.id() == other.key.id()

    def __str__(self):
        params = (self.username, self.email, self.verified, self.admin)
        return 'User(%s, %s, verified=%s, admin=%s)' % params

    def __repr__(self):
        return self.__str__()


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

    def month_text(self):
        '''Return the month as a string name.'''
        return MONTHS[self.month]

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
            blobstore.delete(photo.blob)
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
    competition = ndb.KeyProperty(kind=Competition, default=None)  # required=True)
    title = ndb.StringProperty()
    blob = ndb.BlobKeyProperty(required=True)
    upload_date = ndb.DateTimeProperty(auto_now_add=True)
    position = ndb.IntegerProperty(default=0)
    total_score = ndb.IntegerProperty(default=0)
    # exif data
    make = ndb.StringProperty(default='')
    model = ndb.StringProperty(default='')
    datetime = ndb.DateTimeProperty()
    iso = ndb.IntegerProperty(default=0)
    focal_length = ndb.IntegerProperty(default=0)
    lens = ndb.StringProperty(default='')
    aperture = ndb.FloatProperty(default=0.0)
    exposure_time = ndb.IntegerProperty(default=1)
    exposure_time1 = ndb.FloatProperty(default=1.0)
    copyright = ndb.StringProperty(default='')
    comment_count = ndb.IntegerProperty(default=0)
    # for extra photos
    month = ndb.IntegerProperty(default=1)

    @classmethod
    def user_photos(cls, user, limit=None):
        '''Return all photos of a user.'''
        query = cls.query(cls.user == user.key)
        query = query.filter(cls.competition != None)
        #query = query.order(cls.upload_date)
        return query.fetch(limit=limit)

    @classmethod
    def user_photos_complete(cls, user, limit=None):
        '''Return all photos of a user in completed competitions.'''
        query = cls.query(cls.user == user.key)
        query = query.filter(cls.competition != None)
        photos = []
        for photo in query:
            if photo.competition.get().status == COMPLETED:
                photos.append(photo)
        photos.sort(key=lambda p: p.upload_date)
        return photos

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
    def extra_photos(cls, user):
        '''Return all extra photos for a particular user.'''
        query = cls.query(
            cls.competition == None,
            cls.user == user.key,
        )
        query = query.order(cls.month)
        return query

    @classmethod
    def competition_user(cls, competition, user):
        '''Return the photo entered by user into competition.'''
        query = cls.query(
            cls.competition == competition.key,
            cls.user == user.key,
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

    def exif(self):
        return {
            'make': self.make,
            'model': self.model,
            'datetime': self.format_date(),
            'iso': self.iso,
            'focal_length': self.focal_length,
            'lens': self.lens,
            'exposure_time': self._exposure_time(),
            'aperture': self.aperture,
            'copyright': self.copyright,
        }

    def _exposure_time(self):
        et = self.exposure_time1
        logging.info("exposure time: %d" % et)
        if et < 1:
            return '1/%ds' % round(1 / et)
        else:
            return '%0.1fs' % et

    def ordinal_position(self):
        return ordinal(self.position)

    def username(self):
        return self.user.get().username

    def get_competition(self):
        return self.competition.get()

    def comments(self):
        query = Comment.query(Comment.photo == self.key)
        return query

    def format_date(self):
        if self.datetime:
            day = self.datetime.day
            day = ordinal(day)
            rest = self.datetime.strftime('%B %Y')
            return ' '.join((day, rest))
        else:
            return '?'

    def delete(self):
        '''Delete the photograph.

        To delete a photograph, need to delete the following:
            all comments
            all scores
            the UserComp if it exists
            the blob
            Also, if an extra photo, reduce the extra photo count by one
        '''
        all_keys = []
        if self.competition:
            user_comp = UserComp.query(
                UserComp.user == self.user,
                UserComp.comp == self.competition
            ).get()
            all_keys.append(user_comp.key)
        else:
            user = self.user.get()
            user.extra_photo_count -= 1
            user.put()
        for comment_key in Comment.query(
                Comment.photo == self.key).fetch(keys_only=True):
            all_keys.append(comment_key)
        for score_key in Scores.query(
                Scores.photo == self.key).fetch(keys_only=True):
            all_keys.append(score_key)
        all_keys.append(self.key)
        blobstore.delete(self.blob)
        ndb.delete_multi(all_keys)

    def delete_comments(self):
        '''Delete comments associated with this photo.'''
        query = Comment.query(Comment.photo == self.key)
        ndb.delete_multi(list(query.fetch(keys_only=True)))

    def __str__(self):
        competition = self.competition
        competition = competition.id() if competition else None
        return 'Photo(id={}, compid={})'.format(
            self.key.id(),
            competition,
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
    def recent_comments(cls, limit=5, offset=0):
        query = cls.query()
        query = query.order(-cls.submit_date)
        return query.fetch(limit, offset=offset)

    def username(self):
        return self.user.get().username

    def markdown(self):
        '''Apply markdown to the comment text.'''
        text = markdown.markdown(
            self.text,
            output_format='html5',
            safe_mode='replace',
        )
        return text

    def format_date(self):
        '''Format the stored submit date for pretty printing.'''
        return self.submit_date.strftime('%H:%M, %d-%b-%Y')

    def photo_thumbnail(self):
        return self.photo.get().thumb(42)

    def photo_id(self):
        return self.photo.id()


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

    def markdown(self):
        '''Apply markdown to the note text.'''
        text = markdown.markdown(
            self.text,
            output_format='html5',
            safe_mode='replace',
        )
        return text


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


def blob_exif(blob_key):
    '''Extract EXIF data from the blob data.'''
    keys = (
            ('make', 'Make', '?'),
            ('model', 'Model', '?'),
            ('datetime', 'DateTimeDigitized', '1990:01:01 00:00:00'),
            ('iso', 'ISOSpeedRatings', 0),
            ('focal_length', 'FocalLength', 0),
            ('lens', 'Lens', '?'),
            ('exposure_time', 'ExposureTime', 1),
            ('exposure_time1', 'ExposureTime', 1.0),
            ('aperture', ['ApertureValue', 'MaxApertureValue'], 0.0),
            ('copyright', 'Copyright', '')
        )
    data = {}
    im = Image(blob_key=blob_key)
    im.rotate(0)
    im.execute_transforms(parse_source_metadata=True)
    exif = im.get_original_metadata()
    logging.info(exif)
    for key, key_exif, default in keys:
        if key == 'datetime':
            dt = exif.get(key_exif, default)
            data[key] = datetime.datetime.strptime(dt, '%Y:%m:%d %H:%M:%S')
        elif key == 'focal_length':
            data[key] = int(exif.get(key_exif, default))
        elif key == 'exposure_time':
            t = exif.get(key_exif, default)
            if t == 0:
                data[key] = t
            else:
                data[key] = int(round(1 / t))
        elif key == 'aperture':
            app, max_app = key_exif
            aperture = exif.get(app, None)
            aperture = exif.get(max_app, default) if not aperture else aperture
            data[key] = aperture
        else:
            data[key] = exif.get(key_exif, default)
    return data


class UserStats(ndb.Model):
    user = ndb.KeyProperty(kind=User, required=True)
    comp_photos = ndb.IntegerProperty(default=0)
    comments_give = ndb.IntegerProperty(default=0)
    comments_receive = ndb.IntegerProperty(default=0)
    score_10_give = ndb.IntegerProperty(default=0)
    score_10_receive = ndb.IntegerProperty(default=0)
    score_0_give = ndb.IntegerProperty(default=0)
    score_0_receive = ndb.IntegerProperty(default=0)
    total_points = ndb.IntegerProperty(default=0)
    first_place = ndb.IntegerProperty(default=0)
    second_place = ndb.IntegerProperty(default=0)
    third_place = ndb.IntegerProperty(default=0)
    notes = ndb.IntegerProperty(default=0)
    giver = ndb.IntegerProperty(default=0)

    @classmethod
    def delete_all(cls):
        data = cls.query().fetch(keys_only=True)
        ndb.delete_multi(list(data))

    def __str__(self):
        format_string = (
            '\nUserStats: %s, \n\tphotos: %d, c_g: %d, c_r: %d, points: %d'
            '\n\t10_g: %d, 10_r: %d, 0_g: %d 0_r: %d'
            '\n\t1st: %d, 2nd: %d, 3rd: %d, notes: %d\n'
        )
        data = (
            self.user.get().username,
            self.comp_photos,
            self.comments_give,
            self.comments_receive,
            self.total_points,
            self.score_10_give,
            self.score_10_receive,
            self.score_0_give,
            self.score_0_receive,
            self.first_place,
            self.second_place,
            self.third_place,
            self.notes,
        )
        return format_string % data

    def __repr__(self):
        return self.__str__()
