from main import app
from models import DATABASE, CharacterTemp, User, Character, Comment, CommentRelationship, Ping, \
    CharacterTempPicture, CharacterPicture, Universe, Category, CategoryRelationship, CategoryTemp, GlobalRating, \
    CategoryRating

DEBUG = True
PORT = 8080
HOST = 'localhost'

DATABASE.connect()
DATABASE.create_tables(
    [User, CharacterTemp, Character, Comment, CommentRelationship, Ping, CharacterTempPicture, CharacterPicture,
     Universe, Category, CategoryRelationship, CategoryTemp, GlobalRating, CategoryRating],
    safe=True)
DATABASE.close()

app.run(debug=DEBUG, port=PORT, host=HOST)


# Also remmeber to change the app.yaml python runtime version from python37 to python38 when it's available to do so!


# TODO try to make better SEO performance ya know!
# TODO fix licensing issues if there are any!

# TODO in general just improve front-end message/error message/success message etc!
# TODO provide better email messages
# TODO provide better limiter times for UX and security!
# TODO maybe obfuscate query parameters for better security

# You can try to release your website already here actually or maybe just for a beta version ya know.

# TODO probably upgrade the database by now, and see if you can fix potential connection timeout/issues!!
# TODO make sure to update all libraries!

# TODO provide better meta tag descriptions for every single none ajax endpoint, you know what i mean!
# TODO improve form validation in general (better UX, and message etc.)
# TODO send emails more regularly
# TODO try to make your own new logo with new generated meta/link tags for you new icons!!

# TODO my dad couldn't use the autocomple login form provided by safari properly i think. Whats that all about hmmm?
# TODO try to fix picture submit button won't work on safari browser


# TODO you need to put GDPR consent on your website and maybe get a database consent agreement in place!
# TODO add some guidelines so people can't just do what ever they want!
# TODO terms of service document!
# TODO privacy policy document!
