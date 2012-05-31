#!/usr/bin/env python

from calendar import monthrange
from datetime import date
import jinja2
import webapp2
import os
import logging

from handler import BaseHandler
from model import Competition, User, Photo, Scores, UserComp

MONTHS = {
    1: 'January',
    2: 'February',
    3: 'March',
    4: 'April',
    5: 'May',
    6: 'June',
    7: 'July',
    8: 'August',
    9: 'September',
    10: 'October',
    11: 'November',
    12: 'December'
}

def ordinal(n):
    '''Return ordinal number string from input integer.'''
    if 10 <= n % 100 < 20:
        return str(n) + 'th'
    else:
       return  str(n) + {1 : 'st', 2 : 'nd', 3 : 'rd'}.get(n % 10, "th")

class Comps(BaseHandler):
    def get(self):
        user = self.get_user()
        comps = []
        for c in Competition.all().order('-start').run():
            month = c.month
            month_word = MONTHS[month]
            user_photo = None
            if user:
                user_photo = Photo.competition_user(c, user) is not None
            comps.append((month, month_word, c.year, c.title, c.get_status(),
                user_photo))
        data = {
            'page_title': 'Competitions',
            'user': user,
            'comps': comps,
            'months': MONTHS
        }
        self.render('competitions.html', **data)

class CompHandler(BaseHandler):
    def get(self, year=0, month=0):
        user = self.get_user()
        comp = self.get_comp(year, month)

        if comp is None:
            self.redirect('/competitions')
            return

        month_str = MONTHS[comp.month]
        data = {
            'user': user,
            'comp': comp,
            'year': year,
            'month': month_str,
            'page_title': 'Competition: %s %d' % (month_str, comp.year),
            'page_subtitle': comp.get_status(),
        }

        if comp.status == 0:
            # open
            self.view_open(user, comp, data)
        elif comp.status == 1:
            # scoring
            user_comp = self.get_usercomp(user, comp)
            if not user or not user_comp:
                self.view_open(user, comp, data)
            else:
                self.view_scoring(user, comp, user_comp, data)
        else:
            # completed
            self.view_complete(user, comp, data)

    def post(self, year=0, month=0):
        user = self.get_user()
        year = int(year)
        month = int(month)
        comp = self.get_comp(year, month)
        results = self.parse_scores(self.request.POST)

        #self.write(results)
        #self.write(self.request.POST)

        for photo_id, score in results.iteritems():
            photo = Photo.get_by_id(photo_id)
            new_score = Scores(photo=photo, user_from=user, score=score)
            new_score.put()

        # record that user has submitted scores for this comp
        usercomp = self.get_usercomp(user, comp)
        usercomp.submitted_scores = True
        usercomp.put()

        self.redirect('/competition/%d/%d' % (year, month))

    def view_open(self, user, comp, data):
        photos = []
        for p in Photo.competition_photos(comp):
            title, url, thumb, date = p.data(128)
            photos.append((p, title, url, thumb))

        data.update({
            'photos': photos
        })
        self.render('competition-open.html', **data)

    def view_scoring(self, user, comp, user_comp, data):
        to_score = user_comp and not user_comp.submitted_scores

        photos = []
        for p in Photo.competition_photos(comp):
            title, url, thumb, date = p.data(128)
            user_photo = p.user == user
            if not to_score:
                s = Scores.score_from_user(p, user)
                score = s.score if s else None
            else:
                score = None
            photos.append((p, title, url, thumb, score, user_photo))

        data.update({
            'photos': photos,
            'to_score': to_score
        })
        self.render('competition-scoring.html', **data)


    def view_complete(self, user, comp, data):
        photos = []
        for p in Photo.competition_result(comp):
            title, url, thumb, date = p.data(128)
            photos.append((p, title, p.user.username, url, thumb,
                ordinal(p.position), p.total_score))

        data.update({
            'photos': photos
        })

        self.render('competition-complete.html', **data)

    def get_comp(self, year, month):
        if year == 0 and month == 0:
             # get the current competition
            comp = Competition.all().order('-start').get()
        else:
            month = int(month)
            year = int(year)
            comp = Competition.get_by_date(month, year)
        return comp

    def get_usercomp(self, user, comp):
        if user is not None and comp is not None:
            return UserComp.get_usercomp(user, comp)
        # otherwise return None

class CompAdmin(BaseHandler):
    def get(self):
        user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')

        query = Competition.all().order('-start')
        comps = query.run()

        data = {
            'page_title': 'Competition Admin',
            'user': user,
            'comps': list(comps),
            'months': MONTHS
        }
        self.render('comp-admin.html', **data)

class NewComp(BaseHandler):
    def get(self):
        user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')

        data = {
            'page_title': 'New Competition',
            'user': user,
            'months': MONTHS
        }
        self.render('comp-new.html', **data)

    def post(self):
        user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')

        title = self.request.get('comp-title')
        month = int(self.request.get('comp-month'))
        year = int(self.request.get('comp-year'))

        errors = []

        if not title:
            errors.append('You forgot to give this competition a title.')

        comp = Competition.get_by_date(month, year)
        if comp:
            errors.append('A competition already exists for %s, %d'
                    % (MONTHS[month], year))

        if errors:
            data = {
                'errors': errors,
                'page_title': 'New Competition',
                'user': user,
                'months': MONTHS
            }
            self.render('comp-new.html', **data)
            return

        # no errors so create new competiton
        start = date(year, month, 1)
        end = date(year, month, monthrange(year, month)[1])
        new_comp = Competition(title=title, month=month, year=year,
                            start=start, end=end)
        new_comp.put()
        self.redirect('/competition/admin')

class CompMod(BaseHandler):
    def get(self, year, month):
        user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')
            return

        year = int(year)
        month = int(month)
        comp = Competition.get_by_date(month, year)
        if not comp:
            self.redirect('/competition/admin')
            return

        data = self._data(comp, user)
        self.render('comp-mod.html', **data)

    def post(self, year, month):
        new_title = self.request.get('comp-title')
        new_status = int(self.request.get('comp-status'))
        comp_id = int(self.request.get('comp-id'))

        #logging.info(repr(comp_id))

        comp = Competition.get_by_id(comp_id)

        #logging.info(comp)

        if new_status != 2:
            comp.title = new_title
            comp.status = new_status
            comp.put()
            self.redirect('/competition/admin')
        elif comp.status == 2 and new_status != 2:
            user = self.get_user()
            error = 'Competition has been completed - cannot change status.'
            data = self._data(comp, user, error=error)
            self.render('comp-mod.html', **data)
        else:
            # completing a competition and calculating scores
            completed = self.calculate_scores(comp)
            if completed:
                comp.title = new_title
                comp.status = new_status
                comp.put()
                self.redirect('/competition/admin')
            else:
                # failed to calculate scores
                user = self.get_user()
                error = ('Cannot complete competition - '
                    'not all competitors have submitted scores.')
                data = self._data(comp, user, error=error)
                self.render('comp-mod.html', **data)

    def _data(self, comp, user, **kwds):
        data = {
            'page_title': 'Modify Competition',
            'title': comp.title,
            'year': comp.year,
            'month': MONTHS[comp.month],
            'status': comp.get_status(),
            'user': user,
            'comp_id': comp.key().id(),
            'status_values': (
                (0, 'Open'),
                (1, 'Scoring'),
                (2, 'Completed')
            )
        }

        data.update(kwds)
        #logging.info('kwds %s' % kwds)
        return data

    def calculate_scores(self, comp):
        all_scores = UserComp.all_scores_submitted(comp)
        if not all_scores:
            return False

        results = []
        for photo in Photo.competition_photos(comp):
            total_score = Scores.photo_score(photo)
            results.append((total_score, photo))
        results.sort(reverse=True)

        # calculate positions
        position = 1
        prev_score = 1000000
        #full_results = []
        for i, (score, photo) in enumerate(results, start=1):
            if score != prev_score:
                position = i
            #full_results.append((position, score, photo))
            photo.position = position
            photo.total_score = score
            photo.put()
            prev_score = score

        return True



app = webapp2.WSGIApplication([('/competitions', Comps),
                               ('/competition/(\d{4})/(\d\d?)', CompHandler),
                               ('/competition/admin', CompAdmin),
                               ('/competition/new', NewComp),
                               ('/competition/modify/(\d{4})/(\d\d?)', CompMod),
                               ('/competition/current', CompHandler)],
                              debug=True)