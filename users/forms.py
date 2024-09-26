from flask_wtf import RecaptchaField
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, BooleanField, HiddenField, SelectField, TextAreaField, MultipleFileField
from wtforms.validators import DataRequired, Regexp, Email, Length, \
    EqualTo, Optional, InputRequired

from config import ALLOWED_FILE_EXTENSIONS
from users.utils import email_does_exist, email_does_not_exist, has_not_agreed
from utils import exceeds_limit_for_profile_pic, CustomBaseForm, proper_data_in_file, proper_data_in_multiple_files, \
    exceeds_limit_for_email_pics, files_allowed, exceeds_file_amount_limit, optional_multiple_files


class AuthenticatedContactForm(CustomBaseForm):
    email = StringField(
        'Email',
        validators=[
            DataRequired(message="You need to provide an email which we can use to reach you back on. "),
            Email(message="Not a valid email address sorry. "),
            Length(max=100, message="Can't have an email longer than 100 letters/characters. "),
        ]
    )
    reason = SelectField(
        'Reason',
        validators=[
            InputRequired(message="Please choose the reason behind the message. "),
        ],
        choices=[('', 'Choose...'),
                 ('Rename universe', 'Rename a universe'),
                 ('Edit category', 'Rename/Remove/Add a category to a universe'),
                 ('Edit character', 'Change/Remove an anime character'),
                 ('Report character', 'Report an anime character'),
                 ('Report comment', 'Report a user comment'),
                 ('Report picture', 'Report a character/profile picture'),
                 ('Report bug', 'Report a bug'),
                 ('Server error', 'Internal Server Error'),
                 ('Website appreciation', 'Appreciate the website xD'),
                 ('Business', 'Business related'),
                 ('Other', 'Other')]
    )
    message = TextAreaField(
        'Message',
        description="If your message is related to a specific anime character then include that anime character by URL "
                    "in your message.",
        validators=[
            DataRequired(message="Please provide a message. "),
            Length(max=10000, message="Can't have a message longer than 10.000 letters/characters sorry. ")
        ]
    )
    image_attachments = MultipleFileField(
        'Choose images...',
        description="NOTE: Attaching images is optional, we also only accept a maximum of 5 images.",
        validators=[
            optional_multiple_files,
            exceeds_file_amount_limit,
            files_allowed,
            exceeds_limit_for_email_pics,
            proper_data_in_multiple_files
        ]
    )


class PublicContactForm(AuthenticatedContactForm):
    name = StringField(
        'Name',
        validators=[
            DataRequired(message="Please provide a name that we can call you. "),
            Regexp(r'^(?:(?![^\w\s]|[\w]\s{2,}[\w]|_).)*$',
                   message="Only letters, numbers and a single whitespace between groups of characters are "
                           "acceptable. "),
            Length(min=2, max=35, message="Can't have a name less than 2 and longer than 35 letters/characters. ")
        ]
    )
    recaptcha = RecaptchaField(
        'reCAPTCHA',
    )


class EmailSettings(CustomBaseForm):
    news_letters = BooleanField('Receive news letters')
    user_pings = BooleanField('Receive user pings')


class RegisterForm(CustomBaseForm):
    username = StringField(
        'Username',
        validators=[
            DataRequired(message="Dude, you must provide a username so others can call you by your username. "),
            Regexp(r'^(?:(?![^\w\s]|[\w]\s{2,}[\w]|_).)*$',
                   message="Only letters, numbers and a single whitespace between groups of characters are "
                           "acceptable. "),
            Length(min=2, max=35, message="Can't have a username less than 2 and longer than 35 letters/characters. ")
        ]
    )
    profile_picture = FileField(
        'Picture/GIF',
        description="Having a profile picture is not required. NOTE: Picture quality will be reduced a bit!",
        validators=[
            Optional(),
            FileAllowed(ALLOWED_FILE_EXTENSIONS, message=f".{', .'.join(ALLOWED_FILE_EXTENSIONS)} are the only file "
            f"extensions that are acceptable! "),
            exceeds_limit_for_profile_pic,
            proper_data_in_file
        ]
    )
    email = StringField(
        'Email',
        validators=[
            DataRequired(message="You need to provide an email so we can contact you about important stuff. "),
            Email(message="Not a valid email address sorry. "),
            Length(max=100, message="Can't have an email longer than 100 letters/characters. "),
            email_does_not_exist
        ]
    )
    password = PasswordField(
        'Password',
        description="Note: whitespace is being trimmed at the beginning and end of the password.",
        validators=[
            DataRequired(message="A password is required. Note whitespace is being trimmed. "),
            Length(min=7, max=99, message="Password must be at least 7 and less than 100 letters/characters. "
                                          "Note whitespace is being trimmed. ")
        ]
    )
    password2 = PasswordField(
        'Confirm Password',
        validators=[
            DataRequired(message='Your password is also required here. '),
            EqualTo('password', message="Passwords must match. ")
        ]
    )
    # Custom label is in the register.html template
    agree = BooleanField(
        validators=[has_not_agreed]
    )
    # Custom error message is in the register.html template
    recaptcha = RecaptchaField('reCAPTCHA')
    remember_me = BooleanField('Remember me')
    time = HiddenField(
        validators=[
            DataRequired()
        ]
    )


class LoginForm(CustomBaseForm):
    email = StringField(
        'Email',
        validators=[
            DataRequired(message="Emails are required for us to identify your accounts unique email. "),
        ]
    )
    password = PasswordField(
        'Password',
        validators=[
            DataRequired(message="Your password is required dude xD. ")
        ]
    )
    remember_me = BooleanField('Remember me')
    time = HiddenField(
        validators=[
            DataRequired()
        ]
    )


class UsernameForm(CustomBaseForm):
    username = StringField(
        'New Username',
        validators=[
            DataRequired(message="Dude, you must provide a username so others can call you by your username. "),
            Regexp(r'^(?:(?![^\w\s]|[\w]\s{2,}[\w]|_).)*$',
                   message="Only letters, numbers and a single whitespace between groups of characters are "
                           "acceptable. "),
            Length(min=2, max=35, message="Can't have a username less than 2 and longer than 35 letters/characters. ")
        ]
    )


class EmailFormForEmailChange(CustomBaseForm):
    email = StringField(
        'New Email',
        validators=[
            DataRequired(message="Please type your email address to proceed. "),
            Email(message="That is not a valid email address. "),
            Length(max=100, message="Can't have an email longer than 100 letters/characters. "),
            email_does_not_exist
        ]
    )
    current_password = PasswordField(
        'Current Password',
        validators=[
            DataRequired(message="Your password is required. ")
        ]
    )


class ResetPasswordForm(CustomBaseForm):
    current_password = PasswordField(
        'Current Password',
        validators=[
            DataRequired(message="Your current password is required. ")
        ]
    )
    new_password = PasswordField(
        'New Password',
        description="Note: whitespace is being trimmed at the beginning and end of the password.",
        validators=[
            DataRequired(message="A new password is required. Note whitespace is being trimmed. "),
            Length(min=7, max=99, message="Password must be at least 7 and less than 100 letters/characters. "
                                          "Note whitespace is being trimmed. ")
        ]
    )
    new_password2 = PasswordField(
        'Confirm New Password',
        validators=[
            DataRequired(message='Your new password is also required here. '),
            EqualTo('new_password', message="Passwords must match. ")
        ]
    )


class EmailFormForPasswordReset(CustomBaseForm):
    email = StringField(
        'Email',
        validators=[
            DataRequired(message="Please type your email address to proceed. "),
            email_does_exist
        ]
    )


class ResetPasswordWithTokenForm(CustomBaseForm):
    new_password = PasswordField(
        'New Password',
        description="Note: whitespace is being trimmed at the beginning and end of the password.",
        validators=[
            DataRequired(message="A new password is required. Note whitespace is being trimmed. "),
            Length(min=7, max=99, message="Password must be at least 7 and less than 100 letters/characters. "
                                          "Note whitespace is being trimmed. ")
        ]
    )
    new_password2 = PasswordField(
        'Confirm New Password',
        validators=[
            DataRequired(message='Your new password is also required here. '),
            EqualTo('new_password', message="Passwords must match. ")
        ]
    )


class ProfilePictureForm(CustomBaseForm):
    profile_picture = FileField(
        'New Picture/GIF',
        description="NOTE: Picture quality will be reduced a bit!",
        validators=[
            FileRequired(message="You need a picture for yourself. "),
            FileAllowed(ALLOWED_FILE_EXTENSIONS, message=f".{', .'.join(ALLOWED_FILE_EXTENSIONS)} are the only file "
            f"extensions that are acceptable! "),
            exceeds_limit_for_profile_pic,
            proper_data_in_file
        ]
    )


class DeleteForm(CustomBaseForm):
    delete_field = StringField(
        'Delete',
        description="Please type the word \"DELETE\".",
        validators=[
            DataRequired(message="You must type something at least, e.g. \"DELETE\" xD. "),
            Regexp(r'^DELETE$', message="It must be the exact word \"DELETE\" in all uppercase! ")
        ]
    )
    current_password = PasswordField(
        'Current Password',
        validators=[
            DataRequired(message="Your password is required. ")
        ]
    )
