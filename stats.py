#!/usr/bin/env python

import webapp2

import logging

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

# scores
PHOTO = 10
EXTRA_PHOTO = 2
# use up all your extra photo quota
EXTRA_QUOTA = 30
COMMENT_GIVE = 2
MOST_COMMENT_GIVE = 25
COMMENT_RECEIVE = 4
MOST_COMMENT_RECEIVE = 50
SCORE_10_GIVE = 5
SCORE_10_RECEIVE = 10
SCORE_0_GIVE = 5
SCORE_0_RECEIVE = 10
FIRST = 10
SECOND = 8
THIRD = 6
POSITIONS = {0: 0, 1: FIRST, 2: SECOND, 3: THIRD}
LAST = 10
NOTE = 5
MOST_NOTES = 20
# does this person submit more than receive comments and scores of 10
GIVER = 40
LOGIN = 2
MOST_LOGINS = 20
LOGOUT = 5
MOST_LOGOUTS = 30
BIO = 20
ALL_COMPS = 50


class Stats(BaseHandler):
    def get(self):
        scores = []
        for user_stats in UserStats.query().fetch():
            user = user_stats.user.get()
            score = self.total_score(user_stats, user)
            if score > 0:
                scores.append((score, user.username))

        scores.sort(reverse=True)
        logging.info('scores: %s' % scores)

        data = {
            'page_title': 'Secret Scoreboard',
            'scores': scores,
        }

        self.render('stats.html', **data)

    def total_score(self, user_stat, user):
        '''Calculate the total score for a user.'''
        total = 0
        total += user_stat.comp_photos * PHOTO
        total += user_stat.extra_photos * EXTRA_PHOTO
        total += user_stat.comments_give * COMMENT_GIVE
        total += user_stat.comments_receive * COMMENT_RECEIVE
        total += user_stat.score_10_give * SCORE_10_GIVE
        total += user_stat.score_10_receive * SCORE_10_RECEIVE
        total += user_stat.score_0_give * SCORE_0_GIVE
        total += user_stat.score_0_receive * SCORE_0_RECEIVE
        total += user_stat.first_place * FIRST
        total += user_stat.second_place * SECOND
        total += user_stat.third_place * THIRD
        total += user_stat.notes * NOTE
        total += user_stat.giver * GIVER
        total += user_stat.total_points
        total += user_stat.logins * LOGIN
        total += user_stat.logouts * LOGOUT
        total += user_stat.all_comps * ALL_COMPS
        # most
        total += user_stat.most_comments_give * MOST_COMMENT_GIVE
        total += user_stat.most_comments_receive * MOST_COMMENT_RECEIVE
        total += user_stat.most_notes * MOST_NOTES
        total += user_stat.most_logins * MOST_LOGINS
        total += user_stat.most_logouts * MOST_LOGOUTS
        return total


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
            if photo.competition is None:
                data[user_id].extra_photos += 1
            else:
                data[user_id].comp_photos += 1
                data[user_id].total_points += photo.total_score
                if photo.position == 1:
                    data[user_id].first_place += 1
                elif photo.position == 2:
                    data[user_id].second_place += 1
                elif photo.position == 3:
                    data[user_id].third_place += 1

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
                # give
                data[score.user_from.id()].score_10_give += 1
                # receive
                data[receiver].score_10_receive += 1
            elif score.score == 0:
                # give
                data[score.user_from.id()].score_0_give += 1
                # receive
                data[receiver].score_0_recieve += 1

        for note in Note.query().fetch():
            data[note.user.id()].notes += 1

        # is this person a GIVER
        for user in data.values():
            if user.comments_give > user.comments_receive:
                user.giver += 1
            if user.score_10_give > user.score_10_receive:
                user.giver += 1

        self._most(data, 'comments_give')
        self._most(data, 'comments_receive')
        self._most(data, 'notes')
        self._most(data, 'logins')
        self._most(data, 'logouts')

        UserStats.delete_all()
        for stat in data.values():
            stat.put()

        logging.info(data)
        logging.info('stats calculator...finished')

    def _most(self, data, attr_name='login_count'):
        '''Find the user with the highest value for a particular attribute.'''
        best_user_id = None
        best_count = 0
        for user_id, user_stat in data.items():
            attr_value = getattr(user_stat, attr_name)
            if attr_value > best_count:
                best_user_id = user_id
                best_count = attr_value
        if best_user_id:
            user_stat = data[best_user_id]
            setattr(user_stat, 'most_' + attr_name, 1)


routes = [
    (r'/stats', Stats),
    (r'/stats-calc', StatsCalculator),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
