from urllib.parse import urlparse, urlunparse

from flask import Blueprint, request, redirect, g, render_template, url_for, flash
from flask_login import current_user, logout_user

from main import app
from models import DATABASE, Character, CategoryRelationship, GlobalRating, fn, User, Universe, JOIN

central = Blueprint('central', __name__)


@central.before_app_request
def before_request():
    DATABASE.connect()
    g.user = current_user
    url_parts = urlparse(request.url)
    if url_parts.netloc == app.config['DOMAIN_NAME_WITH_WWW']:
        url_parts_list = list(url_parts)
        url_parts_list[1] = app.config['DOMAIN_NAME_WITH_WWW'].replace('www.', '')
        new_url = urlunparse(url_parts_list)
        return redirect(new_url, code=301)
    if g.user.is_authenticated and g.user.is_banned:
        logout_user()
        flash(message="You've been BANNED.", category="danger")
        return redirect(url_for('central.home'))


@central.after_app_request
def after_request(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'deny'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


@central.teardown_app_request
def teardown_request(error):
    if not DATABASE.is_closed():
        DATABASE.close()


@central.route('/', methods=('GET',))
@central.route('/home', methods=('GET',))
def home():
    most_voted_characters = Character.select().join(CategoryRelationship, JOIN.LEFT_OUTER).group_by(Character).order_by(-fn.COUNT(fn.DISTINCT(CategoryRelationship.user))).limit(8)
    recent_characters = Character.select().order_by(-Character.id).limit(8) 
    top_unofficial_characters = Character.select().where(~Character.official).join(GlobalRating).order_by(-fn.to_number(GlobalRating.overall_score, '999G999')).order_by(GlobalRating.overall_score.desc(nulls='LAST')).limit(8)
    most_characters_universes = [universe[1] for universe in Universe.select().join(Character).group_by(Universe).order_by(-fn.COUNT(Character.universe)).limit(20).tuples()]
    recent_universes = [universe[1] for universe in Universe.select().order_by(-Universe.id).limit(20).tuples()]
    # "characters_and_universes_available=bool(most_voted_characters.count())" if this returns "True" then i know there must be at least one universe and one character.
    # Note that you are checking if there exist unofficial characters by doing "{% if top_unofficial_characters.count() %}" in the template.
    return render_template('home.html', most_voted_characters=most_voted_characters, most_characters_universes=most_characters_universes, recent_universes=recent_universes,
        recent_characters=recent_characters, top_unofficial_characters=top_unofficial_characters, characters_and_universes_available=bool(most_voted_characters.count()))
