#!/usr/bin/env python

from calendar import monthrange
from datetime import date
import webapp2
import logging

from handler import BaseHandler
from model import Competition, Photo, Scores, UserComp, csv_scores
from helper import OPEN, SCORING, COMPLETED, MONTHS, ordinal


class Comps(BaseHandler):
    def get(self):
        '''Show the competitions page.'''
        user = self.get_user()
        comps = []
        for c in Competition.all().order('-start').run():
            month = c.month
            month_word = MONTHS[month]
            user_photo = None
            if user:
                user_photo = Photo.competition_user(c, user) is not None
            comps.append((
                #month,
                c.key().id(),
                month_word,
                c.year,
                c.title,
                c.description,
                c.get_status(),
                user_photo
            ))
        data = {
            'page_title': 'Competitions',
            'user': user,
            'comps': comps,
            'months': MONTHS
        }
        self.render('competitions.html', **data)


class CompHandler(BaseHandler):
    def get(self, comp_id=0):
        '''Show the competition page.'''
        user = self.get_user()
        comp_id = int(comp_id)
        comp = Competition.get_by_id(comp_id)
        #comp = self.get_comp(year, month)

        if comp is None:
            self.redirect('/competitions')
            return

        month_str = MONTHS[comp.month]
        data = {
            'user': user,
            'comp': comp,
            'year': comp.year,
            'month': month_str,
            'page_title': 'Competition: %s %d' % (month_str, comp.year),
            'page_subtitle': comp.get_status(),
        }

        if comp.status == OPEN:
            self.view_open(user, comp, data)
        elif comp.status == SCORING:
            user_comp = self.get_usercomp(user, comp)
            if not user or not user_comp:
                self.view_open(user, comp, data)
            else:
                self.view_scoring(user, comp, user_comp, data)
        else:  # completed
            self.view_complete(user, comp, data)

    def post(self, comp_id=0):
        '''A user is submitting scores.'''
        user = self.get_user()
        comp_id = int(comp_id)
        comp = Competition.get_by_id(comp_id)
        results = self.parse_scores(self.request.POST)

        if not user or not comp:
            # stop some unauthorised post submissions.
            self.redirect('/competitions')
            return

        for photo_id, score in results.iteritems():
            photo = Photo.get_by_id(photo_id)
            new_score = Scores(photo=photo, user_from=user, score=score)
            new_score.put()

        # record that user has submitted scores for this comp
        usercomp = self.get_usercomp(user, comp)
        usercomp.submitted_scores = True
        usercomp.put()

        if self.request.path.endswith('/current'):
            url = '/competition/current'
        else:
            url = '/competition/%d' % (comp_id)

        self.redirect(url)

    def view_open(self, user, comp, data):
        '''Create the competition page when its status is Open.'''
        photos = []
        for p in Photo.competition_photos(comp):
            title, url, thumb, _, _, _, _ = p.data(128)
            photos.append((p, title, url, thumb))

        data.update({
            'photos': photos
        })
        self.render('competition-open.html', **data)

    def view_scoring(self, user, comp, user_comp, data):
        '''Create the competition page when its status is Scoring.'''
        to_score = user_comp and not user_comp.submitted_scores

        logging.info('to_score: %s' % to_score)

        photos = []
        for p in Photo.competition_photos(comp):
            title, url, thumb, _, _, _, _ = p.data(128)
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
        '''Create the competition page when its status is Completed.'''
        photos = []
        for p in Photo.competition_result(comp):
            title, url, thumb, _, _, _, _ = p.data(128)
            photos.append((p, title, p.user.username, url, thumb,
                ordinal(p.position), p.total_score))

        data.update({
            'photos': photos
        })

        self.render('competition-complete.html', **data)

    def parse_scores(self, scores):
        '''Take the raw POST data MultiDict and convert to dict of photo ids
        (keys) and scores (values).'''
        results = {}
        for photo_id, score in scores.iteritems():
            results[int(photo_id)] = int(score)
        return results

    def get_comp(self, year, month):
        '''Return the competition object from the year and the month.'''
        if year == 0 and month == 0:
             # get the current competition
            comp = Competition.all().order('-start').get()
        else:
            month = int(month)
            year = int(year)
            comp = Competition.get_by_date(month, year)
        return comp

    def get_usercomp(self, user, comp):
        '''Return UserComp object for user and competition.'''
        if user is not None and comp is not None:
            return UserComp.get_usercomp(user, comp)
        # otherwise return None


class CompAdmin(BaseHandler):
    '''Competition Admin handler.'''
    def get(self):
        '''Show the competition admin page.'''
        user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')

        query = Competition.all().order('-start')
        comps = query.run()

        data = {
            'page_title': 'Competition Admin',
            'user': user,
            'comps': [(c.key().id(), c) for c in comps],
            'months': MONTHS
        }
        self.render('comp-admin.html', **data)


class NewComp(BaseHandler):
    '''New competition handler.'''
    def get(self):
        '''Show the new competition page.'''
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
        '''Create a new competition.'''
        user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')

        title = self.request.get('comp-title')
        description = self.request.get('comp-description')
        month = int(self.request.get('comp-month'))
        year = int(self.request.get('comp-year'))

        errors = []

        if not title:
            errors.append('You forgot to give this competition a title.')

        comp = Competition.get_by_title_date(title, month, year)
        if comp:
            errors.append(
                'A competition already exists with this title (%s), month (%s), '
                'and year (%d)' % (title, MONTHS[month], year)
            )

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
        new_comp = Competition(
            title=title,
            description=description,
            month=month,
            year=year,
            start=start,
            end=end
        )
        new_comp.put()
        self.redirect('/competition/admin')


class CompMod(BaseHandler):
    '''Competition modification handler.'''
    def get(self, comp_id):
        'Show the competition modification page for a particular competition.'
        user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')
            return

        comp_id = int(comp_id)
        comp = Competition.get_by_id(comp_id)
        if not comp:
            self.redirect('/competition/admin')
            return

        data = self._data(comp, user)
        self.render('comp-mod.html', **data)

    def post(self, comp_id):
        '''Modify a competition.'''
        new_title = self.request.get('comp-title')
        new_description = self.request.get('comp-description')
        new_status = int(self.request.get('comp-status'))
        #comp_id = int(self.request.get('comp-id'))
        comp_id = int(comp_id)

        comp = Competition.get_by_id(comp_id)

        if not new_title:
            self.report_error(comp, 'Error - blank title.')
            return

        #logging.info(comp)
        logging.info(
            'updating competition: status %d, new status: %d',
            comp.status,
            new_status
        )

        if new_status == COMPLETED:
            if comp.status == SCORING:
                # completing a competition and calculating scores
                completed = self.calculate_scores(comp)
                if completed:
                    self.update_competition(
                        comp,
                        new_title,
                        new_description,
                        new_status
                    )
                else:
                    # failed to calculate scores
                    error = ('Cannot complete competition - '
                        'not all competitors have submitted scores.')
                    self.report_error(comp, error)
            elif comp.status == COMPLETED:
                self.update_competition(
                    comp,
                    new_title,
                    new_description,
                    new_status
                )
            else:  # comp.status == OPEN
                # cannot complete an open competition
                error = ('Cannot complete an open competition - '
                    'users have not yet submitted scores.')
                self.report_error(comp, error)
        elif new_status == SCORING:
            if comp.status == SCORING:
                self.update_competition(
                    comp,
                    new_title,
                    new_description,
                    new_status
                )
            elif comp.status == COMPLETED:
                error = 'Competition has been completed - cannot change status.'
                self.report_error(comp, error)
            else:  # comp.status == OPEN
                self.update_competition(
                    comp,
                    new_title,
                    new_description,
                    new_status
                )
        else:  # new_status == OPEN
            if comp.status in (SCORING, COMPLETED):
                error = 'Cannot re-open this competition.'
                self.report_error(comp, error)
            else:  # comp.status == OPEN
                self.update_competition(
                    comp,
                    new_title,
                    new_description,
                    new_status
                )

    def _data(self, comp, user, **kwds):
        '''Create the data dictionary for the renderer.'''
        users = [
            (uc.user.username, 'Yes' if uc.submitted_scores else 'No')
            for uc in comp.users()
        ]
        data = {
            'page_title': 'Modify Competition',
            'title': comp.title,
            'description': comp.description,
            'year': comp.year,
            'month': MONTHS[comp.month],
            'status': comp.get_status(),
            'user': user,
            'users': users,
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
        '''Calculate the scores for a completed competition.'''
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

    def update_competition(self, comp, title, description, status):
        '''Update the competition details and redirect to admin page.'''
        comp.title = title
        comp.description = description
        comp.status = status
        comp.put()
        self.redirect('/competition/admin')

    def report_error(self, comp, error):
        '''Competition could not be modified - report error to user.'''
        user = self.get_user()
        data = self._data(comp, user, error=error)
        self.render('comp-mod.html', **data)


class CompScores(BaseHandler):
    def get(self, comp_id):
        # should check for logged in user cookie
        user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')
            return

        self.response.content_type = 'text/csv'

        comp_id = int(comp_id)
        comp = Competition.get_by_id(comp_id)

        logging.info(comp)

        self.write(csv_scores(comp))

routes = [
    (r'/competitions', Comps),
    (r'/competition/(\d+)', CompHandler),
    (r'/competition/admin', CompAdmin),
    (r'/competition/new', NewComp),
    (r'/competition/modify/(\d+)', CompMod),
    (r'/competition/scores/(\d+)/scores_\d+.csv', CompScores)
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
