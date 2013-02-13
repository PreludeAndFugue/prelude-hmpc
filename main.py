#!/usr/bin/env python

import logging
from random import shuffle
import webapp2
import markdown

from handler import BaseHandler
from helper import MONTHS, ordinal
from model import (
    Photo,
    Competition,
    Comment,
    Note,
    recently_completed_competitions,
)


class Home(BaseHandler):
    def get(self):
        user_id, user = self.get_user()
        data = {
            #'page_title': 'Monthly Photographs 2013',
            'photos': self.random_images(4),
            'user': user,
            'competitions': self.competitions_in_progress(),
            'comments': self.recent_comments(),
            'results': self.recent_results(),
            'notes': Note.recent_notes(),
        }
        self.render('home.html', **data)

    def random_images(self, number=3):
        photo_keys = list(Photo.query().fetch(keys_only=True))
        shuffle(photo_keys)
        photos = []
        i = 0
        for key in photo_keys:
            photo = key.get()
            if photo.total_score == 0:
                # only view photos belonging to completed competition -
                # assuming all photos in completed competitions have non-zero
                # score
                # TODO: better way to implement this
                logging.info("random images: image can't be used")
                continue
            title = photo.title
            if not title:
                title = 'Untitled'
            user = photo.user.get().username
            photos.append((i, key.id(), photo.url(size=800), title, user))
            i += 1
            if len(photos) == number:
                # Once we have the required number of photos, we can quit the
                # loop
                break
        logging.info('random photos: %s', photos)
        return photos

    def competitions_in_progress(self):
        competition_data = []
        for comp in Competition.in_progress():
            competition_data.append((
                comp.key.id(),
                comp.title,
                comp.description,
                comp.year,
                MONTHS[comp.month],
                comp.get_status()
            ))
        return competition_data

    def recent_comments(self):
        comments = []
        for comment in Comment.recent_comments(7):
            text = markdown.markdown(
                comment.text,
                output_format='html5',
                safe_mode='replace',
            )
            comments.append((
                text,
                comment.user.id(),
                comment.user.get().username,
                comment.photo.id(),
                comment.format_date()
            ))
        return comments

    def recent_results(self):
        results = []
        for comp, photos in recently_completed_competitions():
            new_photos = []
            classes = ('badge-first', 'badge-second', 'badge-third')
            for photo in photos:
                logging.info(photo.position)
                new_photos.append((
                    ordinal(photo.position),
                    classes[photo.position - 1],
                    photo.total_score,
                    photo.user.id(),
                    photo.user.get().username,
                ))
            results.append((comp, new_photos))
        return results


class About(BaseHandler):
    def get(self):
        user_id, user = self.get_user()

        data = {
            'user': user,
            'page_title': 'About'
        }

        self.render('about.html', **data)


app = webapp2.WSGIApplication(
    [
        ('/', Home),
        ('/about', About)
    ],
    debug=True
)
