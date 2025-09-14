"""SQLAlchemy models for Warbler."""

from datetime import datetime

from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy

bcrypt = Bcrypt()
db = SQLAlchemy()


class Follows(db.Model):
    """Connection of a follower <-> followed_user."""

    __tablename__ = "follows"

    user_being_followed_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user_following_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )


class Likes(db.Model):
    """Mapping user likes to warbles."""
    __tablename__ = 'likes'

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('users.id', ondelete='cascade'),
        primary_key=True
    )

    message_id = db.Column(
        db.Integer,
        db.ForeignKey('messages.id', ondelete='cascade'),
        primary_key=True
    )

    message_id = db.Column(
        db.Integer,
        db.ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )


class User(db.Model):
    """User in the system."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.Text, nullable=False, unique=True)

    username = db.Column(db.Text, nullable=False, unique=True)

    image_url = db.Column(db.Text, default="/static/images/default-pic.png")

    header_image_url = db.Column(db.Text, default="/static/images/warbler-hero.jpg")

    bio = db.Column(db.Text)

    location = db.Column(db.Text)

    password = db.Column(db.Text, nullable=False)

    # --- Relationships ---

    # User -> Message (one-to-many)
    messages = db.relationship(
        "Message",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Followers: users who follow *this* user
    followers = db.relationship(
        "User",
        secondary="follows",
        primaryjoin=(Follows.user_being_followed_id == id),
        secondaryjoin=(Follows.user_following_id == id),
        back_populates="following",
        lazy="selectin",
    )

    # Following: users *this* user follows
    following = db.relationship(
        "User",
        secondary="follows",
        primaryjoin=(Follows.user_following_id == id),
        secondaryjoin=(Follows.user_being_followed_id == id),
        back_populates="followers",
        lazy="selectin",
    )

    # Likes: messages this user liked
    likes = db.relationship(
        "Message",
        secondary="likes",
        back_populates="likers",
        lazy="selectin",
        passive_deletes=True,
    )

    def __repr__(self):
        return f"<User #{self.id}: {self.username}, {self.email}>"

    def is_followed_by(self, other_user):
        """Is this user followed by `other_user`?"""
        return any(u.id == other_user.id for u in self.followers)

    def is_following(self, other_user):
        """Is this user following `other_user`?"""
        return any(u.id == other_user.id for u in self.following)

    @classmethod
    def signup(cls, username, email, password, image_url=None):
        """Sign up user. Hashes password and adds user to system."""
        hashed_pwd = bcrypt.generate_password_hash(password).decode("UTF-8")
        user = cls(
            username=username,
            email=email,
            password=hashed_pwd,
            image_url=image_url or "/static/images/default-pic.png",
        )
        db.session.add(user)
        return user

    @classmethod
    def authenticate(cls, username, password):
        """Find user with `username`/`password`. Return user or False."""
        user = cls.query.filter_by(username=username).first()
        if user and bcrypt.check_password_hash(user.password, password):
            return user
        return False


class Message(db.Model):
    """An individual message ("warble")."""

    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)

    text = db.Column(db.String(140), nullable=False)

    # Use callable, not evaluated at import time
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Inverse of User.messages
    user = db.relationship("User", back_populates="messages")

    # Users who liked this message
    likers = db.relationship(
        "User",
        secondary="likes",
        back_populates="likes",
        lazy="selectin",
        passive_deletes=True,
    )


def connect_db(app):
    """Connect this database to provided Flask app."""
    db.app = app
    db.init_app(app)
