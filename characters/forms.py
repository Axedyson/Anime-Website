import re

from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, SelectField, TextAreaField, FieldList
from wtforms.validators import DataRequired, Regexp, InputRequired, Length, Optional

from config import ALLOWED_FILE_EXTENSIONS
from utils import exceeds_limit_for_profile_pic, CustomBaseForm, strip_zeros, exceeds_limit_for_character_pics, \
    proper_data_in_file, strip_filter, _is_not_equal_to_tac


class CharacterForm(CustomBaseForm):
    name = StringField(
        'Name',
        validators=[
            DataRequired(message="The anime character must have a name dude xD. "),
            Regexp(r'^(?:(?![^\w\s]|[\w]\s{2,}[\w]|_).[\.]*)*$',
                   message="Only letters, numbers, punctuations, and a single whitespace between groups of characters "
                           "are acceptable. "),
            Length(max=100, message="Can't have a name longer than 100 letters/characters. ")
        ]
    )
    universe = StringField(
        'Universe',
        description="The universe which the character belongs to. For example Monkey D. Luffy belongs to the \"One "
                    "Piece\" universe.",
        validators=[
            DataRequired(message="The character must come from some universe right? Please define the universe. "),
            Regexp(r'^(?:(?!\s{2,}).)*$', message="Only one whitespace character between letters/characters are "
                                                  "acceptable. "),
            Length(max=100, message="Can't have text longer than 100 letters/characters. "),
        ]
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
    ), max_entries=15, label="Add Categories",
        description="If the specified universe is new on this website, "
                    "then suggest some categories to vote by or else we will! Example: \"Strength\", \"Ninjutsu\", "
                    "\"Genjutsu\", \"Intelligence\", etc. NOTE: We only accept a maximum of 15 categories.")
    character_picture = FileField(
        'Picture/GIF',
        description="Make sure the picture doesn't spoil anything. NOTE: Picture quality will be reduced a bit!",
        validators=[
            FileRequired(message="You need a picture for the anime character, just one. "),
            FileAllowed(ALLOWED_FILE_EXTENSIONS, message=f".{', .'.join(ALLOWED_FILE_EXTENSIONS)} are the only file "
            f"extensions that are acceptable! "),
            exceeds_limit_for_profile_pic,
            proper_data_in_file
        ]
    )
    age = StringField(
        'Age',
        description="Could be Unknown, Infinite, 25, 934.8, 100+, -21 etc.",
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
        description="Could be Unknown, Infinite, 1.5, 210, -43, 200+ etc.",
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
        description="Could be Unknown, Infinite, 68, 324.1, -3, 60+ etc.",
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
            DataRequired(message="Is it Unknown, a Human, a Chimera Ant, what? "),
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
        description="Could be highschool student, Pro Hunter, none, etc.",
        validators=[
            DataRequired(message="The character must have some kind of occupation or just none. "),
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
        description="The description MUST not be longer than 10000 characters/letters. "
                    "Please make sections that contain spoilers surrounded by brackets indicating the spoiler "
                    "information. You are allowed to just provide a link for the information/description, like "
                    "https://hunterxhunter.fandom.com/wiki/Gon_Freecss.",
        validators=[
            DataRequired(message="The anime character must have a description. "),
            Regexp(r'^(?:(?!\s{2,}).[\n\r]*)*$', message="Only one whitespace character between letters/characters "
                                                         "are acceptable. "),
            Length(max=10000, message="Can't have a description longer than 10.000 letters/characters. ")
        ]
    )
    official = SelectField(
        'Official or unofficial',
        description="Unofficial characters are homemade characters who haven't been seen in an anime or manga... "
                    "yet, maybe :).",
        validators=[
            InputRequired(message="You must know if the awesome anime character is official or not. ")
        ],
        choices=[('', 'Choose...'), ('True', 'Official'), ('False', 'Unofficial')]
    )


class CharacterPictureForm(CustomBaseForm):
    character_picture = FileField(
        'Picture/GIF',
        description="You are allowed to add pictures that spoils the anime character. NOTE: Picture quality will be "
                    "reduced a bit!",
        validators=[
            FileRequired(message="You need a picture for the anime character. "),
            FileAllowed(ALLOWED_FILE_EXTENSIONS, message=f".{', .'.join(ALLOWED_FILE_EXTENSIONS)} are the only file "
            f"extensions that are acceptable! "),
            exceeds_limit_for_character_pics,
            proper_data_in_file
        ]
    )


class CategoryForm(CustomBaseForm):
    category = SelectField(
        choices=[('', 'Top Anime Characters')]
    )
