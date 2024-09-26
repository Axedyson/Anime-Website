import io
import os
import struct
import warnings
from datetime import datetime

from PIL import Image, ImageOps
from dateutil.parser import parser as isoformat_parser
from flask import abort
from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from hashids import Hashids
from wtforms import MultipleFileField, FieldList, StringField
from wtforms.validators import ValidationError, StopValidation

from config import ALLOWED_FILE_EXTENSIONS
from main import app

# If huge malicious files comes in, they will be interpreted as an error, hopefully...

warnings.simplefilter('error', Image.DecompressionBombWarning)

# I made this class for simulating a file object since the upload method in the models module only accept
# a file like object with the content_type attribute and the read method.
class SmallFileWrapper:

    def __init__(self, stream, content_type):
        self.content_type = content_type
        self.stream = stream

    def read(self):
        return self.stream


# Resize util method

def resize_image(width: int, height: int, image_file):
    ext = os.path.splitext(image_file.filename)[1].lower()
    if ext == '.gif':
        return image_file
    img = Image.open(image_file)
    new_img = ImageOps.fit(img, (width, height), Image.ANTIALIAS)
    img_byte_arr = io.BytesIO()
    new_img.save(img_byte_arr, img.format, quality=90, optimize=True)
    file = SmallFileWrapper(img_byte_arr.getvalue(), content_type=image_file.content_type)
    return file


def image_size_reducer(image_file):
    ext = os.path.splitext(image_file.filename)[1].lower()
    if ext == '.gif':
        return image_file
    img = Image.open(image_file)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, img.format, quality=33, optimize=True)
    file = SmallFileWrapper(img_byte_arr.getvalue(), content_type=image_file.content_type)
    return file


def _return_proper_datetime(time: str):
    try:
        time = isoformat_parser().parse(time)
    except (ValueError, OverflowError):
        time = datetime.now()
    return datetime(
        year=time.year,
        month=time.month,
        day=time.day,
        hour=time.hour,
        minute=time.minute,
        second=time.second,
        microsecond=time.microsecond
    )


# Hashid util methods
# I'm having the extra salt parameter so all the public records can have a different salt each

def create_char_hashid(character_id, extra_salt):
    hashids = Hashids(min_length=6, salt=app.config['SECRET_KEY'] + extra_salt)
    hashid = hashids.encode(character_id)
    return hashid


def decode_char_hashid(hashid, extra_salt):
    hashids = Hashids(min_length=6, salt=app.config['SECRET_KEY'] + extra_salt)
    character_id = hashids.decode(hashid)
    if not character_id:
        abort(404)
    return character_id[0]  # I'm selecting the first element since this returns a tuple with one element in it (the id)


def create_pic_hashid(picture_id, extra_salt):
    hashids = Hashids(min_length=8, salt=app.config['PIC_URL_SALT'] + extra_salt)
    hashid = hashids.encode(picture_id)
    return hashid


def decode_pic_hashid(hashid, extra_salt):
    hashids = Hashids(min_length=8, salt=app.config['PIC_URL_SALT'] + extra_salt)
    picture_id = hashids.decode(hashid)
    if not picture_id:
        abort(404)
    return picture_id[0]  # I'm selecting the first element since this returns a tuple with one element in it (the id)


# Form util methods

class CustomBaseForm(FlaskForm):
    class Meta:
        def bind_field(self, form, unbound_field, options):
            filters = unbound_field.kwargs.get('filters', [])
            if unbound_field.field_class is not FieldList and strip_filter not in filters:
                filters.append(strip_filter)
            return unbound_field.bind(form=form, filters=filters, **options)


def strip_filter(value):
    if value is not None and hasattr(value, 'strip'):
        return value.strip()
    return value


def strip_zeros(user_input):
    if user_input is not None and len(user_input):
        if user_input == 'infinite' or user_input == 'unknown':
            return user_input
        first_char = [user_input[0], False]
        last_char = [user_input[-1], False]
        if first_char[0] == '-':
            user_input = user_input[1:]
            first_char[1] = True
        if last_char[0] == '+':
            last_char[1] = True
            user_input = user_input[:-1]
        if '.' in user_input:
            proper_input = user_input.strip('0')
            if proper_input[-1] == '.':
                proper_input = proper_input[:-1]
        else:
            proper_input = user_input.lstrip('0')
        if first_char[1]:
            proper_input = f"{'-'}{proper_input}"
        if last_char[1]:
            proper_input = f"{proper_input}{'+'}"
        return proper_input
    return user_input


def _is_not_equal_to_tac(form, field: StringField):
    if field.data.lower() == 'top anime characters':
        raise ValidationError("The category \"Top Anime Characters\" is a reserved category, please choose another. ")


def _exceeds_specific_limit(field: FileField, picture_limit: int, gif_limit: int):
    file = field.data
    ext = os.path.splitext(file.filename)[1].lower()
    limit = gif_limit if ext == '.gif' else picture_limit
    if len(file.read()) / (1_024 * 1_024) > limit:
        raise ValidationError(f'Size is too big, must not be over {limit} MB for {ext} files! ')
    file.seek(0)


def exceeds_limit_for_profile_pic(form, field: FileField):
    _exceeds_specific_limit(field, picture_limit=5, gif_limit=2)


def exceeds_limit_for_character_pics(form, field: FileField):
    _exceeds_specific_limit(field, picture_limit=2, gif_limit=1)


def optional_multiple_files(form, field: MultipleFileField):
    if not field.data[0].filename:
        field.errors[:] = []
        raise StopValidation()


def exceeds_file_amount_limit(form, field: MultipleFileField):
    if len(field.data) > 5:
        raise StopValidation("We don't accept more than 5 images, sorry. ")


def files_allowed(form, field: MultipleFileField):
    for file in field.data:
        filename = file.filename.lower()
        if not any(filename.endswith(f'.{ext}') for ext in ALLOWED_FILE_EXTENSIONS):
            raise StopValidation(f".{', .'.join(ALLOWED_FILE_EXTENSIONS)} are the only file extensions that are "
                                 f"acceptable! ")


def exceeds_limit_for_email_pics(form, field: MultipleFileField):
    picture_limit = 2
    gif_limit = 1
    errors = False
    error_files = []
    for file in field.data:  # going to loop through every file so we can print out every single file that is too big
        ext = os.path.splitext(file.filename)[1].lower()
        limit = gif_limit if ext == '.gif' else picture_limit
        if len(file.read()) / (1_024 * 1_024) > limit:
            error_files.append(file.filename)
            errors = True
        else:
            file.seek(0)
    if errors:
        raise ValidationError(f"The following image(s): {', '.join(error_files)} exceeds the allowed file size for "
                              f".gif ({gif_limit} MB) and for other image files ({picture_limit} MB). ")


# There are probably more ways and more efficient ones to check if a file is a proper image file
def proper_data_in_multiple_files(form, field: MultipleFileField):
    errors = False
    error_files = []
    for file in field.data:  # going to loop through every file so we can print out every single file that is corrupted
        img = Image.open(file)
        ext = os.path.splitext(file.filename)[1].lower()
        if ext == '.gif':
            if not img.is_animated:
                error_files.append(file.filename)
                errors = True
                break
        try:
            img.verify()
        # I'm catching these 3 exceptions because they can apparently be thrown
        except (IOError, SyntaxError, struct.error):
            error_files.append(file.filename)
            errors = True
        file.seek(0)
    if errors:
        raise ValidationError(f"The following image(s): {', '.join(error_files)} is either empty or corrupted or NOT "
                              f"animated gif file(s)! ")


# There are probably more ways and more efficient ones to check if a file is a proper image file
def proper_data_in_file(form, field: FileField):
    file = field.data
    img = Image.open(file)
    ext = os.path.splitext(file.filename)[1].lower()
    if ext == '.gif':
        if not img.is_animated:
            raise ValidationError("The gif file is not animated! ")
    try:
        img.verify()
    # I'm catching these 3 exceptions because they can apparently be thrown
    except (IOError, SyntaxError, struct.error):
        raise ValidationError("The image is either empty or corrupted! ")
    file.seek(0)
