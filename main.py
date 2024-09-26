from flask import Flask
from flask_assets import Environment, Bundle
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_mail import Mail
from flask_htmlmin import HTMLMIN
from flask_paranoid import Paranoid
from flask_wtf import CSRFProtect

app = Flask(__name__)

from config import Config

app.config.from_object(Config)

login_manager = LoginManager(app=app)

login_manager.session_protection = None
login_manager.login_view = 'users.login'
login_manager.login_message = 'You need to be logged in to access/use this page'
login_manager.login_message_category = 'warning'

assets = Environment(app=app)

main_css = Bundle('css/styles.css', output='gen/main.min.css', filters='cssmin')
character_css = Bundle('css/vendor/jquery-comments.css', main_css, output='gen/character.min.css', filters='cssmin')
main_js = Bundle('js/styles.js', 'js/utils.js', output='gen/main.min.js', filters='jsmin')
character_js = Bundle('js/vendor/jquery-comments.js', 'js/vendor/jquery-viewer.js', main_js,
                      output='gen/character.min.js', filters='jsmin')

assets.register('main_css', main_css)
assets.register('character_css', character_css)
assets.register('main_js', main_js)
assets.register('character_js', character_js)


HTMLMIN(app=app)
Paranoid(app=app)
CSRFProtect(app=app)
limiter = Limiter(app=app, key_func=get_remote_address)
hashing = Bcrypt(app=app)
mail = Mail(app=app)


from utils import create_char_hashid, create_pic_hashid

app.jinja_env.globals.update(create_char_hashid=create_char_hashid, create_pic_hashid=create_pic_hashid,
							DEFAULT_PROFILE_PIC=app.config['DEFAULT_PROFILE_PIC'],
                            CHARACTER_LIVE_PICS=app.config['CHARACTER_LIVE_PICS'],
                            CHARACTER_TEMP_PICS=app.config['CHARACTER_TEMP_PICS'],
                            CHARACTER_TEMP_PIC=app.config['CHARACTER_TEMP_PIC'],
                            CHARACTER_LIVE_PIC=app.config['CHARACTER_LIVE_PIC'],
                            CHARACTER_TEMP=app.config['CHARACTER_TEMP'],
                            CHARACTER=app.config['CHARACTER'],
                            PFP=app.config['PFP'])

from central.routes import central
from errors.handlers import errors
from admin.routes import admin
from users.routes import users
from characters.routes import characters

app.register_blueprint(central)
app.register_blueprint(errors)
app.register_blueprint(admin)
app.register_blueprint(users)
app.register_blueprint(characters)
