import os

from flask import Flask, render_template, request, flash, redirect, session, g
from flask_debugtoolbar import DebugToolbarExtension
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func  # NEW

from forms import UserAddForm, LoginForm, MessageForm, EditProfileForm
from models import db, connect_db, User, Message, Likes, Follows  # +Follows

CURR_USER_KEY = "curr_user"

app = Flask(__name__)

# Normalize postgres:// -> postgresql:// (safety for some hosts; harmless otherwise)
uri = os.environ.get('DATABASE_URL', 'postgresql:///warbler')
if uri.startswith('postgres://'):
    uri = uri.replace('postgres://', 'postgresql://', 1)

# Get DB_URI from environ variable (useful for production/testing) or default local.
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ECHO'] = False
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "it's a secret")
toolbar = DebugToolbarExtension(app)

connect_db(app)

##############################################################################
# Helpers

def suggested_users_for(user, limit=5):
    """Return a list of suggested users to follow (not me, not already followed),
    ranked by follower count."""
    if not user:
        return []
    return (
        User.query
            .filter(
                User.id != user.id,
                ~User.followers.any(id=user.id)
            )
            .outerjoin(Follows, Follows.user_being_followed_id == User.id)
            .group_by(User.id)
            .order_by(func.count(Follows.user_following_id).desc(), User.id.asc())
            .limit(limit)
            .all()
    )

##############################################################################
# User signup/login/logout

@app.before_request
def add_user_to_g():
    """If we're logged in, add curr user to Flask global."""
    if CURR_USER_KEY in session:
        g.user = User.query.get(session[CURR_USER_KEY])
    else:
        g.user = None

def do_login(user):
    """Log in user."""
    session[CURR_USER_KEY] = user.id

def do_logout():
    """Logout user."""
    if CURR_USER_KEY in session:
        del session[CURR_USER_KEY]

@app.route('/signup', methods=["GET", "POST"])
def signup():
    """Handle user signup."""
    form = UserAddForm()

    if form.validate_on_submit():
        try:
            user = User.signup(
                username=form.username.data,
                password=form.password.data,
                email=form.email.data,
                image_url=form.image_url.data or User.image_url.default.arg,
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Username or email already taken", 'danger')
            return render_template('users/signup.html', form=form)

        do_login(user)
        return redirect("/")

    return render_template('users/signup.html', form=form)

@app.route('/login', methods=["GET", "POST"])
def login():
    """Handle user login."""
    form = LoginForm()

    if form.validate_on_submit():
        user = User.authenticate(form.username.data, form.password.data)

        if user:
            do_login(user)
            flash(f"Hello, {user.username}!", "success")
            return redirect("/")

        flash("Invalid credentials.", 'danger')

    return render_template('users/login.html', form=form)

@app.route('/logout', methods=["GET", "POST"])
def logout():
    """Handle logout of user: clear session, flash, redirect to login."""
    do_logout()
    g.user = None
    flash("You have been logged out.", "success")
    return redirect("/login")

##############################################################################
# General user routes:

@app.route('/users')
def list_users():
    """Page with listing of users. Optional 'q' querystring to search."""
    search = request.args.get('q')

    if not search:
        users = User.query.all()
    else:
        users = User.query.filter(User.username.like(f"%{search}%")).all()

    return render_template('users/index.html', users=users)

@app.route('/users/<int:user_id>')
def users_show(user_id):
    """Show user profile."""
    user = User.query.get_or_404(user_id)

    messages = (Message
                .query
                .filter(Message.user_id == user_id)
                .order_by(Message.timestamp.desc())
                .limit(100)
                .all())

    liked_ids = set([m.id for m in g.user.likes]) if g.user else set()
    return render_template('users/show.html', user=user, messages=messages, liked_ids=liked_ids)

@app.route('/users/<int:user_id>/following')
def show_following(user_id):
    """Show list of people this user is following."""
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/following.html', user=user)

@app.route('/users/<int:user_id>/followers')
def users_followers(user_id):
    """Show list of followers of this user."""
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    user = User.query.get_or_404(user_id)
    return render_template('users/followers.html', user=user)

@app.route('/users/follow/<int:follow_id>', methods=['POST'])
def add_follow(follow_id):
    """Add a follow for the currently-logged-in user."""
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get_or_404(follow_id)
    g.user.following.append(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")

@app.route('/users/stop-following/<int:follow_id>', methods=['POST'])
def stop_following(follow_id):
    """Have currently-logged-in-user stop following this user."""
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    followed_user = User.query.get(follow_id)
    g.user.following.remove(followed_user)
    db.session.commit()

    return redirect(f"/users/{g.user.id}/following")

@app.route('/users/profile', methods=["GET", "POST"])
def profile():
    """Update profile for current user."""
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    form = EditProfileForm(
        username=g.user.username,
        email=g.user.email,
        image_url=g.user.image_url,
        header_image_url=g.user.header_image_url,
        location=g.user.location,
        bio=g.user.bio,
    )

    if form.validate_on_submit():
        user = User.authenticate(g.user.username, form.password.data)
        if not user:
            flash("Incorrect password.", "danger")
            return render_template('users/edit.html', form=form)

        g.user.username = form.username.data
        g.user.email = form.email.data
        g.user.image_url = form.image_url.data or g.user.image_url
        g.user.header_image_url = form.header_image_url.data or g.user.header_image_url
        g.user.location = form.location.data
        g.user.bio = form.bio.data

        try:
            db.session.commit()
            flash("Profile updated!", "success")
            return redirect(f"/users/{g.user.id}")
        except IntegrityError:
            db.session.rollback()
            flash("Username or email already taken.", "danger")

    return render_template('users/edit.html', form=form)

@app.route('/users/delete', methods=["POST"])
def delete_user():
    """Delete user."""
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    do_logout()

    db.session.delete(g.user)
    db.session.commit()

    return redirect("/signup")

##############################################################################
# Likes routes

@app.post('/messages/<int:message_id>/like')
def toggle_like(message_id):
    """Like or unlike a message. Users cannot like their own messages."""
    if not g.user:
        flash("Access unauthorized.", "danger")
        return redirect("/")

    msg = Message.query.get_or_404(message_id)

    if msg.user_id == g.user.id:
        flash("You cannot like your own message.", "warning")
        return redirect(request.referrer or f"/users/{g.user.id}")

    like = Likes.query.filter_by(user_id=g.user.id, message_id=message_id).first()
    if like:
        db.session.delete(like)
    else:
        db.session.add(Likes(user_id=g.user.id, message_id=message_id))

    db.session.commit()
    return redirect(request.referrer or "/")

@app.get('/users/<int:user_id>/likes')
def show_likes(user_id):
    """Show messages this user has liked."""
    user = User.query.get_or_404(user_id)
    messages = (Message.query
                .join(Likes, Likes.message_id == Message.id)
                .filter(Likes.user_id == user.id)
                .order_by(Message.timestamp.desc())
                .all())
    liked_ids = set([m.id for m in g.user.likes]) if g.user else set()
    return render_template("users/likes.html", user=user, messages=messages, liked_ids=liked_ids)

##############################################################################
# Homepage and error pages

@app.route('/')
def homepage():
    """Show homepage:
    - anon users: splash page
    - logged in: follow feed; if empty, show global recent + suggestions
    """
    if not g.user:
        return render_template('home-anon.html')

    ids = [u.id for u in g.user.following] + [g.user.id]
    messages = (Message.query
                .filter(Message.user_id.in_(ids))
                .order_by(Message.timestamp.desc())
                .limit(100)
                .all())

    # Fallback for brand-new users with an empty feed
    if not g.user.following:
        messages = (Message.query
                    .order_by(Message.timestamp.desc())
                    .limit(50)
                    .all())
        flash("Your feed is empty. Here are recent posts—follow people to customize it!", "info")

    liked_ids = set(m.id for m in g.user.likes)
    suggested = suggested_users_for(g.user, limit=5)

    return render_template('home.html',
                           messages=messages,
                           liked_ids=liked_ids,
                           suggested_users=suggested)

##############################################################################
# Turn off all caching in Flask

@app.after_request
def add_header(req):
    """Add non-caching headers on every request."""
    req.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req.headers["Pragma"] = "no-cache"
    req.headers["Expires"] = "0"
    req.headers['Cache-Control'] = 'public, max-age=0'
    return req
