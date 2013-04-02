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
)
from handler import BaseHandler

# scores
PHOTO = 10
COMMENT_GIVE = 1
COMMENT_RECEIVE = 2
SCORE_10_GIVE = 5
SCORE_10_RECEIVE = 10
SCORE_0_GIVE = 5
SCORE_0_RECEIVE = 10
FIRST = 10
SECOND = 8
THIRD = 6
POSITIONS = {0: 0, 1: FIRST, 2: SECOND, 3: THIRD}
LAST = 2
NOTE = 1
GIVER = 10
LOGIN = 2
LOGOUT = 5


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
        total += user.login_count * LOGIN
        total += user.logout_count * LOGOUT
        return total


class StatsCalculator(BaseHandler):
    def get(self):
        logging.info('stats calculator...starting')
        data = dict(
            (user.key.id(), UserStats(user=user.key))
            for user in User.query().fetch()
        )
        for photo in Photo.query().fetch():
            if photo.competition is None:
                continue
            user_id = photo.user.id()
            data[user_id].comp_photos += 1
            data[user_id].total_points += photo.total_score
            if photo.position == 1:
                data[user_id].first_place += 1
            elif photo.position == 2:
                data[user_id].second_place += 1
            elif photo.position == 3:
                data[user_id].third_place += 1
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

        UserStats.delete_all()
        for stat in data.values():
            stat.put()

        logging.info(data)
        logging.info('stats calculator...finished')

routes = [
    (r'/stats', Stats),
    (r'/stats-calc', StatsCalculator),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
