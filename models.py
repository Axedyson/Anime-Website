from flask_login import UserMixin
from google.cloud import storage
from peewee import *
from playhouse.pool import PooledPostgresqlDatabase
from playhouse.postgres_ext import TSVectorField

from config import DATABASE_PASSWORD, DATABASE_USER, MAX_CONNECTIONS, STALE_TIMEOUT, DATABASE_NAME, DATABASE_HOST
from main import login_manager

client = storage.Client()
bucket = client.get_bucket('topanimecharacters.com')

DATABASE = PooledPostgresqlDatabase(database=DATABASE_NAME, max_connections=MAX_CONNECTIONS, stale_timeout=STALE_TIMEOUT, user=DATABASE_USER, password=DATABASE_PASSWORD, host=DATABASE_HOST)


class User(UserMixin, Model):
    username = CharField()
    profile_picture = CharField(null=True)
    email = CharField(unique=True)
    password = CharField(max_length=100)
    joined_at = DateTimeField()
    last_log_in = DateTimeField(null=True)
    current_log_in = DateTimeField()
    email_confirmed = BooleanField(default=False)
    email_confirmed_on = DateTimeField(null=True)
    receive_email_news = BooleanField(default=True)
    receive_email_pings = BooleanField(default=True)
    is_admin = BooleanField(default=False)
    strikes = IntegerField(default=0)
    is_banned = BooleanField(default=False)

    @classmethod
    def create_user(cls, username, email, password, joined_at):
        with DATABASE.transaction():
            user = cls.create(
                username=username,
                email=email,
                password=password,
                joined_at=joined_at,
                current_log_in=joined_at
            )
        return user

    class Meta:
        database = DATABASE
        table_name = "User"


class CharacterTemp(Model):
    user = ForeignKeyField(null=True, model=User, backref='temp_characters', on_delete='SET NULL')
    name = CharField()
    universe = CharField()
    character_picture = CharField(null=True)
    age = CharField()
    height = CharField()
    weight = CharField()
    species = CharField()
    gender = CharField()
    occupation = CharField()
    status = CharField()
    description = TextField()
    official = BooleanField()
    user_striked = BooleanField(default=False)

    @classmethod
    def create_character(cls, name, universe, age, height, weight, species, gender, occupation, status,
                         description, official, user):
        with DATABASE.transaction():
            temp_character = cls.create(
                name=name,
                universe=universe,
                age=age,
                height=height,
                weight=weight,
                species=species,
                gender=gender,
                occupation=occupation,
                status=status,
                description=description,
                official=official,
                user=user
            )
        return temp_character

    class Meta:
        database = DATABASE
        table_name = "Character_temp"


class Universe(Model):
    name = CharField(unique=True)
    search_name = TSVectorField()

    @classmethod
    def create_universe(cls, name: str):
        with DATABASE.transaction():
            universe = cls.create(name=name, search_name=fn.to_tsvector(name))
        return universe

    class Meta:
        database = DATABASE
        table_name = "Universe"


class Character(Model):
    user = ForeignKeyField(null=True, model=User, backref='characters', on_delete='SET NULL')
    name = CharField()
    search_name = TSVectorField()
    universe = ForeignKeyField(null=True, model=Universe, backref='characters', on_delete='CASCADE')
    character_picture = CharField(null=True)
    age = CharField()
    height = CharField()
    weight = CharField()
    species = CharField()
    gender = CharField()
    occupation = CharField()
    status = CharField()
    description = TextField()
    official = BooleanField()
    user_striked = BooleanField(default=False)

    @classmethod
    def create_character(cls, name, universe, age, height, weight, species, gender, occupation, status,
                         description, official, user):
        with DATABASE.transaction():
            character = cls.create(
                name=name,
                search_name=fn.to_tsvector(name),
                universe=universe,
                age=age,
                height=height,
                weight=weight,
                species=species,
                gender=gender,
                occupation=occupation,
                status=status,
                description=description,
                official=official,
                user=user
            )
        return character

    class Meta:
        database = DATABASE
        table_name = "Character"


class CategoryTemp(Model):
    temporary_character = ForeignKeyField(model=CharacterTemp, backref='categories', on_delete='CASCADE')
    name = CharField()

    @classmethod
    def create_temp_category(cls, temporary_character: CharacterTemp, name: str):
        with DATABASE.transaction():
            cls.create(
                temporary_character=temporary_character,
                name=name
            )

    class Meta:
        database = DATABASE
        table_name = "Category_temp"
        indexes = (
            (('temporary_character', 'name'), True),
        )


class Category(Model):
    universe = ForeignKeyField(model=Universe, backref='categories', on_delete='CASCADE')
    name = CharField()

    @classmethod
    def create_category(cls, universe: Universe, name: str):
        with DATABASE.transaction():
            category = cls.create(
                universe=universe,
                name=name
            )
        return category

    class Meta:
        database = DATABASE
        table_name = "Category"
        indexes = (
            (('universe', 'name'), True),
        )


class CategoryRelationship(Model):
    category = ForeignKeyField(model=Category, on_delete='CASCADE')
    character = ForeignKeyField(model=Character, on_delete='CASCADE')
    user = ForeignKeyField(model=User, on_delete='CASCADE')
    score = IntegerField()

    @classmethod
    def create_category_relationship(cls, category: Category, character: Character, user: User, score: int):
        with DATABASE.transaction():
            cls.create(
                category=category,
                character=character,
                user=user,
                score=score
            )

    class Meta:
        database = DATABASE
        table_name = "Category_rel"
        indexes = (
            (('category', 'character', 'user'), True),
        )


class GlobalRating(Model):
    character = ForeignKeyField(model=Character, backref='global_rating', on_delete='CASCADE', unique=True)
    global_rank = IntegerField(null=True)
    universe_rank = IntegerField(null=True)
    overall_score = CharField(null=True)

    @classmethod
    def create_global_rating(cls, character: Character):
        with DATABASE.transaction():
            cls.create(
                character=character
            )

    class Meta:
        database = DATABASE
        table_name = "Global_rating"


class CategoryRating(Model):
    character = ForeignKeyField(model=Character, on_delete='CASCADE')
    category = ForeignKeyField(model=Category, on_delete='CASCADE')
    global_category_rank = IntegerField(null=True)
    universe_category_rank = IntegerField(null=True)
    category_score = CharField(null=True)

    @classmethod
    def create_category_rating(cls, character: Character, category: Category):
        with DATABASE.transaction():
            cls.create(
                character=character,
                category=category
            )

    class Meta:
        database = DATABASE
        table_name = "Category_rating"
        indexes = (
            (('character', 'category'), True),
        )


class CharacterTempPicture(Model):
    user = ForeignKeyField(null=True, model=User, backref='temp_pictures', on_delete='SET NULL')
    character = ForeignKeyField(model=Character, backref='temp_pictures', on_delete='CASCADE')
    character_picture = CharField(null=True)
    user_striked = BooleanField(default=False)

    @classmethod
    def create_temp_character_picture(cls, user, character):
        with DATABASE.transaction():
            character_temp_picture = cls.create(
                user=user,
                character=character
            )
        return character_temp_picture

    class Meta:
        database = DATABASE
        table_name = "Character_temp_pic"


class CharacterPicture(Model):
    character = ForeignKeyField(model=Character, backref='pictures', on_delete='CASCADE')
    character_picture = CharField(null=True)

    @classmethod
    def create_character_picture(cls, character):
        with DATABASE.transaction():
            character_picture = cls.create(
                character=character,
            )
        return character_picture

    class Meta:
        database = DATABASE
        table_name = "Character_pic"


class Comment(Model):
    character = ForeignKeyField(model=Character, backref='comments', on_delete='CASCADE')
    user = ForeignKeyField(model=User, backref='comments', on_delete='CASCADE')
    created = DateTimeField()
    modified = DateTimeField()
    parent = ForeignKeyField('self', null=True, backref='comments', on_delete='CASCADE')
    content = TextField()

    @classmethod
    def create_comment(cls, character, user, parent, content, created):
        with DATABASE.transaction():
            comment = cls.create(
                character=character,
                user=user,
                created=created,
                modified=created,
                parent=parent,
                content=content
            )
        return comment

    class Meta:
        database = DATABASE
        table_name = "Comment"


class Ping(Model):
    from_comment = ForeignKeyField(model=Comment, backref='pings', on_delete='CASCADE')
    to_user = ForeignKeyField(model=User, backref='pinged', on_delete='CASCADE')

    @classmethod
    def create_ping(cls, comment, user):
        with DATABASE.transaction():
            cls.create(from_comment=comment, to_user=user)

    class Meta:
        database = DATABASE
        table_name = "Ping"
        indexes = (
            (('from_comment', 'to_user'), True),
        )


class CommentRelationship(Model):
    from_user = ForeignKeyField(model=User, backref='liked', on_delete='CASCADE')
    to_comment = ForeignKeyField(model=Comment, backref='likes', on_delete='CASCADE')

    @classmethod
    def create_comment_relationship(cls, from_user, to_comment):
        with DATABASE.transaction():
            cls.create(from_user=from_user, to_comment=to_comment)

    class Meta:
        database = DATABASE
        table_name = "Comment_rel"
        indexes = (
            (('from_user', 'to_comment'), True),
        )


def upload_image(file, path: str):
    file_stream = file.read()
    content_type = file.content_type
    blob = bucket.blob(path)
    blob.cache_control = 'no-cache'
    blob.upload_from_string(data=file_stream, content_type=content_type)
    return blob.public_url


def upload_old_image(old_url: str, new_url: str):
    old_blob = _get_blob_by_url(old_url)
    new_blob = bucket.copy_blob(blob=old_blob, destination_bucket=bucket, new_name=new_url)
    return new_blob.public_url


def delete_image(url: str):
    blob = _get_blob_by_url(url)
    blob.delete()


def _get_blob_by_url(url: str):
    start_at = len('https://storage.googleapis.com/topanimecharacters.com/')
    path_to_image = url[start_at:]
    return bucket.blob(path_to_image)


@login_manager.user_loader
def load_user(user_id):
    return User.get_or_none(User.id == user_id)
