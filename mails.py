from threading import Thread

from flask import render_template, url_for
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer

from main import mail, app
from models import User
from utils import create_char_hashid


def _send_mail_in_new_context(flask_app, msg: Message):
    with flask_app.app_context():
        mail.send(msg)


def _send_bulk_mails_in_new_context(flask_app, msg: Message, text_message: str):
    with flask_app.app_context():
        with mail.connect() as conn:
            for user in User.select().where(User.email_confirmed & User.receive_email_news & ~User.is_banned):
                msg.html = render_template('mails/global.html', message=text_message, reason=msg.subject,
                                           username=user.username)
                msg.recipients = [user.email]
                conn.send(msg)


def _send_email(subject: str, recipients: list, html_body: str, images=None):
    msg = _mail_message_setup(subject=subject, recipients=recipients, images=images, html_body=html_body)
    # Send mail asynchronously
    thread = Thread(target=_send_mail_in_new_context, args=[app, msg])
    thread.start()


def _mail_message_setup(subject: str, images, html_body=None, recipients=None):
    msg = Message(subject, sender=('TopAnimeCharacters.com', 'no-reply@topanimecharacters.com'), recipients=recipients)
    if images:
        for image in images:
            msg.attach(image.filename, image.content_type, image.read())
    msg.html = html_body
    return msg


def send_mails_globally(reason, message, images):
    msg = _mail_message_setup(reason, images=images)
    # Send mails asynchronously
    thread = Thread(target=_send_bulk_mails_in_new_context, args=[app, msg, message])
    thread.start()


def send_confirmation_email(user_email, username):
    confirm_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    confirm_url = url_for('users.confirm_email',
                          token=confirm_serializer.dumps(user_email, salt=app.config['EMAIL_URL_SALT']),
                          _external=True)
    html = render_template('mails/confirmation_mail.html', confirm_url=confirm_url, username=username)
    _send_email(subject='Email Confirmation', recipients=[user_email], html_body=html)


def email_confirmation_resend(user_email, username):
    confirm_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    confirm_url = url_for('users.confirm_email',
                          token=confirm_serializer.dumps(user_email, salt=app.config['EMAIL_URL_SALT']),
                          _external=True)
    html = render_template('mails/reconfirmation_mail.html', confirm_url=confirm_url, username=username)
    _send_email(subject='Email Reconfirmation', recipients=[user_email], html_body=html)


def send_password_reset_email(user_email, username):
    password_reset_serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    password_reset_url = url_for('users.reset_password_with_token', token=password_reset_serializer
                                 .dumps(user_email, salt=app.config['PASSWORD_URL_SALT']), _external=True)
    html = render_template('mails/password_reset_mail.html', password_reset_url=password_reset_url, username=username)
    _send_email(subject='Reset Password', recipients=[user_email], html_body=html)


def send_account_deletion_mail(user_email, username):
    html = render_template('mails/account_deletion_mail.html', username=username)
    _send_email(subject="Account deleted", recipients=[user_email], html_body=html)


def send_ban_mail(user_email, username):
    html = render_template('mails/account_banned_mail.html', username=username)
    _send_email(subject="Account BANNED", recipients=[user_email], html_body=html)


def send_to_us(reason, message, username, email, profile_picture, images, account: bool):
    html = render_template('mails/message.html', message=message, username=username, email=email,
                           profile_picture=profile_picture, account=account)
    recipient = 'randomanddisposable@gmail.com' if reason == 'Business' or reason == 'Website appreciation' \
        else 'tacsuport2@gmail.com'
    _send_email(subject=reason, recipients=[recipient], html_body=html, images=images)


def send_ping_user_email(user_email, to_user, comment, comment_content):
    html = render_template(
        template_name_or_list='mails/ping_user_mail.html',
        comment_content=comment_content,
        from_user=comment.user.username,
        to_user=to_user,
        character=comment.character,
        character_url=url_for(endpoint='characters.character',
                              hashid=create_char_hashid(comment.character.id, extra_salt=app.config['CHARACTER']),
                              _external=True))
    _send_email(subject='User ping', recipients=[user_email], html_body=html)
