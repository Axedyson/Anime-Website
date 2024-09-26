from flask import Blueprint, flash, redirect, url_for, render_template, jsonify, g, abort, request, session
from flask_login import login_required, logout_user, login_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from mails import send_confirmation_email, send_account_deletion_mail, email_confirmation_resend, \
    send_password_reset_email, send_to_us
from main import limiter, hashing, app
from models import User, delete_image, upload_image
from users.forms import DeleteForm, LoginForm, RegisterForm, EmailFormForEmailChange, ResetPasswordWithTokenForm, \
    ResetPasswordForm, UsernameForm, ProfilePictureForm, EmailFormForPasswordReset, AuthenticatedContactForm, \
    PublicContactForm, EmailSettings
from users.utils import _is_safe_url
from utils import create_pic_hashid, resize_image, _return_proper_datetime

users = Blueprint('users', __name__)


@users.route('/logout')
@login_required
def logout():
    logout_user()
    flash(message="You've been logged out, come back soon", category="success")
    return redirect(url_for('central.home'))


@users.route('/account', methods=('GET',))
@login_required
def account():
    # make the email modal open on page load if this query parameter has a value (any value)
    launch_email_modal = request.args.get('unsubscribe')
    # instantiate the mail forms so they are ready for post request on other view functions
    delete_form = DeleteForm()
    # gotta have this prefix so chrome doesn't complain about two non-unique ids for the csrf_token fields
    email_form = EmailSettings(prefix='email_')
    if not g.user.email_confirmed:
        email_form.news_letters.process_data(False)
        email_form.user_pings.process_data(False)
    else:
        email_form.news_letters.process_data(g.user.receive_email_news)
        email_form.user_pings.process_data(g.user.receive_email_pings)
    return render_template('account.html', delete_form=delete_form, email_form=email_form,
                           launch_email_modal=launch_email_modal)


@users.route('/contact', methods=('GET', 'POST'))
@limiter.limit('15/minute')
def contact():
    if g.user.is_authenticated:
        if g.user.is_admin:
            flash(message="You are an admin, why would an admin want to send a message to other admins?",
                  category="warning")
            return redirect(url_for('central.home'))
        form = AuthenticatedContactForm()
        if request.method == 'GET':
            if request.args.get('server_error'):
                form.reason.process_data('Server error')
            elif request.args.get('character_removal'):
                form.reason.process_data('Edit character')
            form.email.process_data(g.user.email)
        if form.validate_on_submit():
            # The most suitable way to check if there have been submitted files is to check the first files name
            images = request.files.getlist('image_attachments') if form.image_attachments.data[0].filename else None
            send_to_us(form.reason.data, form.message.data, g.user.username, form.email.data, g.user.profile_picture,
                       images, account=True)
            flash(message="Your message has been sent, please be patient while waiting for a response to your email!",
                  category="success")
            return redirect(url_for('central.home'))
    else:
        form = PublicContactForm()
        if request.method == 'GET':
            if request.args.get('server_error'):
                form.reason.process_data('Server error')
            elif request.args.get('character_removal'):
                form.reason.process_data('Edit character')
        if form.validate_on_submit():
            # The most suitable way to check if there have been submitted files is to check the first files name
            images = request.files.getlist('image_attachments') if form.image_attachments.data[0].filename else None
            send_to_us(form.reason.data, form.message.data, form.name.data, form.email.data, app.config['DEFAULT_PROFILE_PIC'],
                       images, account=False)
            flash(message="Your message has been sent, please be patient while waiting for a response to your email!",
                  category="success")
            return redirect(url_for('central.home'))
    return render_template('contact.html', form=form)


@users.route('/account/change_email_settings', methods=('POST',))
@login_required
@limiter.limit('15/minute')
def change_email_settings():
    if not g.user.email_confirmed:
        flash(message="You are not allowed to change your email settings because you haven't confirmed your email "
                      "address", category="warning")
        return redirect(url_for('users.account'))
    # gotta have this prefix so chrome doesn't complain about two non-unique ids for the csrf_token fields
    form = EmailSettings(prefix='email_')
    if form.validate_on_submit():
        User.update({
            User.receive_email_news: form.news_letters.data,
            User.receive_email_pings: form.user_pings.data
        }).where(User.id == g.user.id).execute()
        flash(message="Your email settings have been updated!", category="success")
        return redirect(url_for('users.account'))
    flash(message="Something went wrong while trying to update your email settings", category='danger')
    return redirect(url_for('users.account'))


@users.route('/account/delete', methods=('POST',))
@limiter.limit('15/minute')
def delete_account():
    if not g.user.is_authenticated:
        return jsonify(password_errors=["You need to be logged into your account before you can delete it xD"],
                       delete_errors=["You need to be logged into your account before you can delete it xD"]), 403
    form = DeleteForm()
    if form.validate_on_submit():
        if hashing.check_password_hash(g.user.password, form.current_password.data):
            if g.user.profile_picture[app.config['LEN_OF_PATH_OF_PROFILE_PIC']:] != 'default':  # delete only if the picture isn't the default picture
                delete_image(g.user.profile_picture)
            g.user.delete_instance()
            send_account_deletion_mail(g.user.email, g.user.username)
            logout_user()
            flash(message="Your user account has been deleted. It's sad but it's true :(", category="success")
            return jsonify(status="success")
        else:
            return jsonify(delete_errors=[], password_errors=["Your current password doesn't match! "]), 422
    return jsonify(delete_errors=form.delete_field.errors, password_errors=form.current_password.errors), 422


@users.route('/login', methods=('GET', 'POST'))
def login():
    if g.user.is_authenticated:
        flash(message="You're already logged in...", category="info")
        return redirect(url_for('central.home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.get_or_none(User.email == form.email.data.lower())
        if not user:
            flash(message="Your email or password doesn't match!", category="warning")
        else:
            if hashing.check_password_hash(user.password, form.password.data):
                if user.is_banned:
                    flash(message="Your user account has been BANNED. That's why you can't log in", category="danger")
                    return redirect(url_for('central.home'))
                User.update({
                    User.last_log_in: user.current_log_in,
                    User.current_log_in: _return_proper_datetime(form.time.data)
                }).where(User.id == user.id).execute()
                login_user(user, remember=form.remember_me.data)
                next_page_path = request.args.get('next')
                # _is_safe_url function should check if the url is safe for redirects.
                if not _is_safe_url(next_page_path):
                    abort(400)
                flash(message=f"Welcome You've been logged in {g.user.username}!", category="success")
                return redirect(next_page_path or url_for('central.home'))
            else:
                flash(message="Your email or password doesn't match!", category="warning")
    return render_template('login.html', form=form)


@users.route('/account/change_email', methods=('GET', 'POST'))
@login_required
@limiter.limit('15/hour')
def change_email():
    form = EmailFormForEmailChange()
    if request.method == 'GET':
        form.email.process_data(g.user.email)
    if form.validate_on_submit():
        if hashing.check_password_hash(g.user.password, form.current_password.data):
            User.update({
                User.email: form.email.data.lower(),
                User.email_confirmed: False,
                User.email_confirmed_on: None
            }).where(User.id == g.user.id).execute()
            user = User.get_by_id(g.user.id)
            email_confirmation_resend(user.email, user.username)
            flash(message="Email changed. A confirmation link is on it's way to your new email", category="success")
            return redirect(url_for('users.account'))
        else:
            flash(message="Your password doesn't match!", category="warning")
    return render_template('change_email.html', form=form)


@users.route('/account/change_password', methods=('GET', 'POST'))
@login_required
@limiter.limit('15/minute')
def change_password():
    form = ResetPasswordForm()
    if form.validate_on_submit():
        if hashing.check_password_hash(g.user.password, form.current_password.data):
            User.update({User.password: hashing.generate_password_hash(form.new_password.data).decode('utf-8')}).where(
                User.id == g.user.id).execute()
            flash(message="Password has been updated", category="success")
            return redirect(url_for('users.account'))
        else:
            flash(message="Your current password doesn't match!", category="warning")
    return render_template('change_password.html', form=form)


@users.route('/account/change_username', methods=('GET', 'POST'))
@login_required
@limiter.limit('15/minute')
def change_username():
    form = UsernameForm()
    if request.method == 'GET':
        form.username.process_data(g.user.username)
    if form.validate_on_submit():
        User.update({User.username: form.username.data}).where(User.id == g.user.id).execute()
        flash(message="Username has been updated. Let's hope others like it, am i right? :)", category="success")
        return redirect(url_for('users.account'))
    return render_template('change_username.html', form=form)


@users.route('/account/update_profile_picture', methods=('GET', 'POST'))
@login_required
@limiter.limit('15/minute')
def update_profile_picture():
    form = ProfilePictureForm()
    if form.validate_on_submit():
        resized_img = resize_image(width=165, height=165, image_file=request.files['profile_picture'])
        picture_url = upload_image(resized_img, app.config['PATH_READY_IMAGES'] + "profile/" +
                                   create_pic_hashid(g.user.id, extra_salt=app.config['PFP']))
        User.update({User.profile_picture: picture_url}).where(User.id == g.user.id).execute()
        flash(message="Profile picture has been updated. Let's hope others like it, am i right? :)", category="success")
        return redirect(url_for('users.account'))
    return render_template('update_profile_picture.html', form=form)


@users.route('/account/remove_profile_picture', methods=('GET', 'POST'))
@login_required
@limiter.limit('15/minute')
def remove_profile_picture():
    if g.user.profile_picture[app.config['LEN_OF_PATH_OF_PROFILE_PIC']:] == 'default':  # don't remove if the user has the default profile picture
        flash(message="You don't have a profile picture, nothing to remove", category="warning")
        return redirect(url_for('users.account'))
    delete_image(g.user.profile_picture)
    default_picture = 'https://storage.googleapis.com/topanimecharacters.com/validated/images/profile/default'
    User.update({User.profile_picture: default_picture}).where(User.id == g.user.id).execute()
    flash(message="Profile picture removed, reverted back to the default profile picture", category="success")
    return redirect(url_for('users.account'))


@users.route('/account/reset_password/<token>', methods=('GET', 'POST'))
@limiter.limit('15/minute')
def reset_password_with_token(token):
    try:
        password_reset_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        email = password_reset_serializer.loads(token, salt=app.config['PASSWORD_URL_SALT'],
                                                max_age=app.config['TOKEN_MAX_AGE'])
    except (BadSignature, SignatureExpired):
        flash(message="The reset password link is invalid or has expired", category="danger")
        return redirect(url_for('users.login'))
    form = ResetPasswordWithTokenForm()
    if form.validate_on_submit():
        User.update({User.password: hashing.generate_password_hash(form.new_password.data).decode('utf-8')}).where(
            User.email == email).execute()
        flash(message="Your password has been updated", category="success")
        return redirect(url_for('users.login'))
    return render_template('reset_password_with_token.html', form=form, token=token)


@users.route('/account/reset_password', methods=('GET', 'POST'))
@limiter.limit('15/hour')
def reset_password():
    form = EmailFormForPasswordReset()
    if form.validate_on_submit():
        user = User.get(User.email == form.email.data.lower())
        if user.email_confirmed:
            send_password_reset_email(user.email, user.username)
            flash(message="A password reset link is on it's way to your email", category="success")
            return redirect(url_for('users.login'))
        else:
            email_confirmation_resend(user.email, user.username)
            flash(message="Please confirm your email before attempting a password reset. Another email confirmation "
                          "link is on it's way to your email just in case", category="warning")
    return render_template('reset_password.html', form=form)


@users.route('/register', methods=('GET', 'POST'))
@limiter.limit('15/minute')
def register():
    if g.user.is_authenticated:
        flash(message="Please log out to actually create a new account", category="info")
        return redirect(url_for('central.home'))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User.create_user(
            username=form.username.data,
            email=form.email.data.lower(),
            password=hashing.generate_password_hash(form.password.data).decode('utf-8'),
            joined_at=_return_proper_datetime(form.time.data)
        )
        if form.profile_picture.data:
            new_url = app.config['PATH_READY_IMAGES'] + "profile/" + \
                      create_pic_hashid(user.id, extra_salt=app.config['PFP'])
            resized_img = resize_image(width=330, height=330, image_file=request.files['profile_picture'])
            picture_url = upload_image(resized_img, new_url)
        else:
            picture_url = 'https://storage.googleapis.com/topanimecharacters.com/validated/images/profile/default'
        User.update({User.profile_picture: picture_url}).where(User.id == user.id).execute()
        send_confirmation_email(user.email, user.username)
        login_user(user, remember=form.remember_me.data)
        flash(message="Yay, you've signed up! An email confirmation link is on it's way to your email, please confirm "
                      "it", category="success")
        return redirect(url_for('central.home'))
    return render_template('register.html', form=form)


@users.route('/account/confirm/<token>')
def confirm_email(token):
    try:
        confirm_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        email = confirm_serializer.loads(token, salt=app.config['EMAIL_URL_SALT'],
                                         max_age=app.config['TOKEN_MAX_AGE'])
    except (BadSignature, SignatureExpired):
        flash(message="The confirmation link is invalid or has expired", category="danger")
        return redirect(url_for('central.home'))
    user = User.get_or_none(User.email == email)
    if user is None:
        flash(message="The confirmation link is invalid or has expired", category="danger")
        return redirect(url_for('central.home'))
    if user.email_confirmed:
        flash(message="Account already confirmed", category="info")
        return redirect(url_for('central.home'))
    else:
        session['email_confirmation'] = user.id
        return redirect(url_for('central.home'))


@users.route('/account/confirm_email_final', methods=('POST',))
def confirm_email_final():
    user_id = session.pop('email_confirmation', default=None)
    user = User.get_or_none(User.id == user_id)
    if not user:
        return jsonify(message="Couldn't confirm your email address unfortunately"), 401
    if user.email_confirmed:
        return jsonify(message="We thank you for having confirmed your email address :)")
    User.update({
        User.email_confirmed: True,
        User.email_confirmed_on: _return_proper_datetime(request.get_json())
    }).where(User.id == user_id).execute()
    return jsonify(message="Thank you for confirming your email address!")


@users.route('/account/resend_confirmation')
@login_required
@limiter.limit('2/hour')
def resend_email_confirmation():
    if g.user.email_confirmed:
        flash(message="Account already confirmed", category="info")
        return redirect(url_for('users.account'))
    email_confirmation_resend(g.user.email, g.user.username)
    flash(message="Another email confirmation link is on it's way to your email", category="success")
    return redirect(url_for('users.account'))


@users.route('/frequently_asked_questions', methods=('GET',))
def frequently_asked_questions():
    return render_template('about/frequently_asked_questions.html')


@users.route('/cookies_policy', methods=('GET',))
def cookies_policy():
    return render_template('about/cookies_policy.html')


@users.route('/privacy_policy', methods=('GET',))
def privacy_policy():
    return render_template('about/privacy_policy.html')


@users.route('/terms_of_use', methods=('GET',))
def terms_of_use():
    return render_template('about/terms_of_use.html')
