#!/usr/bin/env python

import webapp2

import logging
from collections import defaultdict

from model import (
    User,
    Photo,
    Comment,
    Scores,
    Note,
    UserStats,
    Competition,
)
from handler import BaseHandler
from helper import COMPLETED

# scores
PHOTO = 10
HIGH_SCORE_PHOTO = 50
EXTRA_PHOTO = 2
# use up all your extra photo quota
EXTRA_QUOTA = 30
COMMENT_GIVE = 2
MOST_COMMENT_GIVE = 25
COMMENT_RECEIVE = 4
MOST_COMMENT_RECEIVE = 50
MOST_COMMENT_PHOTO = 50
SCORE_10_GIVE = 5
SCORE_10_RECEIVE = 10
SCORE_0_GIVE = 5
SCORE_0_RECEIVE = 10
FIRST = 10
SECOND = 8
THIRD = 6
POSITIONS = {0: 0, 1: FIRST, 2: SECOND, 3: THIRD}
LAST = 20
NOTE = 5
MOST_NOTES = 20
# does this person submit more than receive comments and scores of 10
GIVER = 40
LOGIN = 2
MOST_LOGINS = 20
LOGOUT = 5
MOST_LOGOUTS = 30
MOST_LAST = 50
BIO = 20
ALL_COMPS = 50

# pair the attributes of a UserStat object with the points
PAIRINGS = [
    ('comp_photos', PHOTO), ('extra_photos', EXTRA_PHOTO),
    ('comments_give', COMMENT_GIVE), ('comments_receive', COMMENT_RECEIVE),
    ('score_10_give', SCORE_10_GIVE), ('score_10_receive', SCORE_10_RECEIVE),
    ('score_0_give', SCORE_0_GIVE), ('score_0_receive', SCORE_0_RECEIVE),
    ('first_place', FIRST), ('second_place', SECOND), ('third_place', THIRD),
    ('last_place', LAST), ('notes', NOTE), ('giver', GIVER), ('total_points', 1),
    ('logins', LOGIN), ('logouts', LOGOUT), ('all_comps', ALL_COMPS),
    ('most_comments_give', MOST_COMMENT_GIVE), ('most_last_place', MOST_LAST),
    ('most_comments_receive', MOST_COMMENT_RECEIVE), ('most_notes', MOST_NOTES),
    ('most_logins', MOST_LOGINS), ('most_logouts', MOST_LOGOUTS),
    ('most_comments_photo', MOST_COMMENT_PHOTO),
    ('high_score_photo', HIGH_SCORE_PHOTO)
]


class Stats(BaseHandler):
    def get(self):
        scores = []
        for user_stats in UserStats.query().fetch():
            user = user_stats.user.get()
            score = sum(getattr(user_stats, attr) * points
                        for attr, points in PAIRINGS)
            if score > 0:
                scores.append((score, user.username))

        scores.sort(reverse=True)
        logging.info('scores: %s' % scores)

        data = {
            'page_title': 'Secret Scoreboard',
            'scores': scores,
        }

        self.render('stats.html', **data)


class StatsCalculator(BaseHandler):
    def get(self):
        logging.info('stats calculator...starting')
        # create a UserStat object for all Users in the db
        users = list(User.query().fetch())
        data = dict(
            (user.key.id(), UserStats(user=user.key))
            for user in users
        )

        for user in users:
            user_stat = data[user.key.id()]
            user_stat.logins = user.login_count
            user_stat.logouts = user.logout_count
            user_stat.bio = 1 if user.bio else 0

        for photo in Photo.query().fetch():
            user_id = photo.user.id()
            user_stat = data[user_id]
            if photo.competition is None:
                user_stat.extra_photos += 1
            else:
                if photo.competition.get().status != COMPLETED:
                    # not interested in competition photos for incomplete
                    # competitions
                    continue
                user_stat.comp_photos += 1
                user_stat.total_points += photo.total_score
                if photo.position == 1:
                    user_stat.first_place += 1
                elif photo.position == 2:
                    user_stat.second_place += 1
                elif photo.position == 3:
                    user_stat.third_place += 1

        completed_comp_count = Competition.count()
        for user_stat in data.values():
            if user_stat.comp_photos == completed_comp_count:
                user_stat.all_comps = 1

        for comment in Comment.query().fetch():
            # give
            data[comment.user.id()].comments_give += 1
            # receive
            receiver = comment.photo.get().user.id()
            data[receiver].comments_receive += 1

        for score in Scores.query().fetch():
            receiver = score.photo.get().user.id()
            if score.score == 10:
                # give 10
                data[score.user_from.id()].score_10_give += 1
                # receive 10
                data[receiver].score_10_receive += 1
            elif score.score == 0:
                # give 0
                data[score.user_from.id()].score_0_give += 1
                # receive 0
                data[receiver].score_0_recieve += 1

        for note in Note.query().fetch():
            data[note.user.id()].notes += 1

        # is this person a GIVER
        for user in data.values():
            if user.comments_give > user.comments_receive:
                user.giver += 1
            if user.score_10_give > user.score_10_receive:
                user.giver += 1

        # last place finishers
        self._last_positions(data)

        self._photo_with_most_comments(data)
        self._photo_with_high_score(data)

        self._most(data, 'comments_give')
        self._most(data, 'comments_receive')
        self._most(data, 'notes')
        self._most(data, 'logins')
        self._most(data, 'logouts')
        self._most(data, 'last_place')

        UserStats.delete_all()
        for stat in data.values():
            stat.put()

        logging.info(data)
        logging.info('stats calculator...finished')

    def _most(self, data, attr_name='login_count'):
        '''Find the user(s) with the highest value for a particular
        attribute.'''

        best_count = max(getattr(user, attr_name) for user in data.values())
        logging.info('best_count for %s: %d' % (attr_name, best_count))

        if best_count:
            for user in data.values():
                if getattr(user, attr_name) == best_count:
                    setattr(user, 'most_' + attr_name, 1)

    def _last_positions(self, data):
        '''Update UserStat records for all users who have a photo that was last
        in a competition.'''
        for comp in Competition.get_by_status(COMPLETED):
            photos = list(Photo.competition_photos(comp))
            last_position = max(photos, key=lambda x: x.position).position
            #logging.info('%s: last: %d' % (comp, last_position))
            for photo in filter(lambda x: x.position == last_position, photos):
                data[photo.user.id()].last_place += 1

    def _photo_with_most_comments(self, data):
        '''Find the photograph with the most comments.'''
        comment_count = defaultdict(int)
        for comment in Comment.query():
            comment_count[comment.photo] += 1

        if not comment_count:
            return

        max_comments = max(comment_count.values())
        for photo, comments in comment_count.items():
            if comments == max_comments:
                user_id = photo.get().user.id()
                data[user_id].most_comments_photo = 1

    def _photo_with_high_score(self, data):
        '''Find the photograph(s) with the highest score.

        photo_score / (photos_in_comp - 1)

        Note: only need to consider first placed photos.
        '''
        results = defaultdict(list)
        for photo in Photo.query(Photo.position == 1):
            comp = photo.competition.get()
            photo_count = comp.users().count()
            percent_score = photo.total_score / (10.0 * (photo_count - 1))
            results[percent_score].append(photo)
        max_score = max(results.keys())
        for photo in results[max_score]:
            data[photo.user.id()].high_score_photo += 1


routes = [
    (r'/stats', Stats),
    (r'/stats-calc', StatsCalculator),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
