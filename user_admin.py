#!/usr/bin/env python

import datetime
from google.appengine.api import mail
import logging
import re
import webapp2
from webapp2_extras.security import (
    generate_password_hash,
    check_password_hash,
    generate_random_string
)

from handler import BaseHandler
from model import User


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


class Logout(BaseHandler):
    def get(self):
        self.response.delete_cookie('userid')
        self.redirect('/')


class Login(BaseUser):
    def get(self):
        self.render('login.html', page_title="Login")

    def post(self):
        '''When the user clicks the submit button.'''
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
        user_id, user = self.get_user()
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
        user_id, user = self.get_user()
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


class Reset(BaseHandler):
    def get(self):
        data = {
            'page_title': 'Reset Password'
        }

        self.render('reset.html', **data)

    def post(self):
        email = self.request.get('email')
        logging.info('Reset password for email: %s', email)

        errors = []
        messages = []
        data = {
            'page_title': 'Reset Password',
            'errors': errors,
            'messages': messages
        }

        if not email:
            errors.append(
                'You forgot to enter an email address.'
            )
        else:
            user = User.user_from_email(email)
            if not user:
                errors.append(
                    'There is no account for this email address. Please check '
                    'that you typed in the correct email address.'
                )
                data['email'] = email
            else:
                expire = datetime.datetime.now()
                expire += datetime.timedelta(hours=1)
                code = generate_random_string(length=30)
                user.pass_reset_code = code
                user.pass_reset_expire = expire
                user.put()

                subject = 'HMPC: request to change password'
                logging.info('generated verify code: %s' % code)
                body = (
                    'This is an automated email form HMPC.\n\n'
                    'Please click the following link (or paste it into the '
                    'browser address bar) to change your password. This code '
                    'is valid for only one hour.\n\n'
                    'When you reset your password, you will be redirected to '
                    'the login page to login.\n\n'
                    'http://prelude-hmpc.appspot.com/password/%s\n'
                )
                mail.send_mail(
                    'gdrummondk@gmail.com',
                    email,
                    subject,
                    body % code
                )

                msg = (
                    'An email has been sent to the following email address: %s.'
                    ' Follow the instructions in the email to change your '
                    'password.'
                )
                messages.append(msg % email)

        self.render('reset.html', **data)


class Password(BaseHandler):
    def get(self, code):
        errors = []
        data = {
            'page_title': 'Reset Password',
            'errors': errors,
        }
        logging.info('code: %s', code)
        user = User.user_from_reset_code(code)
        if not user:
            errors.append(
                'This is not a valid password reset code. You can request '
                'another password reset code or contact admin for help.'
            )
        else:
            expired = user.pass_reset_expire < datetime.datetime.now()
            if expired:
                errors.append(
                    'The password reset code has expired - you submitted this '
                    'request more than an hour ago. Please make another '
                    'request to change your password.'
                )

        if errors:
            data['hide_form'] = True

        self.render('password.html', **data)

    def post(self, code):
        errors = []
        data = {
            'page_title': 'Reset Password',
            'errors': errors,
        }

        password = self.request.get('password')
        password_verify = self.request.get('password-verify')
        if not password or password != password_verify:
            errors.append(
                "Missing password or both passwords didn't match. Please try "
                "again."
            )
        else:
            user = User.user_from_reset_code(code)
            if not user:
                errors.append(
                    'No account for this reset code! Please contact admin.'
                )
            else:
                hash_pass = generate_password_hash(password)
                user.password = hash_pass
                user.pass_reset_code = None
                user.pass_reset_expire = None
                user.put()
                self.redirect('/login')
                return

        # reach here when there is an error to report
        self.render('password.html', **data)


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
        user_id, user = self.get_user()
        data = {
            'page_title': 'Contact',
            'user': user
        }
        if extra_data:
            data.update(extra_data)
        self.render('contact.html', **data)

routes = [
    ('/login', Login),
    ('/logout', Logout),
    ('/register', Register),
    ('/contact', Contact),
    ('/verify/(.+)', VerifyUser),
    ('/reset', Reset),
    ('/password/(.+)', Password)
]
app = webapp2.WSGIApplication(routes=routes, debug=True)
