#!/usr/bin/env python

import webapp2
import logging
import datetime

from handler import BaseHandler
from model import Note


def empty_note():
    class X(object):
        def __init__(self):
            self.title = ''
            self.text = ''
    return X()


class Notes(BaseHandler):
    def get(self):
        user_id, user = self.get_user()

        start = self.request.get('start')
        logging.info('start: %s', start)

        if not start:
            start = 0
        else:
            start = int(start)
            if start > 1000000:
                start = 0

        if start == 0:
            before = 0
            after = 10
        else:
            before = start - 10
            after = start + 10

        notes = list(Note.recent_notes(10, start))
        more_old = '' if len(notes) == 10 else 'disabled'
        more_new = '' if start > 0 else 'disabled'

        data = {
            'page_title': 'Notes',
            'user': user,
            'user_id': user_id,
            'notes': notes,
            'before': before,
            'after': after,
            'more_old': more_old,
            'more_new': more_new,
        }

        self.render('notes.html', **data)


class NoteNew(BaseHandler):
    '''Create a new note.'''
    def get(self):
        user_id, user = self.get_user()
        if not user:
            self.redirect('/')
            return

        note = empty_note()

        data = {
            'page_title': 'New Note',
            'user': user,
            'userid': user_id,
            'note': note,
        }
        self.render('note-edit.html', **data)

    def post(self):
        user_id, user = self.get_user()
        if not user:
            self.redirect('/')
            return

        title = self.request.get('note-title')
        text = self.request.get('note-text')
        dt = datetime.datetime.now()
        logging.info('%s\n%s\n%s', title, text, dt)

        if not title or not text:
            msg = (
                'You must enter a title and some text to create a new note.'
            )
            data = {
                'page_title': 'Blank Note',
                'user': user,
                'error_msg': msg
            }
            self.render('error.html', **data)
            return

        new_note = Note(
            user=user.key,
            submit_date=dt,
            title=title,
            text=text,
        )
        new_note.put()

        self.redirect('/notes')


class NoteEdit(BaseHandler):
    def get(self, note_id=0):
        '''Edit a note'''
        user_id, user = self.get_user()
        if not user:
            self.redirect('/')
            return

        note_id = int(note_id)
        note = Note.get_by_id(note_id)

        error, data = self._check(user, note)
        if error:
            self.render('error.html', **data)
            return

        data = {
            'page_title': 'Edit Note',
            'user': user,
            'userid': user_id,
            'note': note,
        }
        self.render('note-edit.html', **data)

    def post(self, note_id=0):
        '''Updating the comment and redirecting back to the photo page.'''
        user_id, user = self.get_user()
        if not user:
            self.redirect('/')
            return

        note_id = int(note_id)
        note = Note.get_by_id(note_id)

        error, data = self._check(user, note)
        if error:
            self.render('error.html', **data)

        title = self.request.get('note-title')
        text = self.request.get('note-text')
        logging.info('%s\n%s', repr(title), repr(text))

        if not title or not text:
            msg = (
                'You must enter a title and some text to create a new note.'
            )
            data = {
                'page_title': 'Blank Note',
                'user': user,
                'error_msg': msg
            }
            self.render('error.html', **data)
            return

        note.title = title
        note.text = text
        note.put()

        self.redirect('/notes')

    def _check(self, user, note):
        '''Check to make sure comment exists and the user can edit it.'''
        data = {
            'page_title': 'Error',
            'user': user,
        }
        if not note:
            data['error_msg'] = 'Could not find Note.'
            return True, data

        if note.user.id() != user.key.id() and not user.admin:
            data['error_msg'] = 'You cannot edit this comment.'
            return True, data

        return False, None

routes = [
    (r'/notes', Notes),
    (r'/note/edit/(\d+)', NoteEdit),
    (r'/note/new', NoteNew),
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
