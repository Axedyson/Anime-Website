import re

from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, TextAreaField, MultipleFileField, FieldList, HiddenField, FormField
from wtforms.validators import DataRequired, Regexp, InputRequired, Length, Optional

from config import ALLOWED_FILE_EXTENSIONS
from utils import exceeds_limit_for_profile_pic, CustomBaseForm, strip_zeros, proper_data_in_file, \
    optional_multiple_files, exceeds_file_amount_limit, files_allowed, exceeds_limit_for_email_pics, \
    proper_data_in_multiple_files, strip_filter, _is_not_equal_to_tac


class AdminCharacterForm(CustomBaseForm):
    name = StringField(
        'Name',
        validators=[
            DataRequired(message="The anime character must have a name, Admin. "),
            Regexp(r'^(?:(?![^\w\s]|[\w]\s{2,}[\w]|_).[\.]*)*$',
                   message="Only letters, numbers, punctuations and a single whitespace between groups of characters "
                           "are acceptable. "),
            Length(max=100, message="Can't have a name longer than 100 letters/characters. ")
        ]
    )
    universe = StringField(
        'Universe',
        validators=[
            DataRequired(message="The character must come from some universe right? Please define the universe. "),
            Regexp(r'^(?:(?!\s{2,}).)*$', message="Only one whitespace character between letters/characters are "
                                                  "acceptable. "),
            Length(max=100, message="Can't have text longer than 100 letters/characters. ")
        ]
    )
    universe_action = SelectField(
        'Universe action',
        validators=[
            InputRequired(message="Please choose an action to perform regarding the universe for the anime character. ")
        ],
        choices=[('', 'Choose...'), ('True', 'Add to existing universe'), ('False', 'Create new universe and then add')]
    )
    categories = FieldList(StringField(
        filters=[strip_filter],
        validators=[
            Optional(),
            Regexp(r'^(?:(?!\s{2,}).)*$', message="Only one whitespace character between letters/characters are "
                                                  "acceptable. "),
            Length(max=30, message="Can't have text longer than 30 letters/characters. "),
            _is_not_equal_to_tac
        ]
    ), max_entries=15, label="Edit Categories")
    character_picture = FileField(
        'Picture/GIF',
        validators=[
            Optional(),
            FileAllowed(ALLOWED_FILE_EXTENSIONS, message=f".{', .'.join(ALLOWED_FILE_EXTENSIONS)} are the only file "
            f"extensions that are acceptable! "),
            exceeds_limit_for_profile_pic,
            proper_data_in_file
        ],
    )
    age = StringField(
        'Age',
        filters=[strip_zeros],
        validators=[
            DataRequired(message="Please specify an age for the character it can be unknown. "),
            Regexp(r'^unknown$|^infinite$|^-?[\d]+(\.[\d]+)?\+?$', re.IGNORECASE,
                   message="Only \"Unknown\", \"Infinite\", and one \".\" within a number as decimal separator are"
                           " acceptable. "),
            Length(max=100, message="Can't have an age with more than 100 digits/characters. ")
        ]
    )
    height = StringField(
        'Height',
        filters=[strip_zeros],
        validators=[
            DataRequired(message="Please specify a height for the character it can be unknown. "),
            Regexp(r'^unknown$|^infinite$|^-?[\d]+(\.[\d]+)?\+?$', re.IGNORECASE,
                   message="Only \"Unknown\", \"Infinite\", and one \".\" within a number as decimal separator are"
                           " acceptable. "),
            Length(max=100, message="Can't have a height with more than 100 digits/characters. ")
        ]
    )
    weight = StringField(
        'Weight',
        filters=[strip_zeros],
        validators=[
            DataRequired(message="Please specify a weight for the character it can be unknown. "),
            Regexp(r'^unknown$|^infinite$|^-?[\d]+(\.[\d]+)?\+?$', re.IGNORECASE,
                   message="Only \"Unknown\", \"Infinite\", and one \".\" within a number as decimal separator are"
                           " acceptable. "),
            Length(max=100, message="Can't have a weight with more than 100 digits/characters. ")
        ]
    )
    species = StringField(
        'Species',
        validators=[
            DataRequired(message="Specify a species, can be \"Unknown\". "),
            Regexp(r'^(?:(?!\s{2,}).)*$', message="Only one whitespace character between letters/characters are "
                                                  "acceptable. "),
            Length(max=100, message="Can't have text longer than 100 letters/characters. ")
        ]
    )
    gender = SelectField(
        'Gender',
        validators=[
            InputRequired(message="Please choose a gender for the awesome anime character. "),
        ],
        choices=[('', 'Choose...'), ('Female', 'Female'), ('Male', 'Male'), ('Hermaphrodite', 'Hermaphrodite'),
                 ('Genderless', 'Genderless'), ('Unknown', 'Unknown')]
    )
    occupation = StringField(
        'Occupation',
        validators=[
            DataRequired(message="Specify an occupation, can be \"Unknown\". "),
            Regexp(r'^(?:(?!\s{2,}).)*$', message="Only one whitespace character between letters/characters are "
                                                  "acceptable. "),
            Length(max=100, message="Can't have text longer than 100 letters/characters. ")
        ]
    )
    status = SelectField(
        'Status',
        validators=[
            InputRequired(message="Please choose a status for the awesome anime character. ")
        ],
        choices=[('', 'Choose...'), ('Alive', 'Alive'), ('Dead', 'Dead'), ('Missing', 'Missing'), ('Gone', 'Gone'),
                 ('Unknown', 'Unknown')]
    )
    description = TextAreaField(
        'Description',
        validators=[
            DataRequired(message="The anime character must have a description, could be a link. "),
            Regexp(r'^(?:(?!\s{2,}).[\n\r]*)*$', message="Only one whitespace character between letters/characters "
                                                         "are acceptable. "),
            Length(max=10000, message="Can't have a description longer than 10.000 letters/characters. ")
        ]
    )
    official = SelectField(
        'Official or unofficial',
        validators=[
            InputRequired(message="Is the anime character official or not. ")
        ],
        choices=[('', 'Choose...'), ('True', 'Official'), ('False', 'Unofficial')]
    )


class AdminMailForm(CustomBaseForm):
    reason = StringField(
        'Reason',
        validators=[
            DataRequired(message="Please choose the reason/subject behind the message. "),
            Regexp(r'^(?:(?!\s{2,}).)*$', message="Only one whitespace character between letters/characters are "
                                                  "acceptable. "),
            Length(max=100, message="Can't have text longer than 100 letters/characters. ")
        ]
    )
    message = TextAreaField(
        'Message',
        validators=[
            DataRequired(message="Please provide a message. "),
            Length(max=10000, message="Can't have a message longer than 10.000 letters/characters sorry. ")
        ]
    )
    image_attachments = MultipleFileField(
        'Choose images...',
        validators=[
            optional_multiple_files,
            exceeds_file_amount_limit,
            files_allowed,
            exceeds_limit_for_email_pics,
            proper_data_in_multiple_files
        ]
    )


class AdminUniverseCategoryForm(CustomBaseForm):
    category = StringField(
        filters=[strip_filter],
        validators=[
            Optional(),
            Regexp(r'^(?:(?!\s{2,}).)*$', message="Only one whitespace character between letters/characters are "
                                                  "acceptable. "),
            Length(max=30, message="Can't have text longer than 30 letters/characters. "),
            _is_not_equal_to_tac
        ]
    )
    category_id = HiddenField(
        validators=[
            Optional()
        ]
    )


class AdminUniverseForm(CustomBaseForm):
    universe = StringField(
        'New Universe Name',
        validators=[
            DataRequired(message="Please specify the new name for the universe. "),
            Regexp(r'^(?:(?!\s{2,}).)*$', message="Only one whitespace character between letters/characters are "
                                                  "acceptable. "),
            Length(max=100, message="Can't have text longer than 100 letters/characters. "),
        ]
    )
    categories = FieldList(
        FormField(AdminUniverseCategoryForm),
        max_entries=15,
        label="Edit Categories")
