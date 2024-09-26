from flask import Blueprint, g, abort, request, render_template, flash, redirect, url_for
from flask_paginate import Pagination
from playhouse.flask_utils import get_object_or_404

from admin.forms import AdminCharacterForm, AdminMailForm, AdminUniverseForm
from admin.utils import delete_live_character_completely, delete_live_universe_completely, strike_or_ban_user, \
    delete_universe_if_no_characters_left, delete_old_ratings_and_create_new_ones, _create_new_ratings
from mails import send_mails_globally
from main import limiter, app
from models import CharacterTemp, Character, delete_image, upload_image, upload_old_image, CharacterTempPicture, \
    CharacterPicture, DataError, Universe, fn, Category, IntegrityError, CategoryRating, GlobalRating
from utils import decode_char_hashid, create_char_hashid, create_pic_hashid, resize_image, decode_pic_hashid

admin = Blueprint('admin', __name__, url_prefix='/admin')


@admin.before_request
def before_request():
    if not (g.user.is_authenticated and g.user.email_confirmed and g.user.is_admin):
        abort(403)


@admin.route('pictures/<hashid>/users/<int:user_id>/strike_user_by_picture', methods=('GET', 'POST'))
def strike_user_by_picture(hashid, user_id: int):
    picture_id = decode_pic_hashid(hashid, extra_salt=app.config['CHARACTER_TEMP_PICS'])
    character_temp_picture = get_object_or_404(CharacterTempPicture, (CharacterTempPicture.id == picture_id))
    if character_temp_picture.user_striked:
        flash(message="User already striked at the specified picture", category="warning")
        return redirect(url_for('admin.approve_pictures'))
    strike_or_ban_user(user_id)
    CharacterTempPicture.update({CharacterTempPicture.user_striked: True}).where(CharacterTempPicture.id == picture_id).execute()
    return redirect(url_for('admin.approve_pictures'))


@admin.route('characters/<hashid>/users/<int:user_id>/strike_user_by_live_character', methods=('GET', 'POST'))
def strike_user_by_live_character(hashid, user_id: int):
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    live_character = get_object_or_404(Character, (Character.id == character_id))
    if live_character.user_striked:
        flash(message="User already striked at the specified live character", category="warning")
        return redirect(url_for('admin.edit_character', hashid=create_char_hashid(character_id, extra_salt=app.config['CHARACTER'])))
    strike_or_ban_user(user_id)
    Character.update({Character.user_striked: True}).where(Character.id == character_id).execute()
    return redirect(url_for('admin.edit_character', hashid=create_char_hashid(character_id, extra_salt=app.config['CHARACTER'])))


@admin.route('temp_characters/<hashid>/users/<int:user_id>/strike_user_by_temp_character', methods=('GET', 'POST'))
def strike_user_by_temp_character(hashid, user_id: int):
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER_TEMP'])
    temp_character = get_object_or_404(CharacterTemp, (CharacterTemp.id == character_id))
    if temp_character.user_striked:
        flash(message="User already striked at the specified temporary character", category="warning")
        return redirect(url_for('admin.approve_character', hashid=create_char_hashid(character_id, extra_salt=app.config['CHARACTER_TEMP'])))
    strike_or_ban_user(user_id)
    CharacterTemp.update({CharacterTemp.user_striked: True}).where(CharacterTemp.id == character_id).execute()
    return redirect(url_for('admin.approve_character', hashid=create_char_hashid(character_id, extra_salt=app.config['CHARACTER_TEMP'])))


@admin.route('/mail', methods=('GET', 'POST'))
@limiter.limit('15/minute')
def mail():
    form = AdminMailForm()
    if form.validate_on_submit():
        images = request.files.getlist('image_attachments') if form.image_attachments.data[0].filename else None
        send_mails_globally(form.reason.data, form.message.data, images)
        flash(message="Mail sent! let's hope they understand it am i right :)", category="success")
        return redirect(url_for('central.home'))
    return render_template('admin/mail.html', form=form)


@admin.route('/characters', methods=('GET',))
def approve_characters():
    page = request.args.get('page', default=1, type=int)
    per_page = request.cookies.get('approve_characters_per_page', 20, type=int)
    if per_page > 50:
        per_page = 50
    elif per_page < 1:
        per_page = 1
    total = CharacterTemp.select().count()
    pagination_characters = CharacterTemp.select().order_by(+CharacterTemp.id).paginate(page=page,
                                                                                        paginate_by=per_page)
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap4', bs_version=4,
                            record_name='submitted characters', format_number=True, format_total=True,
                            alignment='center',
                            display_msg="Displaying <b>{start} - {end}</b> {record_name} in a total of <b>{total}</b>")
    try:
        return render_template('admin/approve_characters.html', characters=pagination_characters, pagination=pagination)
    except DataError:
        abort(404)


@admin.route('/universes/<path:universe_name>/edit', methods=('GET', 'POST'))
def edit_universe(universe_name: str):
    universe = get_object_or_404(Universe, (Universe.name == universe_name))
    form = AdminUniverseForm()
    if request.method == 'GET':
        form.universe.process_data(universe_name)
        for category in universe.categories:
            form.categories.append_entry({'category': category.name, 'category_id': category.id})
    if request.method == 'POST':
        # Reorder the ids in the name and id attributes from 1 to x of the html input fields to avoid bugs.
        # I'm not doing this inside the form validation because this will not run if the form validation fails.
        for i, category_form in enumerate(form.categories):
            category_form['category_id'].id = f'categories-{i}-category_id'
            category_form['category_id'].name = f'categories-{i}-category_id'
            category_form['category'].id = f'categories-{i}-category'
            category_form['category'].name = f'categories-{i}-category'
    if form.validate_on_submit():
        if not any([category_form['category'] for category_form in form.categories.data]):
            return render_template('admin/edit_universe.html', universe=universe_name, form=form,
                                   extra_errors="Please provide at least one category for this universe. ")
        no_duplicates_var = [category_form['category'].lower() for category_form in form.categories.data if
                             category_form['category']]
        # Checking for no duplicates, if there are any duplicates, then render the page again with errors.
        if len(no_duplicates_var) > len({*no_duplicates_var}):
            return render_template('admin/edit_universe.html', universe=universe_name, form=form,
                                   extra_errors="Please don't provide any duplicate categories. ")
        # Update the database by deleting deleted categories.
        try:
            Category.delete().where((Category.id.not_in(
                [int(category_form['category_id']) for category_form in form.categories.data if
                 category_form['category_id']])) & (Category.universe == universe)).execute()
        # Users can change the value of the html hidden input field to something that is not "int()" passable.
        # I only need to check it here since this is the first time I'm checking for it and I'm going to check for EVERY
        # single category_id
        except ValueError:
            return render_template('admin/edit_universe.html', universe=universe_name, form=form,
                                   extra_errors="Please don't change the value of the hidden html input fields id(s)! ")
        # Update the database by updating the previous (old) categories with the new inputted names.
        for category_form in form.categories.data:
            try:
                if category_form['category_id']:
                    Category.update({Category.name: category_form['category'].title()}) \
                        .where(Category.id == category_form['category_id']).execute()
            # If the admin user swapped unique category names, then render the page again with an error.
            # (I have tried. It's too hard to do such an operation, I'm just going to leave it as it is right now).
            except IntegrityError:
                return render_template('admin/edit_universe.html', universe=universe_name, form=form,
                                       extra_errors="Please don't swap the unique category names. ")
        form_data_set = {category_form['category'].lower() for category_form in form.categories.data}
        model_data_set = {category.name.lower() for category in universe.categories}
        # Update the database by creating the newly made categories.
        for category in form_data_set - model_data_set:
            # Checking if the category form data is not an emtpy string (emtpy user input).
            if category:
                # Create the new categories
                category = Category.create_category(universe=universe, name=category.title())
                # Then create a new categoryRating row with that specific "category" for every character.
                for character in universe.characters:
                    CategoryRating.create_category_rating(character=character, category=category)
        if form.universe.data.lower() != universe_name.lower():
            if Universe.select().where(fn.lower(Universe.name) == form.universe.data.lower()).exists():
                form.universe.errors.append(f"The universe {form.universe.data} already exists. ")
                return render_template('admin/edit_universe.html', universe=universe_name, form=form)
            Universe.update(
                {Universe.name: form.universe.data, Universe.search_name: fn.to_tsvector(form.universe.data)}).where(
                Universe.name == universe_name).execute()
        flash(message="Universe updated. Let's hope they get happy, am i right? :)", category="success")
        return redirect(url_for('characters.render_universe_characters', universe_name=form.universe.data))
    return render_template('admin/edit_universe.html', universe=universe_name, form=form)


@admin.route('/universes/<path:universe_name>/delete', methods=('GET', 'DELETE'))
def delete_universe(universe_name: str):
    single_universe = get_object_or_404(Universe, (Universe.name == universe_name))
    delete_live_universe_completely(single_universe)
    return redirect(url_for('characters.render_universes'))


@admin.route('/characters/<hashid>/approve', methods=('GET', 'POST'))
@limiter.limit('15/minute')
def approve_character(hashid):
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER_TEMP'])
    first_character = get_object_or_404(CharacterTemp, (CharacterTemp.id == character_id))
    form = AdminCharacterForm()
    if request.method == 'GET':
        form.name.process_data(first_character.name)
        form.universe.process_data(first_character.universe)
        for category in first_character.categories:
            form.categories.append_entry(category.name)
        form.age.process_data(first_character.age)
        form.height.process_data(first_character.height)
        form.weight.process_data(first_character.weight)
        form.species.process_data(first_character.species)
        form.gender.process_data(first_character.gender)
        form.occupation.process_data(first_character.occupation)
        form.status.process_data(first_character.status)
        form.description.process_data(first_character.description)
        form.official.process_data(first_character.official)
    if form.validate_on_submit():
        universe = Universe.get_or_none(fn.lower(Universe.name) == form.universe.data.lower())
        if form.universe_action.data == 'True':
            if not universe:
                form.universe.errors.append(f"The universe {form.universe.data} doesn't exist. ")
                form.universe_action.errors.append(f"The universe {form.universe.data} doesn't exist. ")
                return render_template('admin/approve_character.html', form=form, character=first_character)
        else:
            if not universe:
                if not any(form.categories.data):
                    return render_template('admin/approve_character.html', form=form, character=first_character,
                                           extra_errors="Please provide at least one category for the new universe. ")
                universe = Universe.create_universe(name=form.universe.data)
                for category in {category.lower() for category in form.categories.data}:
                    if category:
                        Category.create_category(universe=universe, name=category.title())
            else:
                form.universe.errors.append(f"The universe {form.universe.data} already exists. ")
                form.universe_action.errors.append(f"The universe {form.universe.data} already exists. ")
                return render_template('admin/approve_character.html', form=form, character=first_character)
        new_character = Character.create_character(
            name=form.name.data,
            universe=universe,
            age=form.age.data,
            height=form.height.data,
            weight=form.weight.data,
            species=form.species.data,
            gender=form.gender.data,
            occupation=form.occupation.data,
            status=form.status.data,
            description=form.description.data,
            official=form.official.data == 'True',
            user=first_character.user
        )
        new_url = app.config['PATH_READY_IMAGES'] + "character/" + create_pic_hashid(new_character.id, extra_salt=app.config['CHARACTER_LIVE_PIC'])
        if form.character_picture.data:
            resized_img = resize_image(width=330, height=380, image_file=request.files['character_picture'])
            picture_url = upload_image(resized_img, new_url)
        else:
            picture_url = upload_old_image(first_character.character_picture, new_url)
        Character.update({Character.character_picture: picture_url}) \
            .where(Character.id == new_character.id).execute()
        _create_new_ratings(new_character, universe)
        delete_image(first_character.character_picture)
        first_character.delete_instance()
        flash(message="Released to the public, this is exciting stuff!", category="success")
        return redirect(url_for('admin.approve_characters'))
    return render_template('admin/approve_character.html', form=form, character=first_character)


@admin.route('/characters/<hashid>/edit', methods=('GET', 'POST'))
@limiter.limit('15/minute')
def edit_character(hashid):
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    live_character = get_object_or_404(Character, (Character.id == character_id))
    form = AdminCharacterForm()
    if request.method == 'GET':
        form.name.process_data(live_character.name)
        form.universe.process_data(live_character.universe.name)
        form.universe_action.process_data(True)
        form.age.process_data(live_character.age)
        form.height.process_data(live_character.height)
        form.weight.process_data(live_character.weight)
        form.species.process_data(live_character.species)
        form.gender.process_data(live_character.gender)
        form.occupation.process_data(live_character.occupation)
        form.status.process_data(live_character.status)
        form.description.process_data(live_character.description)
        form.official.process_data(live_character.official)
    if form.validate_on_submit():
        universe = Universe.get_or_none(fn.lower(Universe.name) == form.universe.data.lower())
        if form.universe_action.data == 'True':
            if not universe:
                form.universe.errors.append(f"The universe {form.universe.data} doesn't exist. ")
                form.universe_action.errors.append(f"The universe {form.universe.data} doesn't exist. ")
                return render_template('admin/edit_character.html', form=form, character=live_character)
        else:
            if not universe:
                if not any(form.categories.data):
                    return render_template('admin/edit_character.html', form=form, character=live_character,
                                           extra_errors="Please provide at least one category for the new universe. ")
                universe = Universe.create_universe(name=form.universe.data)
                for category in form.categories.data:
                    if category:
                        Category.create_category(universe=universe, name=category.title())
            else:
                form.universe.errors.append(f"The universe {form.universe.data} already exists. ")
                form.universe_action.errors.append(f"The universe {form.universe.data} already exists. ")
                return render_template('admin/edit_character.html', form=form, character=live_character)
        Character.update({
            Character.name: form.name.data,
            Character.search_name: fn.to_tsvector(form.name.data),
            Character.universe: universe,
            Character.age: form.age.data,
            Character.height: form.height.data,
            Character.weight: form.weight.data,
            Character.species: form.species.data,
            Character.gender: form.gender.data,
            Character.occupation: form.occupation.data,
            Character.status: form.status.data,
            Character.description: form.description.data,
            Character.official: form.official.data == 'True',
        }).where(Character.id == live_character.id).execute()
        if live_character.universe != universe:
            delete_old_ratings_and_create_new_ones(live_character, universe)
        else:
            # delete the old global rank values if the character has been set to be unofficial.
            if form.official.data == 'False' and live_character.official:
                GlobalRating.update({
                    GlobalRating.global_rank: None
                }).where(GlobalRating.character == live_character).execute()
                CategoryRating.update({
                    CategoryRating.global_category_rank: None
                }).where(CategoryRating.character == live_character).execute()
        delete_universe_if_no_characters_left(live_character.universe)  # retrieve old universe and then maybe delete it
        if form.character_picture.data:
            resized_img = resize_image(width=330, height=380, image_file=request.files['character_picture'])
            picture_url = upload_image(resized_img, app.config['PATH_READY_IMAGES'] + "character/" + create_pic_hashid(
                live_character.id, extra_salt=app.config['CHARACTER_LIVE_PIC']))
            Character.update({Character.character_picture: picture_url}).where(
                Character.id == live_character.id).execute()
        flash(message="Character updated. Let's hope they get happy, am i right? :)", category="success")
        return redirect(url_for('characters.character', hashid=create_char_hashid(live_character.id, extra_salt=app.config['CHARACTER'])))
    return render_template('admin/edit_character.html', form=form, character=live_character)


@admin.route('/pictures', methods=('GET',))
def approve_pictures():
    page = request.args.get('page', default=1, type=int)
    per_page = request.cookies.get('approve_pictures_per_page', 20, type=int)
    if per_page > 50:
        per_page = 50
    elif per_page < 1:
        per_page = 1
    total = CharacterTempPicture.select().count()
    pagination_pictures = CharacterTempPicture.select().order_by(+CharacterTempPicture.id) \
        .paginate(page=page, paginate_by=per_page)
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap4', bs_version=4,
                            record_name='submitted pictures', format_number=True, format_total=True,
                            alignment='center',
                            display_msg="Displaying <b>{start} - {end}</b> {record_name} in a total of <b>{total}</b>")
    try:
        return render_template('admin/approve_pictures.html', pictures=pagination_pictures, pagination=pagination)
    except DataError:
        abort(404)


@admin.route('/characters/<hashid>/pictures', methods=('GET',))
def edit_pictures(hashid):
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    live_character = get_object_or_404(Character, (Character.id == character_id))
    page = request.args.get('page', default=1, type=int)
    per_page = request.cookies.get('edit_pictures_per_page', 20, type=int)
    if per_page > 50:
        per_page = 50
    elif per_page < 1:
        per_page = 1
    total = live_character.pictures.count()
    pagination_pictures = live_character.pictures.paginate(page=page, paginate_by=per_page)
    pagination = Pagination(page=page, per_page=per_page, total=total, css_framework='bootstrap4', bs_version=4,
                            record_name='live pictures', format_number=True, format_total=True,
                            alignment='center',
                            display_msg="Displaying <b>{start} - {end}</b> {record_name} in a total of <b>{total}</b>")
    try:
        return render_template('admin/edit_pictures.html', pictures=pagination_pictures, pagination=pagination,
                               character=live_character)
    except DataError:
        abort(404)


@admin.route('/pictures/<hashid>/approve', methods=('GET', 'POST'))
@limiter.limit('15/minute')
def approve_picture(hashid):
    picture_id = decode_pic_hashid(hashid, extra_salt=app.config['CHARACTER_TEMP_PICS'])
    character_temp_picture = get_object_or_404(CharacterTempPicture, (CharacterTempPicture.id == picture_id))
    character_live_picture = CharacterPicture.create_character_picture(character=character_temp_picture.character)
    new_url = app.config['PATH_READY_IMAGES'] + "character_pictures/" + \
              create_pic_hashid(character_live_picture.id, extra_salt=app.config['CHARACTER_LIVE_PICS'])
    picture_url = upload_old_image(character_temp_picture.character_picture, new_url)
    CharacterPicture.update({CharacterPicture.character_picture: picture_url}).where(
        CharacterPicture.id == character_live_picture.id).execute()
    delete_image(character_temp_picture.character_picture)
    character_temp_picture.delete_instance()
    flash(message="Picture submitted to the public!", category="success")
    return redirect(url_for('admin.approve_pictures'))


@admin.route('/pictures/<hashid>/delete_live', methods=('GET', 'DELETE'))
@limiter.limit('15/minute')
def delete_live_picture(hashid):
    picture_id = decode_pic_hashid(hashid, extra_salt=app.config['CHARACTER_LIVE_PICS'])
    live_picture = get_object_or_404(CharacterPicture, (CharacterPicture.id == picture_id))
    character_id = live_picture.character.id
    delete_image(live_picture.character_picture)
    live_picture.delete_instance()
    flash(message="Picture deleted. Let's hope they will not get mad :(", category="success")
    return redirect(url_for('admin.edit_pictures',
                            hashid=create_char_hashid(character_id, extra_salt=app.config['CHARACTER'])))


@admin.route('/pictures/<hashid>/delete_submitted', methods=('GET', 'DELETE'))
@limiter.limit('15/minute')
def delete_submitted_picture(hashid):
    picture_id = decode_pic_hashid(hashid, extra_salt=app.config['CHARACTER_TEMP_PICS'])
    temp_picture = get_object_or_404(CharacterTempPicture, (CharacterTempPicture.id == picture_id))
    delete_image(temp_picture.character_picture)
    temp_picture.delete_instance()
    flash(message="Picture deleted. Let's hope they will not get mad :(", category="success")
    return redirect(url_for('admin.approve_pictures'))


@admin.route('/characters/<hashid>/delete_live', methods=('GET', 'DELETE'))
@limiter.limit('15/minute')
def delete_live_character(hashid):
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER'])
    live_character = get_object_or_404(Character, (Character.id == character_id))
    delete_live_character_completely(live_character)
    flash(message="Character deleted. Let's hope they will not get mad :(", category="success")
    return redirect(url_for('characters.render_characters'))


@admin.route('/characters/<hashid>/delete_submitted', methods=('GET', 'DELETE'))
@limiter.limit('15/minute')
def delete_submitted_character(hashid):
    character_id = decode_char_hashid(hashid, extra_salt=app.config['CHARACTER_TEMP'])
    temp_character = get_object_or_404(CharacterTemp, (CharacterTemp.id == character_id))
    delete_image(temp_character.character_picture)
    temp_character.delete_instance()
    flash(message="Character deleted. Let's hope they will not get mad :(", category="success")
    return redirect(url_for('admin.approve_characters'))
