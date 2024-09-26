from threading import Thread

from flask import flash
from playhouse.flask_utils import get_object_or_404
from main import app
from mails import send_ban_mail

from models import User, Universe, delete_image, GlobalRating, CategoryRating, fn, CategoryRelationship, Comment, Ping, CommentRelationship


def _delete_all_associated_character_pictures(live_character):
    # delete the profile picture.
    delete_image(live_character.character_picture)
    # delete all the temporary submitted pictures.
    for picture in live_character.temp_pictures:
        delete_image(picture.character_picture)
    # and then delete all the live pictures.
    for picture in live_character.pictures:
        delete_image(picture.character_picture)


def delete_live_character_completely(live_character):
    thread = Thread(target=_delete_live_character, args=[live_character])
    thread.start()


def delete_live_universe_completely(live_universe):
    thread = Thread(target=_delete_live_universe, args=[live_universe])
    thread.start()


def _delete_live_character(live_character):
    _delete_all_associated_character_pictures(live_character)
    # I'm not calling the "get_or_none()" function, since i know for sure that the universe exist.
    universe = Universe.select().where(Universe.name == live_character.universe.name).get()
    live_character.delete_instance()
    delete_universe_if_no_characters_left(universe)


def _delete_live_universe(live_universe):
    for character in live_universe.characters:
        _delete_all_associated_character_pictures(character)
    live_universe.delete_instance()


def delete_universe_if_no_characters_left(universe: Universe):
    if not universe.characters.exists():
        universe.delete_instance()


def delete_old_ratings_and_create_new_ones(live_character, universe):
    # delete the old ones
    GlobalRating.delete().where(GlobalRating.character == live_character).execute()
    CategoryRating.delete().where(CategoryRating.character == live_character).execute()
    CategoryRelationship.delete().where(CategoryRelationship.character == live_character).execute()
    # create the new ones
    _create_new_ratings(live_character, universe)


def _create_new_ratings(character, universe):
    GlobalRating.create_global_rating(character=character)
    for category in universe.categories:
        CategoryRating.create_category_rating(character=character, category=category)


def strike_or_ban_user(user_id: int):
    user = get_object_or_404(User, (User.id == user_id))
    if not user.is_banned:
        User.update({User.strikes: user.strikes + 1}).where(User.id == user_id).execute()
        # Don't want to retrieve the user object again to check for their strikes. I'm just adding 1 to the amount of strikes to simulate that the user got an increase in strikes.
        if user.strikes + 1 >= app.config['MAX_STRIKES']:  # Reason behind why I'm using ">=" is because if i unban a user and i forget to reset the strikes or lower them then it would never ban if i used "=".
            if user.profile_picture[app.config['LEN_OF_PATH_OF_PROFILE_PIC']:] != 'default':  # delete only if the picture isn't the default picture
                delete_image(g.user.profile_picture)
            send_ban_mail(user.email, user.username)
            User.update({
                User.username: '[banned_user]',
                User.profile_picture: app.config['DEFAULT_PROFILE_PIC'],
                User.is_banned: True
            }).where(User.id == user_id).execute()
            Ping.delete().where(Ping.to_user == user).execute()
            Comment.delete().where(Comment.user == user).execute()
            CommentRelationship.delete().where(CommentRelationship.from_user == user).execute()
            CategoryRelationship.delete().where(CategoryRelationship.user == user).execute()
            flash(message="User have been sucessfully striked, and now BANNED", category="success")
        else:
            flash(message="User have been sucessfully striked", category="success")
    else:
        flash(message="The user has been BANNED already", category="success")
