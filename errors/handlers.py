from flask import Blueprint, render_template

errors = Blueprint('errors', __name__)


@errors.app_errorhandler(400)
def bad_request(error):
    return render_template('errors/400.html'), 400


@errors.app_errorhandler(401)
def unauthorized(error):
    return render_template('errors/401.html'), 401


@errors.app_errorhandler(403)
def forbidden(error):
    return render_template('errors/403.html'), 403


@errors.app_errorhandler(404)
def page_not_found(error):
    return render_template('errors/404.html'), 404


@errors.app_errorhandler(405)
def method_not_allowed(error):
    return render_template('errors/405.html'), 405


@errors.app_errorhandler(429)
def too_many_requests(error):
    return render_template('errors/429.html'), 429


@errors.app_errorhandler(500)
def internal_sever_error(error):
    return render_template('errors/500.html'), 500
