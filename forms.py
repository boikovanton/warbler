from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, Optional, URL, ValidationError

def url_or_root_path(form, field):
    """Allow empty, absolute http(s) URL, or app-relative path starting with '/'."""
    data = (field.data or "").strip()
    if not data:
        return  # Optional ok
    if data.startswith("/"):
        return  # accept /static/... etc
    # otherwise must be a valid absolute URL
    try:
        URL(require_tld=False, schemes=["http", "https"])(form, field)
    except Exception:
        raise ValidationError("Must be a valid URL (http/https) or a path starting with '/'.")

class MessageForm(FlaskForm):
    text = TextAreaField('Message', validators=[DataRequired()])

class UserAddForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[Length(min=6)])
    image_url = StringField('(Optional) Image URL', validators=[Optional(), url_or_root_path])

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[Length(min=6)])

class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(max=50)])
    email = StringField('E-mail', validators=[DataRequired(), Email(), Length(max=120)])
    image_url = StringField('Profile Image URL', validators=[Optional(), url_or_root_path])
    header_image_url = StringField('Header Image URL', validators=[Optional(), url_or_root_path])
    location = StringField('Location', validators=[Optional(), Length(max=100)])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=500)])
    password = PasswordField('Current Password', validators=[DataRequired()])
