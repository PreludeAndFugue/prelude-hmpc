#!/usr/bin/env python

from google.appengine.api import mail
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
import re
import webapp2
from webapp2_extras.security import (
    generate_password_hash,
    check_password_hash,
    generate_random_string
)

import logging

from handler import BaseHandler
from model import Competition, User, Photo, UserComp
from helper import OPEN


class BaseUser(BaseHandler):
    def valid_name(self, name):
        USER_RE = re.compile("^[a-zA-Z0-9_-]{3,20}$")
        return USER_RE.match(name)

    def valid_pass(self, password):
        PASS_RE = re.compile("^.{3,20}$")
        return PASS_RE.match(password)

    def valid_email(self, email):
        EMAIL_RE = re.compile("^[\S]+@[\S]+\.[\S]+$")
        return EMAIL_RE.match(email)

    def validate_user(self, user, password):
        hash_pass = user.password
        return check_password_hash(password, hash_pass)

    def set_cookie(self, user):
        user_id = user.key().id()
        username = user.username
        template = '%d|%s' % (user_id, username)
        value = self.cookie_serializer.serialize('userid', template)
        self.response.set_cookie('userid', value)


class Login(BaseUser):
    def get(self):
        self.render('login.html', page_title="Login")

    def post(self):
        email = self.request.get('email', '')
        password = self.request.get('password', '')

        # collect the errors
        errors = []

        # data for the page if it has to be re-rendered because of invalid login
        data = {
            'errors': errors,
            'email': email,
            'page_title': 'Login'
        }

        # catch errors in the form
        if not email:
            errors.append('You forgot to enter an email address.')
        if not password:
            errors.append('You forgot to enter a password.')
        if errors:
            self.render('login.html', **data)
            return

        logging.warning('This is the email address: %s' % repr(email))

        user = User.user_from_email(email)

        # invalid email address or password
        if not user or not self.validate_user(user, password):
            errors.append('Invalid email address or password.')
            self.render('login.html', **data)

            log_msg = 'Login: invalid email address or password. %s'
            logging.warning(log_msg, user)

            return

        # unverified user
        if not user.verified:
            errors.append('Your account has not yet been verified. '
                'You should have received an email with a verification link. '
                'Please check your mail (and your spam folder). If you have '
                'not received the email, please contact admin.')
            data['contact'] = True
            self.render('login.html', **data)
            logging.warning('Login: unverified user attempted login. %s', user)
            return

        # user exists - set cookie and redirect
        self.set_cookie(user)
        self.redirect('/user')


class Logout(BaseHandler):
    def get(self):
        self.response.delete_cookie('userid')
        self.redirect('/')


class Register(BaseUser):
    def get(self):
        user = self.get_user()
        data = {
            'page_title': 'Registration',
            'user': user
        }
        if not user:
            self.render('register.html', **data)
        else:
            self.render('register_no.html', **data)

    def post(self):
        username = self.request.get('username', '')
        password = self.request.get('password', '')
        validate = self.request.get('validate', '')
        email = self.request.get('email', '')

        # collect error text strings
        errors = self.input_errors(username, password, validate, email)

        data = {
            'username': username,
            'email': email,
            'errors': errors,
            'page_title': 'Registration'
        }

        if errors:
            self.render('register.html', **data)
        else:
            # no errors so create new user
            hash_pass = generate_password_hash(password)
            verify_code = generate_random_string(length=30)
            user = User(username=username, password=hash_pass, email=email,
                verify_code=verify_code)
            user.put()
            logging.info('Register: successfully created user: %s', user)
            # send email to admin about new user
            body = 'Username: %s\nEmail: %s' % (user.username, user.email)
            mail.send_mail_to_admins(
                'gdrummondk@gmail.com',
                'hmpc: new user',
                body
            )
            # send user verification email to user's email address
            self.send_verification_email(username, email, verify_code)
            # set the cookie
            #self.set_cookie(user)
            self.redirect('/')

    def send_verification_email(self, username, email, verify_code):
        to = '%s <%s>' % (username, email)
        subject = 'Account verification for HMPC'
        verify = '%s/%s' % (username, verify_code)

        logging.info('generated verify code: %s' % verify)

        body = (
            'This is an automated email form HMPC.\n\n'
            'Please click the following link (or paste it into the browser '
            'address bar) to verify your user account on HMPC.\n\n'
            'http://prelude-hmpc.appspot.com/verify/%s\n'
        )
        mail.send_mail('gdrummondk@gmail.com', to, subject, body % verify)

    def input_errors(self, username, password, validate, email):
        '''Return a list of errors with user registration data.'''
        # collect error text strings
        errors = []

        # username errors
        if not username:
            errors.append('You forgot to enter a username.')
            logging.warning('Register: forgot username.')
        elif not self.valid_name(username):
            errors.append('A Valid user name can contain only the characters '
                'a-z, A-Z, 0-9, _ (underscore) and - (dash) and must be at '
                'least 3 characters long.')
            logging.warning('Register: invalid username: %s.', username)

        user = User.user_from_name(username)
        if user:
            # user name already exists
            errors.append('That user name already exists, please choose '
                'another one.')
            logging.warning('Register: username already in use. %s', user)

        # email errors
        if not email:
            errors.append('You forgot to enter an email address.')
            logging.warning('Register: forgot email.')
        elif not self.valid_email(email):
            errors.append(
                'Check your email address - it may not '
                'be correct.')
            logging.warning('Register: invalid email: %s', email)
        else:
            # maybe the email address is being used by another user - can't
            # have more than one user with the same email address because the
            # email address is used as login id
            user = User.user_from_email(email)
            if user:
                # email address is attached to other user
                errors.append(
                    'This email address is being used by another user'
                )
                msg = 'Register: email address already in use: %s'
                logging.warning(msg, email)

        # password errors
        if not password or not validate:
            errors.append('You forgot to enter your password twice.')
            logging.warning('Register: forgot to enter password twice.')
        elif password != validate:
            msg = "Your password confirmation doesn't match your password."
            errors.append(msg)
            logging.warning('Register: validate != password.')
        if not self.valid_pass(password):
            errors.append(
                'Not a valid password - it must contain at least '
                '3 characters.')
            logging.warning('Register: invalid password.')

        return errors


class VerifyUser(BaseUser):
    def get(self, verify_code_hash):
        user = self.get_user()
        data = {
            'user': user,
            'page_title': 'User Verification'
        }

        username, verify_code = verify_code_hash.split('/')
        test_user = User.user_from_name(username)

        if not test_user:
            logging.warning('VerifyUser: user not found in db.')
            self.render('verify_fail.html', **data)
            return

        if test_user.verify_code == verify_code:
            test_user.verified = True
            test_user.verify_code = None
            test_user.put()
            logging.info('VerifyUser: user succesfully verified.')
            self.render('verify.html', **data)
        else:
            self.render('verify_fail.html', **data)


class UserPage(BaseHandler):
    def get(self):
        user = self.get_user()
        if not user:
            self.render('user_no.html', page_title='User')
            return

        open_comps = Competition.get_by_status(OPEN)
        open_comps_no_photos = []
        for oc in open_comps:
            usercomp = UserComp.get_usercomp(user, oc)
            if not usercomp:
                open_comps_no_photos.append(oc)

        upload_url = None
        if open_comps_no_photos:
            upload_url = blobstore.create_upload_url('/upload')

        #logging.info(open_comps)
        logging.info(open_comps_no_photos)

        photos = []
        for p in Photo.user_photos(user):
            title, url, thumb, date = p.data()
            photos.append((p, title, url, thumb, date))

        #logging.info(comp_photo)

        data = {
            'user': user,
            'page_title': 'User',
            'page_subtitle': user.username,
            'upload_url': upload_url,
            'photos': photos,
            'open_comps': open_comps_no_photos,
        }
        self.render('user.html', **data)

    def post(self):
        # submitting a photograph - handled by Upload class
        pass


class Upload(BaseHandler, blobstore_handlers.BlobstoreUploadHandler):
    def get(self):
        self.redirect('/user')

    def post(self):
        user = self.get_user()
        user_id, username = self.get_cookie()
        upload_files = self.get_uploads('photo-submit')

        if not upload_files:
            data = {
                'user': user,
                'page_title': 'Upload error',
                'error': 'You forgot to select an image file.'
            }
            self.render('upload_error.html', **data)
            return

        blob_info = upload_files[0]

        #logging.info('blob info %s' % dir(blob_info))
        logging.info(blob_info.kind())
        logging.info(blob_info.properties())
        logging.info(blob_info.size)

        if blob_info.content_type != 'image/jpeg':
            # only store jpegs - delete file otherwise
            blob_info.delete()
            data = {
                'user': user,
                'page_title': 'Upload error',
                'error': (
                    'You tried to upload a file which was '
                    'not a jpeg image.'
                )
            }
            self.render('upload_error.html', **data)
            return

        photo_title = self.request.get('photo-title')
        comp_id = int(self.request.get('comp-id'))
        comp = Competition.get_by_id(comp_id)

        # add photo details to database
        photo = Photo(
            user=user,
            title=photo_title,
            blob=blob_info,
            competition=comp
        )
        photo.put()

        # add UserComp record
        usercomp = UserComp(user=user, comp=comp)
        usercomp.put()

        self.redirect('/user')


class Contact(BaseHandler):
    def get(self):
        self.display()

    def post(self):
        name = self.request.get('name', '')
        email = self.request.get('email', '')
        message = self.request.get('message', '')

        if not name or not email or not message:
            data = {
                'message_sent': True,
                'alert_type': 'alert-error',
                'message': 'No message sent - complete all fields.'
            }
        else:
            body = 'name: %s\nemail: %s\n\n%s' % (name, email, message)
            mail.send_mail_to_admins('gdrummondk@gmail.com', 'hmpc', body)
            data = {
                'message_sent': True,
                'alert_type': 'alert-success',
                'message': 'You have sent a message to the administrators.'
            }

        self.display(data)

    def display(self, extra_data=None):
        data = {
            'page_title': 'Contact',
            'user': self.get_user()
        }
        if extra_data:
            data.update(extra_data)
        self.render('contact.html', **data)

routes = [
    ('/login', Login),
    ('/logout', Logout),
    ('/register', Register),
    ('/user', UserPage),
    ('/contact', Contact),
    ('/upload', Upload),
    ('/verify/(.+)', VerifyUser)
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
