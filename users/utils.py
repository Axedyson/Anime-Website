from urllib.parse import urlparse, urljoin

from flask import request
from wtforms import ValidationError, StringField

from models import User


def _is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def email_does_not_exist(form, field: StringField):
    if User.select().where(User.email == field.data.lower()).exists():
        raise ValidationError('User with that email already exists in our database. ')


def email_does_exist(form, field: StringField):
    if not User.select().where(User.email == field.data.lower()).exists():
        raise ValidationError("User with that email doesn't exist in our database. ")


def has_not_agreed(form, field):
	if field.data == False:
		raise ValidationError('You must accept the Cookies Policy, Privacy Policy, and Terms Of Use agreement. ')
