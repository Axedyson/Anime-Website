import re
from decimal import Decimal, ROUND_HALF_UP

from flask import g, request, render_template, abort, url_for
from flask_paginate import Pagination
from playhouse.shortcuts import model_to_dict

from main import app
from models import Comment, CommentRelationship, Character, DataError, CategoryRating, GlobalRating, Category, Universe
from utils import create_char_hashid

# When removing some global category remember to delete ALL the global_category_rank data in the database associated
# with that specific global category name!!!
CATEGORY_NAMES = ['Strength', 'Intelligence', 'Will Power', 'Speed', 'Teamwork']

# Amount of universes to load if the cookie has been set to universes only search.
UNIVERSE_ONLY_SEARCH_AMOUNT = 320

# Amount of universes to load if the cookie has been set to all search.
UNIVERSE_ALL_SEARCH_AMOUNT = 160

# Amount of characters to load if the cookie has been set to characters only search or the search is character filter search.
CHARACTER_ONLY_SEARCH_AMOUNT = 20

# Amount of characters to load if the cookie has been set to all search.
CHARACTER_ALL_SEARCH_AMOUNT = 10


def render_all_or_specific_characters(form, category_name, universe=None):
    page = request.args.get('page', default=1, type=int)
    per_page = request.cookies.get('per_page', 20, type=int)
    if per_page > 50:
        per_page = 50
    elif per_page < 1:
        per_page = 1
    # Making "category_ratings" and "global_ratings" into tuples is faster in terms of computing power!
    if universe:
        if category_name:
            category = Category.get((Category.universe == universe) & (Category.name == category_name))
            characters_to_paginate = Character.select().join(CategoryRating).where(CategoryRating.category == category).order_by(+CategoryRating.universe_category_rank)
            category_ratings = CategoryRating.select().where(CategoryRating.category == category).order_by(+CategoryRating.universe_category_rank)
            ranks_and_scores = [(rating[4], rating[5]) for rating in category_ratings.paginate(page=page, paginate_by=per_page).tuples()]
        else:
            characters_to_paginate = Character.select().where(Character.universe == universe).join(GlobalRating).order_by(+GlobalRating.universe_rank)
            global_ratings = GlobalRating.select().where(GlobalRating.character.in_(characters_to_paginate)).order_by(+GlobalRating.universe_rank)
            ranks_and_scores = [(rating[3], rating[4]) for rating in global_ratings.paginate(page=page, paginate_by=per_page).tuples()]
    else:
        if category_name:
            categories = [category for category in Category.select().where(Category.name == category_name)]
            characters_to_paginate = Character.select().join(CategoryRating).where((Character.official) & (CategoryRating.category.in_(categories))).order_by(+CategoryRating.global_category_rank)
            category_ratings = CategoryRating.select().join(Character).where((CategoryRating.category.in_(categories)) & (Character.official)).order_by(+CategoryRating.global_category_rank)
            ranks_and_scores = [(rating[3], rating[5]) for rating in category_ratings.paginate(page=page, paginate_by=per_page).tuples()]
        else:
            characters_to_paginate = Character.select().where(Character.official).join(GlobalRating).order_by(+GlobalRating.global_rank)
            global_ratings = GlobalRating.select().where(GlobalRating.character.in_(characters_to_paginate)).order_by(+GlobalRating.global_rank)
            ranks_and_scores = [(rating[2], rating[4]) for rating in global_ratings.paginate(page=page, paginate_by=per_page).tuples()]
    total = characters_to_paginate.count()
    pagination_characters = characters_to_paginate.paginate(page=page, paginate_by=per_page)
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap4', bs_version=4,
                            record_name='characters', format_number=True, format_total=True, alignment='center',
                            display_msg="Displaying <b>{start} - {end}</b> {record_name} in a total of <b>{total}</b>")

    try:
        return render_template('characters.html', characters=pagination_characters, pagination=pagination, form=form,
                               category=category_name if category_name else '', universe=universe.name if universe else None, ratings=ranks_and_scores)
    except DataError:
        abort(404)


def search_characters_and_their_ratings(query: str, offset=0, limit=CHARACTER_ALL_SEARCH_AMOUNT):
    characters = Character.select().where(Character.name.contains(query)).order_by(+Character.id).offset(offset).limit(limit)  # Reason why I'm ordering by id is that if a character gets a new global_rank then it could mess up the pagination!
    # Return the characters, and then a boolean value indicating if there are more characters to retrieve.
    return characters, bool(Character.select().where(Character.name.contains(query)).offset(offset + limit).limit(1).count())


def search_universe_names(query: str, offset=0, limit=UNIVERSE_ALL_SEARCH_AMOUNT):
    row_index = 0
    col_index = 0
    universes = Universe.select().where(Universe.name.contains(query)).offset(offset).limit(limit)
    universe_rows = [[[]]] if universes.exists() else None
    for universe_name in [universe[1] for universe in universes.tuples()]:
        # Checks to see if there are 20 universe names inside a given column
        if len(universe_rows[row_index][col_index]) == 20:
            # Checks to see if there are 4 columns inside a row
            if col_index == 3:
                universe_rows.append([[universe_name]])
                row_index += 1
                col_index = 0
            else:
                universe_rows[row_index].append([universe_name])
                col_index += 1
        else:
            universe_rows[row_index][col_index].append(universe_name)
    # Return the universe rows and also a boolean value indicating if there are more universes to retrieve.
    return universe_rows, bool(Universe.select().where(Universe.name.contains(query)).offset(offset + limit).limit(1).count())


def live_search_character_suggestions(query, limit):
    return [{"value": character_instance[2], "data": {"category": 'Characters', 'source': character_instance[5], 'link': url_for('characters.character', hashid=create_char_hashid(character_instance[0], app.config['CHARACTER'])), 'official': character_instance[14], 'ratings': model_to_dict(GlobalRating.get(GlobalRating.character == character_instance[0]), exclude=[GlobalRating.id, GlobalRating.character, GlobalRating.universe_rank])}} for character_instance in Character.select().where(Character.search_name.match(query)).limit(limit).tuples()]


def live_search_universe_suggestions(query, limit):
    return [{'value': universe[1], 'data': {'category': 'Universes', 'link': url_for('characters.render_universe_characters', universe_name=universe[1])}} for universe in Universe.select().where(Universe.search_name.match(query)).limit(limit).tuples()]


def filter_characters(data: dict):
    characters = Character.select()
    for k, v in data.items():
        if k == 'name':
            characters = characters.where(Character.name.contains(v))
        elif k == 'universe':
            characters = characters.join(Universe).where(Universe.name.contains(v))
        elif k == 'age':
            characters = characters.where(Character.age == v)
        elif k == 'height':
            characters = characters.where(Character.height == v)
        elif k == 'weight':
            characters = characters.where(Character.weight == v)
        elif k == 'species':
            characters = characters.where(Character.species.contains(v))
        elif k == 'gender':
            characters = characters.where(Character.gender == v)
        elif k == 'occupation':
            characters = characters.where(Character.occupation.contains(v))
        elif k == 'status':
            characters = characters.where(Character.status == v)
        elif k == 'official':
            characters = characters.where(Character.official == (v == 'Yes'))
    return characters


def extract_proper_character_data(characters):
    return [{'url': url_for('characters.character', hashid=create_char_hashid(character.id, extra_salt=app.config['CHARACTER'])), 'name': character.name, 
    'picture': character.character_picture, 'official': character.official, 'occupation': character.occupation, 'global_rank': character.global_rating.get().global_rank, 
    'overall_score': character.global_rating.get().overall_score} for character in characters]


def _extract_comment_data(comment: Comment):
    return {
        'id': comment.id,
        'created_by_current_user': g.user.is_authenticated and g.user.id == comment.user.id,
        'created_by_admin': comment.user.is_admin,
        'pings': {ping.to_user.id: ping.to_user.username for ping in comment.pings},
        'content': comment.content,
        'parent': comment.parent.id if comment.parent else None,
        'modified': comment.modified.isoformat(),
        'created': comment.created.isoformat(),
        'fullname': comment.user.username,
        'user_has_upvoted': g.user.is_authenticated and comment.likes.where(
            CommentRelationship.from_user == g.user.id).select().exists(),
        'creator': comment.user.id,
        'profile_picture_url': comment.user.profile_picture,
        'upvote_count': comment.likes.count()
    }


def _build_comment_tree(head_comment_ids, all_comments):
    comments = Comment.select().where(Comment.id << head_comment_ids)
    for comment in all_comments.where(Comment.parent << head_comment_ids):
        if all_comments.where(Comment.parent << [comment.id]).exists():
            comments += _build_comment_tree([comment.id], all_comments)
        else:
            comments += Comment.select().where(Comment.id == comment.id)
    return comments


def generate_score_in_proper_format(score: float):
    score = Decimal(score)
    string_value = str(score.quantize(Decimal('0.001'), ROUND_HALF_UP))
    string_value = string_value.replace('.', ',')
    string_value = re.sub(r'^0+,', '', string_value)
    string_value = string_value.lstrip('0')
    return string_value if string_value else '0'
