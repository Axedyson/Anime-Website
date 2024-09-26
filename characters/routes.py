import re
from statistics import mean
from string import ascii_uppercase as alphabet

from flask import Blueprint, g, redirect, url_for, render_template, request, flash, jsonify, abort, make_response
from flask_login import login_required
from playhouse.flask_utils import get_object_or_404

from characters.forms import CharacterForm, CharacterPictureForm, CategoryForm
from characters.utils import _build_comment_tree, _extract_comment_data, render_all_or_specific_characters, generate_score_in_proper_format, live_search_character_suggestions, live_search_universe_suggestions, \
    search_universe_names, search_characters_and_their_ratings, UNIVERSE_ALL_SEARCH_AMOUNT, UNIVERSE_ONLY_SEARCH_AMOUNT, CHARACTER_ALL_SEARCH_AMOUNT, CHARACTER_ONLY_SEARCH_AMOUNT, CATEGORY_NAMES, filter_characters, extract_proper_character_data
from mails import send_ping_user_email
from main import limiter, app
from models import DATABASE, Character, CharacterTemp, upload_image, Comment, CommentRelationship, User, Ping, \
    CharacterTempPicture, DataError, IntegrityError, Universe, CategoryTemp, Category, CategoryRelationship, fn, \
    GlobalRating, CategoryRating
from utils import create_pic_hashid, resize_image, decode_char_hashid, _return_proper_datetime, image_size_reducer

characters = Blueprint('characters', __name__)


@characters.route('/search', methods=('GET',))
def search():
    query = request.args.get('query', type=str)
    if query:
        # Setup variables.
        filter_search = False
        search_category_toggle = request.cookies.get('search_category_toggle', 'all')
        # Check if the length of the query exceeds 100 characters, if it does, then flash an error message.
        if len(query) > 100:
            flash(message="We don't accept searches longer than 100 letters/characters", category="warning")
            return render_template("search_suggestions.html", search_query_input=request.args, errors=True, search_category_toggle=search_category_toggle, 
                filter_search=filter_search)
        else:
            errors = False  # There are no errors if we reached this else scope.
            query = query.strip()  # Strip the query so it takes less processing power when searching for it, I know it's only going to make a small difference.
            more_data = {}
            if search_category_toggle == 'universes':
                characters = None
                universe_names, more_universes = search_universe_names(query, limit=UNIVERSE_ONLY_SEARCH_AMOUNT)
                more_data.update(universes=more_universes)
            elif search_category_toggle == 'characters':
                universe_names = None
                characters, more_characters = search_characters_and_their_ratings(query, limit=CHARACTER_ONLY_SEARCH_AMOUNT)
                more_data.update(characters=more_characters)
            elif search_category_toggle == 'all':
                universe_names, more_universes = search_universe_names(query)
                characters, more_characters = search_characters_and_their_ratings(query)
                more_data.update(characters=more_characters, universes=more_universes)
            else:
                search_category_toggle = 'all'
                universe_names, more_universes = search_universe_names(query)
                characters, more_characters = search_characters_and_their_ratings(query)
                more_data.update(characters=more_characters, universes=more_universes)
    else:
        # Setup variables.
        filter_search = True
        universe_names = None
        search_category_toggle = 'character filter'

        # Dict of the predefined query parameters that are required for the search view (dict that simulates the expected "request.args" dict object).
        # I had to make it here so there will always be created a new dict every request, if i didn't do that, an instance would share same dict and that would cause great confusion for the user.
        search_query_parameters = {'name': '', 'universe': '', 'age': '', 'height': '', 'weight': '', 'species': '', 'gender': '', 'occupation': '', 'status': '', 'official': ''}

        # Creates a set that contains all the keys that are common to both sets therefore checking if the provided query parameters are valid.
        common_set = set(search_query_parameters.keys()) & set(request.args.keys())
        if not common_set:
            # Couldn't find another programming friendly/readable way to display the error for the user, had to make a new template :(
            return render_template("search_suggestions_errors.html", error_message="Missing query parameters!", category="Danger", 
                search_category_toggle=search_category_toggle)
        # Construct a dict with the predefined search query parameters so it looks good on the front-end ya know.
        search_query_parameters.update({k: request.args[k] for k in common_set})
        request.args = search_query_parameters
        errors = [k for k in common_set if len(request.args[k]) > 100]
        if errors:
            # Checking if all query arguments are errors.
            if len(errors) == len(common_set):
                # Couldn't find another programming friendly/readable way to display the error for the user, had to make a new template :(
                return render_template("search_suggestions_errors.html", error_message="All the required input you've provided has a length of over 100 letters/characters " 
                    "which isn't allowed", category="Warning", search_category_toggle=search_category_toggle)
            # Only some query argument errors here.
            else:
                flash(message="We don't accept search input longer than 100 letters/characters", category="warning")
        data = {k: v for k, v in dict(zip([k for k in common_set if k not in errors], [request.args[k].strip() for k in common_set if k not in errors])).items() if v}        
        if not data:
            return render_template("search_suggestions_errors.html", error_message="Whitespace/no data, is not acceptable", category="Warning", search_category_toggle=search_category_toggle)
        
        characters = filter_characters(data).order_by(+Character.id).limit(CHARACTER_ONLY_SEARCH_AMOUNT)  # Reason why I'm ordering by id is that if a character gets a new global_rank then it could mess up the pagination!
        more_data = {'characters': bool(characters.offset(CHARACTER_ONLY_SEARCH_AMOUNT).limit(1).count())}
    return render_template('search_suggestions.html', search_query_input=request.args, characters=characters, universe_name_rows=universe_names,
        filter_search=filter_search, search_category_toggle=search_category_toggle, errors=errors, more_data=more_data)


@characters.route('/character_filter_search', methods=('GET',))
def ajax_character_filter_search():
    # Creates a set that contains all the keys that are common to both sets therefore checking if the provided query parameters are valid.
    common_set = {'name', 'universe', 'age', 'height', 'weight', 'species', 'gender', 'occupation', 'status', 'official'} & set(request.args.keys())
    if not common_set:
        return jsonify(message="Missing query parameters!"), 422
    errors = [k for k in common_set if len(request.args[k]) > 100]
    if errors:
        # Checking if all query arguments are errors.
        if len(errors) == len(common_set):
            return jsonify(message="All the required input you've provided has a length of over 100 letters/characters which isn't allowed"), 422
    data = {k: v for k, v in dict(zip([k for k in common_set if k not in errors], [request.args[k].strip() for k in common_set if k not in errors])).items() if v}        
    if not data:
        return jsonify(message="Whitespace/no data, is not acceptable"), 422
    page = request.args.get('page', default=1, type=int)
    # Make sure that the page is not 0 so users don't abuse this route for retrieving characters instead of using the "search" route
    if page < 1:
        page = 1
    # Set the current character load offset by the given current page.
    offset = page * CHARACTER_ONLY_SEARCH_AMOUNT
    characters = filter_characters(data).order_by(+Character.id).offset(offset).limit(CHARACTER_ONLY_SEARCH_AMOUNT)  # Reason why I'm ordering by id is that if a character gets a new global_rank then it could mess up the pagination!
    more_characters = bool(characters.offset(offset + CHARACTER_ONLY_SEARCH_AMOUNT).limit(1).count())
    return jsonify(characters=extract_proper_character_data(characters), more_data=more_characters)


@characters.route('/character_search', methods=('GET',))
def ajax_character_search():
    query = request.args.get('query', type=str)
    if query:
        if len(query) > 100:
            return jsonify(message="We don't accept searches longer than 100 letters/characters"), 422
    else:
        return jsonify(message="Missing query parameter!"), 422
    # Gotta have the search_category_toggle cookie value sent as a query argument since the user can change the cookie value at anytime.
    limit = CHARACTER_ONLY_SEARCH_AMOUNT if request.args.get('search_category_toggle', type=str) == "characters" else CHARACTER_ALL_SEARCH_AMOUNT
    page = request.args.get('page', default=1, type=int)
    # Make sure that the page is not 0 so users don't abuse this route for retrieving characters instead of using the "search" route
    if page < 1:
        page = 1
    characters, more_characters = search_characters_and_their_ratings(query, offset=page * limit, limit=limit)
    return jsonify(characters=extract_proper_character_data(characters), more_data=more_characters)


@characters.route('/universe_search', methods=('GET',))
def ajax_universe_search():
    query = request.args.get('query', type=str)
    if query:
        if len(query) > 100:
            return jsonify(message="We don't accept searches longer than 100 letters/characters"), 422
    else:
        return jsonify(message="Missing query parameter!"), 422
    # Gotta have the search_category_toggle cookie value sent as a query argument since the user can change the cookie value at anytime.
    limit = UNIVERSE_ONLY_SEARCH_AMOUNT if request.args.get('search_category_toggle', type=str) == "universes" else UNIVERSE_ALL_SEARCH_AMOUNT
    page = request.args.get('page', default=1, type=int)
    # Make sure that the page is not 0 so users don't abuse this route for retrieving characters instead of using the "search" route
    if page < 1:
        page = 1
    universe_names, more_universes = search_universe_names(query, offset=page * limit, limit=limit)
    return jsonify(universes=universe_names, more_data=more_universes)


@characters.route('/live_search', methods=('POST',))
def live_search():
    query = request.form.get('query', type=str, default='').strip()
    if query and not len(query) > 100:        
        query = re.sub(r'[^\w+]', '+', query.strip().replace(' ', '+')) + ':*'
    else:
        return jsonify(suggestions=[])
    search_category_toggle = request.cookies.get('search_category_toggle', 'all')
    if search_category_toggle == 'all':
        suggestions_arr = live_search_character_suggestions(query, limit=5)
        suggestions_arr.extend(live_search_universe_suggestions(query, limit=5))
    elif search_category_toggle == 'universes':
        suggestions_arr = live_search_universe_suggestions(query, limit=10)
    elif search_category_toggle == 'characters':
        suggestions_arr = live_search_character_suggestions(query, limit=10)
    else:
        suggestions_arr = live_search_character_suggestions(query, limit=5)
        suggestions_arr.extend(live_search_universe_suggestions(query, limit=5))
    return jsonify(suggestions=suggestions_arr)


@characters.route('/characters', methods=('GET', 'POST'))
def render_characters():
    real_categories = [(category, category) for category in CATEGORY_NAMES if
                       Category.select().where(Category.name == category).exists()]
    form = CategoryForm()
    form.category.choices.extend(real_categories)
    category_query_arg = request.args.get('category')
    category = category_query_arg if category_query_arg in [category[0] for category in real_categories] else None
    if form.validate_on_submit():
        # I'm redirecting so the user can get the correct url with the category query parameter.
        if len(form.category.data):
            return redirect(url_for('characters.render_characters', category=form.category.data))
        return redirect(url_for('characters.render_characters'))
    return render_all_or_specific_characters(form=form, category_name=category)


@characters.route('/universes/<path:universe_name>', methods=('GET', 'POST'))
def render_universe_characters(universe_name: str):
    universe = get_object_or_404(Universe, (Universe.name == universe_name))
    form = CategoryForm()
    form.category.choices.extend([(category.name, category.name) for category in universe.categories])
    category_query_arg = request.args.get('category')
    category = category_query_arg if Category.select().where((Category.name == category_query_arg) & (
                Category.universe == universe)).exists() else None if category_query_arg else None
    if form.validate_on_submit():
        # I'm redirecting so the user can get the correct url with the category query parameter.
        if len(form.category.data):
            return redirect(url_for('characters.render_universe_characters', universe_name=universe_name,
                                    category=form.category.data))
        return redirect(url_for('characters.render_universe_characters', universe_name=universe_name))
    return render_all_or_specific_characters(form=form, category_name=category, universe=universe)


@characters.route('/universes', methods=('GET',))
def render_universes():
    uni_alp_dict = {}  # default dicts are now ordered in python 3.7 yay, don't have to sort it or use orderedDict!
    uni_not_alp_list = []
    row_index_alp = 0
    col_index_alp = 0
    row_index_not_alp = 0
    col_index_not_alp = 0
    universe_names = [universe[1] for universe in Universe.select().order_by(Universe.name).tuples()]
    for name in universe_names:
        no_match = True
        for letter in list(alphabet):
            if re.match(fr'^{letter}', name.upper()):
                arr = uni_alp_dict.get(letter)
                if arr:
                    # checks to see if there are exactly 20 universe names inside a given column array.
                    if len(arr[row_index_alp][col_index_alp]) == 20:
                        # checks to see if there are exactly 4 columns inside a given row.
                        if col_index_alp == 3:
                            arr.append([[name]])
                            row_index_alp += 1
                            col_index_alp = 0
                        else:
                            arr[row_index_alp].append([name])
                            col_index_alp += 1
                    else:
                        arr[row_index_alp][col_index_alp].append(name)
                else:
                    uni_alp_dict[letter] = [[[]]]
                    row_index_alp = 0
                    col_index_alp = 0
                    uni_alp_dict[letter][row_index_alp][col_index_alp].append(name)
                no_match = False
                break
        if no_match:
            if not len(uni_not_alp_list):
                uni_not_alp_list.append([[]])
            # checks to see if there are exactly 20 universe names inside a given column array.
            if len(uni_not_alp_list[row_index_not_alp][col_index_not_alp]) == 20:
                # checks to see if there are exactly 4 columns inside a given row.
                if col_index_not_alp == 3:
                    uni_not_alp_list.append([[name]])
                    row_index_not_alp += 1
                    col_index_not_alp = 0
                else:
                    uni_not_alp_list[row_index_not_alp].append([name])
                    col_index_not_alp += 1
            else:
                uni_not_alp_list[row_index_not_alp][col_index_not_alp].append(name)
    return render_template('universes.html', universes_alp=uni_alp_dict, universes_not_alp=uni_not_alp_list)


@characters.route('/characters/<hashid>/pictures', methods=('GET',))
def pictures(hashid):
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    single_character = Character.get_or_none(Character.id == character_id)
    if not single_character:
        return jsonify(message="The character you're trying to retrieve pictures from doesn't exist"), 404
    if not single_character.pictures.exists():
        return jsonify([])
    random_seed = request.args.get('seed', type=float)
    if not (random_seed is not None and 1 > random_seed >= 0):
        return jsonify([])
    DATABASE.execute_sql(f'set seed to {random_seed};')
    page = request.args.get('page', default=1, type=int)
    character_pictures = single_character.pictures.select().order_by(fn.Random()).paginate(page=page, paginate_by=10)
    try:
        return jsonify([picture.character_picture for picture in character_pictures])
    except DataError:
        return jsonify([])


@characters.route('/characters/<hashid>', methods=('GET',))
def character(hashid):
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    single_character = get_object_or_404(Character, (Character.id == character_id))
    # setup code for all of the other ajax requests and small features on this view/page
    comment_id = None
    if single_character.comments.exists():
        comment_id = single_character.comments.where(Comment.parent.is_null()).order_by(-Comment.id).get().id
    form = CharacterPictureForm()
    description = single_character.description.split('\n')
    global_rating = GlobalRating.get(GlobalRating.character == single_character)
    return render_template('character.html', character=single_character, form=form, description=description,
                           newest_comment_id=comment_id, global_rating=global_rating)


@characters.route('/characters/add_character', methods=('GET', 'POST'))
@login_required
@limiter.limit('15/minute')
def add_character():
    if not g.user.email_confirmed:
        flash(message="Please confirm your email before attempting to add a new anime character", category="warning")
        return redirect(url_for('users.account'))
    form = CharacterForm()
    if form.validate_on_submit():
        temp_character = CharacterTemp.create_character(
            name=form.name.data,
            universe=form.universe.data,
            age=form.age.data,
            height=form.height.data,
            weight=form.weight.data,
            species=form.species.data,
            gender=form.gender.data,
            occupation=form.occupation.data,
            status=form.status.data,
            description=form.description.data,
            official=form.official.data == 'True',
            user=g.user.id
        )
        for category in {category.lower() for category in form.categories.data}:
            if category:
                CategoryTemp.create_temp_category(temporary_character=temp_character, name=category)
        new_url = app.config['PATH_TEMP_IMAGES'] + "character/" + \
                  create_pic_hashid(temp_character.id, extra_salt=app.config['CHARACTER_TEMP_PIC'])
        resized_img = resize_image(width=330, height=380, image_file=request.files['character_picture'])
        picture_url = upload_image(resized_img, new_url)
        CharacterTemp.update({CharacterTemp.character_picture: picture_url}) \
            .where(CharacterTemp.id == temp_character.id).execute()
        flash(message="Submitted for approval, have patience!", category="success")
        return redirect(url_for('central.home'))
    # Making sure that the ids and names of the category input fields are rendered with the correct ordered numbers!
    for i, field in enumerate(form.categories.entries):
        field.id = f'categories-{i}'
        field.name = f'categories-{i}'
    return render_template('add_character.html', form=form)


@characters.route('/cron/characters/update_ratings')
def cron_job_update_ratings():
    if app.config['CRON_JOB_SECURE'] and not request.headers.get('X-Appengine-Cron'):
        abort(403)
    # Here you can change the amount of people required to rate before actually calculating a score for a character.
    number_of_required_people = 1  # must not be zero as that doesn't make sense.

    # Normally i would've ordered it like this: "-CategoryRating.category_score". But now I'm ordering it like this:
    # "-fn.to_number(CategoryRating.category_score, '999G999')" why? Because if the category score is
    # precisely 100,000 then it would normally rank that as the lowest, pretty weird, right!
    for universe in Universe.select():
        for character_instance in universe.characters.tuples():
            # update the category_scores for every character
            for category in universe.categories.tuples():
                scores = [score[4] for score in CategoryRelationship.select().where((CategoryRelationship.category == category[0]) & (CategoryRelationship.character == character_instance[0])).tuples()]
                if len(scores) >= number_of_required_people:
                    score = generate_score_in_proper_format(mean(scores))
                else:
                    score = None
                    # If the category_score is none then set the global_category_rank and the universe_category_rank to none too.
                    CategoryRating.update({
                        CategoryRating.global_category_rank: score,
                        CategoryRating.universe_category_rank: score
                    }).where((CategoryRating.category == category[0]) & (CategoryRating.character == character_instance[0])).execute()
                CategoryRating.update({
                    CategoryRating.category_score: score
                }).where((CategoryRating.category == category[0]) & (CategoryRating.character == character_instance[0])).execute()

            # update the overall_score for every character
            scores = [score[4] for score in CategoryRelationship.select().where(CategoryRelationship.character == character_instance[0]).tuples()]
            if len(scores) >= number_of_required_people:
                score = generate_score_in_proper_format(mean(scores))
            else:
                score = None
                # If the overall_score is none then set the global_rank and the universe_rank to none too.
                GlobalRating.update({
                    GlobalRating.global_rank: score,
                    GlobalRating.universe_rank: score
                }).where(GlobalRating.character == character_instance[0]).execute()
            GlobalRating.update({
                GlobalRating.overall_score: score
            }).where(GlobalRating.character == character_instance[0]).execute()

        # update the universe_category_ranks for every character
        for category in universe.categories.tuples():
            for i, character_instance in enumerate(universe.characters.join(CategoryRating).where((CategoryRating.category == category[0]) & (CategoryRating.category_score.is_null(False))).order_by(-fn.to_number(CategoryRating.category_score, '999G999')).tuples()):
                CategoryRating.update({
                    CategoryRating.universe_category_rank: i + 1
                }).where((CategoryRating.category == category[0]) & (CategoryRating.character == character_instance[0])).execute()

        # update the universe_rank for every character
        for i, character_instance in enumerate(universe.characters.join(GlobalRating).where(GlobalRating.overall_score.is_null(False)).order_by(-fn.to_number(GlobalRating.overall_score, '999G999')).tuples()):
            GlobalRating.update({
                GlobalRating.universe_rank: i + 1
            }).where(GlobalRating.character == character_instance[0]).execute()

    # update the global_category_ranks for every character
    for category_name in CATEGORY_NAMES:
        categories = [category[0] for category in Category.select().where(Category.name == category_name).tuples()]
        for i, character_instance in enumerate(Character.select().join(CategoryRating).where((Character.official) & (CategoryRating.category_score.is_null(False)) & (CategoryRating.category.in_(categories))).order_by(-fn.to_number(CategoryRating.category_score, '999G999')).tuples()):
            CategoryRating.update({
                CategoryRating.global_category_rank: i + 1
            }).where((CategoryRating.category.in_(categories)) & (CategoryRating.character == character_instance[0])).execute()

    # update the global_rank for every character
    for i, character_instance in enumerate(Character.select().join(GlobalRating).where((Character.official) & (GlobalRating.overall_score.is_null(False))).order_by(-fn.to_number(GlobalRating.overall_score, '999G999')).tuples()):
        GlobalRating.update({
            GlobalRating.global_rank: i + 1
        }).where(GlobalRating.character == character_instance[0]).execute()

    response = make_response('It was a success!')
    response.mimetype = 'text/plain'
    return response


@characters.route('/characters/<hashid>/rate', methods=('POST',))
@limiter.limit('15/minute')
def rate(hashid):
    if not g.user.is_authenticated:
        return jsonify(message="You are not logged in, please log in before you can vote"), 403
    if not g.user.email_confirmed:
        return jsonify(message='Your email is not confirmed, please confirm it'), 401
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    single_character = Character.get_or_none(Character.id == character_id)
    if not single_character:
        return jsonify(message="The character you're trying to rate doesn't exist"), 404
    data = request.get_json()
    score = data['score']
    if not isinstance(score, int):
        return jsonify(message="The score must be a whole number between 0 inclusive and 100 inclusive"), 422
    if not 0 <= score <= 100:
        return jsonify(message="The score must be a whole number between 0 inclusive and 100 inclusive"), 422
    category_name = data['category']
    if not category_name:
        return jsonify(message="Please choose a category to vote by"), 422
    if not isinstance(category_name, str):
        return jsonify(message="The category must be a type of string"), 422
    category = Category.get_or_none((Category.name == category_name) & (Category.universe == single_character.universe))
    if not category:
        return jsonify(message="The specified category doesn't exist"), 422
    if CategoryRelationship.select().where(
            (CategoryRelationship.category == category) & (CategoryRelationship.character == single_character) & (
                    CategoryRelationship.user == g.user.id)).exists():
        CategoryRelationship.update({
            CategoryRelationship.score: score
        }).where((CategoryRelationship.category == category) & (CategoryRelationship.character == single_character) & (
                CategoryRelationship.user == g.user.id)).execute()
    else:
        CategoryRelationship.create_category_relationship(
            category=category,
            character=single_character,
            user=g.user.id,
            score=score
        )
    return jsonify(data)


@characters.route('/characters/<hashid>/rate/delete', methods=('DELETE',))
@limiter.limit('15/minute')
def delete_rate(hashid):
    if not g.user.is_authenticated:
        return jsonify(message="You are not logged in, please log in before you can delete a score"), 403
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    single_character = Character.get_or_none(Character.id == character_id)
    if not single_character:
        return jsonify(message="The character you're trying to delete a score from doesn't exist"), 404
    category_query_arg = request.args.get('category')
    if not category_query_arg:
        return jsonify(message="You must provide a category to delete your score from"), 422
    category = Category.get_or_none(
        (Category.name == category_query_arg) & (Category.universe == single_character.universe))
    if not category:
        return jsonify(message="No category found in this universe by that name you provided"), 422
    score = CategoryRelationship.get_or_none(
        (CategoryRelationship.category == category) & (CategoryRelationship.character == single_character) & (
                CategoryRelationship.user == g.user.id))
    if not score:
        return jsonify(status='success', message="The score didn't exist in the first place in fact")
    else:
        score.delete_instance()
        return jsonify(status='success')


@characters.route('/characters/<hashid>/rating', methods=('GET',))
def rating(hashid):
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    single_character = Character.get_or_none(Character.id == character_id)
    if not single_character:
        return jsonify(message="The character you're trying to retrieve your ratings from doesn't exist"), 404
    category_query_arg = request.args.get('category')
    if not category_query_arg:
        return jsonify(message="You must provide a category to get your ratings from"), 422
    category = Category.get_or_none(
        (Category.name == category_query_arg) & (Category.universe == single_character.universe))
    if not category:
        return jsonify(message="No category found in this universe by that name you provided"), 422
    score = None
    if g.user.is_authenticated:
        score = CategoryRelationship.get_or_none(
            (CategoryRelationship.category == category) & (CategoryRelationship.character == single_character) & (
                    CategoryRelationship.user == g.user.id))
    global_rating = GlobalRating.get(GlobalRating.character == single_character)
    category_rating = CategoryRating.get(
        (CategoryRating.character == single_character) & (CategoryRating.category == category))
    return jsonify({'user_score': score.score if score else None,
                    'global_rank': global_rating.global_rank,
                    'global_category_rank': category_rating.global_category_rank,
                    'universe_rank': global_rating.universe_rank,
                    'universe_category_rank': category_rating.universe_category_rank,
                    'overall_score': global_rating.overall_score,
                    'category_score': category_rating.category_score})


@characters.route('/characters/<hashid>/add_picture', methods=('POST',))
@limiter.limit('15/minute')
def add_picture(hashid):
    if not g.user.is_authenticated:
        return jsonify(picture_errors=['You are not logged in, please log in before attempting to add a picture']), 403
    if not g.user.email_confirmed:
        return jsonify(picture_errors=['Your email is not confirmed, please confirm it']), 401
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    single_character = Character.get_or_none(Character.id == character_id)
    if not single_character:
        return jsonify(picture_errors=["The character you're trying to add a picture to doesn't exist anymore"]), 404
    form = CharacterPictureForm()
    if form.validate_on_submit():
        character_temp_picture = CharacterTempPicture. \
            create_temp_character_picture(user=g.user.id, character=single_character)
        new_url = app.config['PATH_TEMP_IMAGES'] + "character_pictures/" + \
                  create_pic_hashid(character_temp_picture.id, extra_salt=app.config['CHARACTER_TEMP_PICS'])
        reduced_img = image_size_reducer(image_file=request.files['character_picture'])
        picture_url = upload_image(reduced_img, new_url)
        CharacterTempPicture.update({CharacterTempPicture.character_picture: picture_url}).where(
            CharacterTempPicture.id == character_temp_picture.id).execute()
        return jsonify(status="success")
    return jsonify(picture_errors=form.character_picture.errors), 422


@characters.route('/characters/<hashid>/comments', methods=('GET',))
def comments(hashid):
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    single_character = Character.get_or_none(Character.id == character_id)
    if not single_character:
        return jsonify(message="The character you're trying to retrieve comments from doesn't exist"), 404
    if not single_character.comments.exists():
        return jsonify([[], {'more_comments': False}, {'last_comment_id': None, 'next_comment_id': None}])
    newest_comment_id = request.args.get('newest_comment_id', type=int)
    if not newest_comment_id:
        return jsonify([[], {'more_comments': False}, {'last_comment_id': None, 'next_comment_id': None}])
    per_page = request.cookies.get('per_load', default=15, type=int)
    if per_page > 50:
        per_page = 50
    elif per_page < 1:
        per_page = 1
    next_comment_id = request.args.get('next_comment_id', default=newest_comment_id, type=int)
    comment_ids = single_character.comments.where(Comment.parent.is_null()).order_by(-Comment.id).where(
        Comment.id <= next_comment_id).select(Comment.id).limit(per_page)
    if not comment_ids.exists():
        return jsonify([[], {'more_comments': False}, {'last_comment_id': None, 'next_comment_id': None}])
    comment_tree = _build_comment_tree(comment_ids, single_character.comments)
    comments_array = [_extract_comment_data(comment) for comment in comment_tree]
    last_comment_id = list(comment_ids).pop().id
    next_comment_id = list(comment_ids.limit(per_page + 1)).pop().id
    more_comments = last_comment_id != next_comment_id
    return jsonify([comments_array, {'more_comments': more_comments},
                    {'last_comment_id': last_comment_id, 'next_comment_id': next_comment_id}])


@characters.route('/characters/<hashid>/comment_users', methods=('GET',))
def comment_users(hashid):
    if not g.user.is_authenticated:
        return jsonify(message="You are not logged in, please log in"), 403
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    single_character = Character.get_or_none(Character.id == character_id)
    if not single_character:
        return jsonify(message="The character you're trying to retrieve users from doesn't exist"), 404
    if not single_character.comments.where(Comment.user != g.user.id).exists():
        return jsonify([])
    last_comment_id = request.args.get('last_comment_id', type=int)
    newest_comment_id = request.args.get('newest_comment_id', type=int)
    if not (last_comment_id and newest_comment_id):
        return jsonify(
            message="You're fast, trying to ping users when no comments have been loaded yet, wait a bit please"), 422
    comment_ids = single_character.comments.where(Comment.parent.is_null()).order_by(-Comment.id).where(
        Comment.id.between(last_comment_id, newest_comment_id)).select(Comment.id)
    if not comment_ids.exists():
        return jsonify([])
    comment_tree = _build_comment_tree(comment_ids, single_character.comments)
    users_array, unique_user_ids, unique_comments = [], [], []
    for comment in comment_tree:
        if comment.user.id not in unique_user_ids:
            unique_user_ids.append(comment.user.id)
            unique_comments.append(comment)
    for comment in unique_comments:
        users_array.append({
            'id': comment.user.id,
            'fullname': 'Current User' if g.user.id == comment.user.id else comment.user.username,
            'profile_picture_url': comment.user.profile_picture
        })
    return jsonify(users_array)


@characters.route('/characters/<hashid>/add_comment', methods=('POST',))
@limiter.limit('30/minute')
def add_comment(hashid):
    if not g.user.is_authenticated:
        return jsonify(message="You are not logged in, please log in"), 403
    if not g.user.email_confirmed:
        return jsonify(message='Your email is not confirmed, please confirm it'), 401
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    single_character = Character.get_or_none(Character.id == character_id)
    if not single_character:
        return jsonify(message="The character you're trying to add a comment to doesn't exist anymore"), 404
    data = request.get_json()
    content = data['content'].strip()
    if len(content) > 10000:
        return jsonify(message="Can't have a comment longer than 10.000 letters/characters."), 422
    if content.count('\n') > 50:
        return jsonify(message="Can't have a comment with more than 50 newlines."), 422
    users_to_be_pinged = set()
    for user_id in list(data['pings'].keys()):
        user = User.get_or_none(User.id == user_id)
        if user:
            users_to_be_pinged.add(user)
    if data['parent'] and not Comment.select().where(Comment.id == data['parent']).exists():
        return jsonify(message="The comment you're replying to doesn't exist anymore"), 404
    comment = Comment.create_comment(
        character=single_character,
        user=g.user.id,
        parent=data['parent'],
        content=content,
        created=_return_proper_datetime(data["created"])
    )
    comment_content = comment.content
    for user in users_to_be_pinged:
        Ping.create_ping(comment=comment, user=user)
        comment_content = re.sub(fr'@{user.id}(?!\S)', f'@{user.username}', comment_content)
    for user in users_to_be_pinged:
        if user.email_confirmed and user.receive_email_pings and not user.is_banned:
            send_ping_user_email(user.email, user.username, comment, comment_content)
    return jsonify(_extract_comment_data(comment))


@characters.route('/comments/<int:comment_id>/update', methods=('PUT',))
@limiter.limit('30/minute')
def update_comment(comment_id):
    if not g.user.is_authenticated:
        return jsonify(message="You are not logged in, please log in"), 403
    if not g.user.email_confirmed:
        return jsonify(message='Your email is not confirmed, please confirm it'), 401
    comment = Comment.select().where(Comment.id == comment_id)
    if not comment.exists():
        return jsonify(message="The comment you're trying to update doesn't exist anymore"), 404
    if g.user.is_admin or comment.get().user.id == g.user.id:
        data = request.get_json()
        content = data['content'].strip()
        if len(content) > 10000:
            return jsonify(message="Can't have a comment longer than 10.000 letters/characters."), 422
        if content.count('\n') > 50:
            return jsonify(message="Can't have a comment with more than 50 newlines."), 422
        users_to_be_pinged = set()
        for user_id in list(data['pings'].keys()):
            user = User.get_or_none(User.id == user_id)
            if user:
                users_to_be_pinged.add(user)
        Comment.update({
            Comment.content: content,
            Comment.modified: _return_proper_datetime(data["modified"])
        }).where(Comment.id == comment_id).execute()
    else:
        return jsonify(message='You do not own the comment, therefore you cannot update the comment'), 401
    users = [user.id for user in users_to_be_pinged]
    comment = comment.get()
    for ping in comment.pings:
        if ping.to_user.id not in users:
            ping.delete_instance()
    comment_content = comment.content
    for user in users_to_be_pinged:
        comment_content = re.sub(fr'@{user.id}(?!\S)', f'@{user.username}', comment_content)
    for user in users_to_be_pinged:
        if not comment.pings.where(Ping.to_user == user).exists():
            Ping.create_ping(comment=comment, user=user)
            if user.email_confirmed and user.receive_email_pings and not user.is_banned:
                send_ping_user_email(user.email, user.username, comment, comment_content)
    return jsonify(_extract_comment_data(comment))


@characters.route('/comments/<int:comment_id>/upvote', methods=('POST',))
@limiter.limit('30/minute')
def upvote_comment(comment_id):
    if not g.user.is_authenticated:
        return jsonify(message="You are not logged in, please log in"), 403
    if not g.user.email_confirmed:
        return jsonify(message='Your email is not confirmed, please confirm it'), 401
    if not Comment.select().where(Comment.id == comment_id).exists():
        return jsonify(message="The comment you're trying to like doesn't exist anymore"), 404
    try:
        CommentRelationship.create_comment_relationship(from_user=g.user.id, to_comment=comment_id)
    except IntegrityError:
        return jsonify(
            message="Please don't spam the like button, please wait a bit before using the button again"), 409
    return jsonify(status="success")


@characters.route('/comments/<int:comment_id>/downvote', methods=('DELETE',))
@limiter.limit('30/minute')
def downvote_comment(comment_id):
    if not g.user.is_authenticated:
        return jsonify(message="You are not logged in, please log in"), 403
    if not g.user.email_confirmed:
        return jsonify(message='Your email is not confirmed, please confirm it'), 401
    if not Comment.select().where(Comment.id == comment_id).exists():
        return jsonify(message="The comment you're trying to unlike doesn't exist anymore"), 404
    like = CommentRelationship.get_or_none(CommentRelationship.from_user == g.user.id,
                                           CommentRelationship.to_comment == comment_id)
    if not like:
        return jsonify(message="Please don't spam the like button, please wait a bit before using the button again"), \
               409
    like.delete_instance()
    return jsonify(status="success")


@characters.route('/comments/<int:comment_id>/delete', methods=('DELETE',))
@limiter.limit('30/minute')
def delete_comment(comment_id):
    if not g.user.is_authenticated:
        return jsonify(message="You are not logged in, please log in"), 403
    if not g.user.email_confirmed:
        return jsonify(message='Your email is not confirmed, please confirm it'), 401
    comment = Comment.get_or_none(Comment.id == comment_id)
    if not comment:
        return jsonify(stauts="success", message="The comment didn't exist in the first place in fact")
    if g.user.is_admin or comment.user.id == g.user.id:
        comment.delete_instance()
        return jsonify(status="success")
    else:
        return jsonify(message='You do not own the comment, therefore you cannot delete the comment'), 401
