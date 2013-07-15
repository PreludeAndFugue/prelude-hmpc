#!/usr/bin/env python

from calendar import monthrange
from datetime import date
import webapp2
import logging

from handler import BaseHandler
from model import Competition, Photo, Scores, UserComp, csv_scores
from helper import OPEN, SCORING, COMPLETED, MONTHS


class Competitions(BaseHandler):
    def get(self):
        '''Show the competitions page.'''
        user_id, user = self.get_user()

        comps = []

        for c in Competition.all():
            month = c.month
            month_word = MONTHS[month]
            user_photo = False
            if user:
                user_photo = Photo.competition_user(c, user) is not None
            comps.append((
                #month,
                c.key.id(),
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


class CompetitionHandler(BaseHandler):
    def get(self, comp_id=0):
        '''Show the competition page.'''
        user_id, user = self.get_user()
        comp_id = int(comp_id)
        comp = Competition.get_by_id(comp_id)

        if comp is None:
            self.redirect('/competitions')
            return

        month_str = MONTHS[comp.month]
        data = {
            'user': user,
            'comp': comp,
            'year': comp.year,
            'month': month_str,
            'page_title': comp.title,
            'page_subtitle': comp.get_status(),
            'description': comp.description,
        }

        if comp.status == OPEN:
            self.view_open(user, comp_id, comp, data)
        elif comp.status == SCORING:
            user_comp = self.get_usercomp(user, comp)
            self.view_scoring(user, comp_id, comp, user_comp, data)
        else:  # completed
            self.view_complete(user, comp_id, comp, data)

    def post(self, comp_id=0):
        '''A user is submitting scores.'''
        user_id, user = self.get_user()
        comp_id = int(comp_id)
        comp = Competition.get_by_id(comp_id)

        if not user or not comp:
            # stop some unauthorised post submissions.
            self.redirect('/competitions')
            return

        results = self.parse_scores(self.request.POST)

        for photo_id, score in results.iteritems():
            photo = Photo.get_by_id(photo_id)
            #photo = self.get_photo(photo_id)
            new_score = Scores(
                photo=photo.key,
                user_from=user.key,
                score=score
            )
            new_score.put()

        # record that user has submitted scores for this comp
        usercomp = self.get_usercomp(user, comp)
        usercomp.submitted_scores = True
        usercomp.put()

        self.redirect('/competition/%d' % (comp_id))

    def view_open(self, user, comp_id, comp, data):
        '''Create the competition page when its status is Open.'''
        #for p in Photo.competition_photos(comp):
        photo_count = len(list(Photo.competition_photos(comp)))

        data.update({
            'photo_count': photo_count
        })
        self.render('competition-open.html', **data)

    def view_scoring(self, user, comp_id, comp, user_comp, data):
        '''Create the competition page when its status is Scoring.'''
        competitor = bool(user) and bool(user_comp)
        to_score = user_comp and not user_comp.submitted_scores

        photos = []
        for p in Photo.competition_photos(comp):
        #for p in self.get_competition_photos(comp_id, comp=comp):
            title, url, thumb, _, _, _, _ = p.data(128)
            if user:
                user_photo = p.user.get() == user
                if not to_score:
                    s = Scores.score_from_user(p, user)
                    score = s.score if s else None
                else:
                    score = None
            else:
                user_photo = False
                score = None
            photos.append((p, title, url, thumb, score, user_photo))

        data.update({
            'competitor': competitor,
            'photos': photos,
            'to_score': to_score
        })
        self.render('competition-scoring.html', **data)

    def view_complete(self, user, comp_id, comp, data):
        '''Create the competition page when its status is Completed.'''
        data['photos'] = list(Photo.competition_result(comp))
        data['scores'] = Scores.competition_scores(comp)
        self.render('competition-complete.html', **data)

    def parse_scores(self, scores):
        '''Take the raw POST data MultiDict and convert to dict of photo ids
        (keys) and scores (values).'''
        results = {}
        for photo_id, score in scores.iteritems():
            results[int(photo_id)] = int(score)
        return results

    def get_usercomp(self, user, comp):
        '''Return UserComp object for user and competition.'''
        if user and comp:
            return UserComp.get_usercomp(user, comp)
        # otherwise return None


class CompetitionAdmin(BaseHandler):
    '''Competition Admin handler.'''
    def get(self):
        '''Show the competition admin page.'''
        user_id, user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')

        comps = Competition.all()

        data = {
            'page_title': 'Competition Admin',
            'user': user,
            'comps': [(c.key.id(), c) for c in comps],
            'months': MONTHS
        }
        self.render('competitions-admin.html', **data)


class CompetitionNew(BaseHandler):
    '''New competition handler.'''
    def get(self):
        '''Show the new competition page.'''
        user_id, user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')

        data = {
            'page_title': 'New Competition',
            'user': user,
            'months': MONTHS
        }
        self.render('competition-new.html', **data)

    def post(self):
        '''Create a new competition.'''
        user_id, user = self.get_user()
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
            self.render('competition-new.html', **data)
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


class CompetitionModify(BaseHandler):
    '''Competition modification handler.'''
    def get(self, comp_id):
        'Show the competition modification page for a particular competition.'
        user_id, user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')
            return

        comp_id = int(comp_id)
        comp = Competition.get_by_id(comp_id)
        if not comp:
            self.redirect('/competition/admin')
            return

        data = self._data(comp, user)
        self.render('competition-modify.html', **data)

    def post(self, comp_id):
        '''Modify a competition.'''
        user_id, user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')
            return

        new_title = self.request.get('comp-title')
        new_description = self.request.get('comp-description')
        new_status = int(self.request.get('comp-status'))
        comp_id = int(comp_id)
        comp = Competition.get_by_id(comp_id)

        if not new_title:
            self.report_error(comp, 'Error - blank title.')
            return

        logging.info(
            'updating competition: status %d, new status: %d',
            comp.status,
            new_status
        )

        successful_update, error = self._successful_update(comp, new_status)
        if successful_update:
            self._update_competition(
                comp,
                new_title,
                new_description,
                new_status
            )
        else:
            self._report_error(comp, user, error)

    def _data(self, comp, user, **kwds):
        '''Create the data dictionary for the renderer.'''
        users = []
        photos = []
        status = comp.status
        for uc in comp.users():
            user1 = uc.user.get()
            users.append((
                user1,
                'Yes' if uc.submitted_scores else 'No'
            ))
            if status == OPEN:
                photo = Photo.competition_user(comp, user1)
                photos.append(photo.key.id())

        data = {
            'page_title': 'Modify Competition',
            'title': comp.title,
            'description': comp.description,
            'year': comp.year,
            'month': MONTHS[comp.month],
            'status': comp.get_status(),
            'user': user,
            'users': users,
            'photos': photos,
            'comp_id': comp.key.id(),
            'status_values': (
                (0, 'Open'),
                (1, 'Scoring'),
                (2, 'Completed')
            )
        }

        data.update(kwds)
        #logging.info('kwds %s' % kwds)
        return data

    def _successful_update(self, comp, new_status):
        successful_update = False
        error = None
        if new_status == COMPLETED:
            if comp.status == SCORING:
                # completing a competition and calculating scores
                completed = self._calculate_scores(comp)
                if completed:
                    successful_update = True
                else:
                    # failed to calculate scores
                    error = (
                        'Cannot complete competition - '
                        'not all competitors have submitted scores.'
                    )
            elif comp.status == COMPLETED:
                successful_update = True
            else:  # comp.status == OPEN
                # cannot complete an open competition
                error = (
                    'Cannot complete an open competition - '
                    'users have not yet submitted scores.'
                )
        elif new_status == SCORING:
            if comp.status == SCORING:
                successful_update = True
            elif comp.status == COMPLETED:
                error = 'Competition has been completed - cannot change status.'
            else:  # comp.status == OPEN
                successful_update = True
        else:  # new_status == OPEN
            if comp.status in (SCORING, COMPLETED):
                error = 'Cannot re-open this competition.'
            else:  # comp.status == OPEN
                successful_update = True
        return successful_update, error

    def _calculate_scores(self, comp):
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

    def _update_competition(self, comp, title, description, status):
        '''Update the competition details and redirect to admin page.'''
        comp.title = title
        comp.description = description
        comp.status = status
        comp.finished = True if status == 2 else False
        comp.put()
        self.redirect('/competition/admin')

    def _report_error(self, comp, user, error):
        '''Competition could not be modified - report error to user.'''
        data = self._data(comp, user, error=error)
        self.render('competition-modify.html', **data)


class CompetitionScores(BaseHandler):
    def get(self, comp_id):
        # should check for logged in user cookie
        user_id, user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')
            return

        self.response.content_type = 'text/csv'

        comp_id = int(comp_id)
        comp = Competition.get_by_id(comp_id)

        logging.info(comp)

        self.write(csv_scores(comp))


class CompetitionDelete(BaseHandler):
    def get(self, comp_id):
        user_id, user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')
            return

        comp_id = int(comp_id)
        comp = Competition.get_by_id(comp_id)

        data = {
            'user': user,
            'page_title': 'Delete Competition',
            'comp_id': comp_id,
            'comp': comp,
        }
        self.render('competition-delete.html', **data)

    def post(self, comp_id):
        '''
        Delete a competition, photographs, comments
        '''
        user_id, user = self.get_user()
        if not user or not user.admin:
            self.redirect('/')
            return

        comp_id = int(comp_id)
        comp = Competition.get_by_id(comp_id)
        logging.info('Deleting comp: %s' % comp)

        comp.delete()

        self.redirect('/competition/admin')


routes = [
    (r'/competitions', Competitions),
    (r'/competition/(\d+)', CompetitionHandler),
    (r'/competition/admin', CompetitionAdmin),
    (r'/competition/new', CompetitionNew),
    (r'/competition/modify/(\d+)', CompetitionModify),
    (r'/competition/scores/(\d+)/scores_\d+.csv', CompetitionScores),
    (r'/competition/delete/(\d+)', CompetitionDelete),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
