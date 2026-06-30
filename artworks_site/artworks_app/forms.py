from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, SubmitField, TextAreaField,
                     DecimalField, RadioField, SelectField, HiddenField)
from wtforms.validators import (DataRequired, Email, EqualTo, Length, Optional,
                                ValidationError, Regexp)
from flask_wtf.file import FileField, FileAllowed
from .catalog import select_choices

IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
IMAGE_FILE_MSG = 'Formats acceptés : JPG, PNG, GIF, WebP.'


def _unique_username(form, field):
    from .models import User
    name = (field.data or '').strip()
    if User.query.filter_by(username=name).first():
        raise ValidationError('Ce nom d\'utilisateur est déjà pris.')


def _unique_email(form, field):
    from .models import User
    email = (field.data or '').strip().lower()
    if User.query.filter_by(email=email).first():
        raise ValidationError('Cet email est déjà utilisé.')


def _valid_plan_for_role(form, field):
    from .subscriptions import normalize_plan, role_plans_catalog
    role = form.role.data or 'collectionneur'
    slug = normalize_plan(role, (field.data or 'free').strip())
    catalog = role_plans_catalog().get(role, {})
    if slug not in catalog:
        raise ValidationError('Choisissez une formule valide pour ce profil.')


class RegistrationForm(FlaskForm):
    role = RadioField('Vous êtes', choices=[
        ('collectionneur', 'Collectionneur'),
        ('galerie', 'Galerie'),
        ('artiste', 'Artiste'),
    ], default='collectionneur', validators=[DataRequired(message='Choisissez un type de profil.')])
    plan = StringField('Formule', default='free', validators=[
        DataRequired(message='Choisissez une formule.'),
        _valid_plan_for_role,
    ])
    username = StringField('Username', validators=[
        DataRequired(message='Nom d\'utilisateur requis.'),
        Length(min=3, max=64, message='Entre 3 et 64 caractères.'),
        Regexp(r'^[\w\-.\s]+$', message='Lettres, chiffres, espaces, tirets et points uniquement.'),
        _unique_username,
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Email requis.'),
        Email(message='Adresse email invalide.'),
        Length(max=120),
        _unique_email,
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Mot de passe requis.'),
        Length(min=6, message='Au moins 6 caractères.'),
    ])
    password2 = PasswordField('Repeat Password', validators=[
        DataRequired(message='Confirmez le mot de passe.'),
        EqualTo('password', message='Les mots de passe ne correspondent pas.'),
    ])
    submit = SubmitField('Register')


class LoginForm(FlaskForm):
    username = StringField('Identifiant', validators=[
        DataRequired(message='Nom d\'utilisateur ou email requis.'),
    ])
    password = PasswordField('Mot de passe', validators=[
        DataRequired(message='Mot de passe requis.'),
    ])
    submit = SubmitField('Se connecter')


class ArtworkForm(FlaskForm):
    title = StringField('Titre', validators=[DataRequired(), Length(max=140)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=2000)])
    price = DecimalField('Prix (€)', validators=[Optional()])
    discipline = SelectField('Discipline', choices=[], validators=[Optional()])
    medium = StringField('Technique', validators=[Optional(), Length(max=64)])
    dimensions = StringField('Dimensions', validators=[Optional(), Length(max=80)])
    format = SelectField('Format', choices=[
        ('', '— Format —'),
        ('portrait', 'Portrait'),
        ('paysage', 'Paysage'),
        ('carre', 'Carré'),
        ('panoramique', 'Panoramique'),
    ], validators=[Optional()])
    year = StringField('Année', validators=[Optional(), Length(max=8)])
    series_id = SelectField('Série', coerce=int, choices=[], validators=[Optional()])
    image = FileField('Image', validators=[FileAllowed(IMAGE_EXTENSIONS, IMAGE_FILE_MSG)])
    submit = SubmitField('Publier')


class SeriesForm(FlaskForm):
    name = StringField('Nom de la série', validators=[DataRequired(), Length(max=140)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=2000)])
    year = StringField('Année', validators=[Optional(), Length(max=8)])
    cover = FileField('Image de couverture',
                      validators=[FileAllowed(IMAGE_EXTENSIONS, IMAGE_FILE_MSG)])
    submit = SubmitField('Enregistrer')


class ProfileForm(FlaskForm):
    display_name = StringField('Nom affiché', validators=[Optional(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    discipline = SelectField('Discipline', choices=[], validators=[Optional(), Length(max=120)])
    location = StringField('Localisation', validators=[Optional(), Length(max=120)])
    gallery = StringField('Galerie / Studio', validators=[Optional(), Length(max=120)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=2000)])
    statement = TextAreaField('Statement', validators=[Optional(), Length(max=4000)])
    bio = TextAreaField('Biographie', validators=[Optional(), Length(max=4000)])
    avatar = FileField('Photo de profil',
                       validators=[FileAllowed(IMAGE_EXTENSIONS, IMAGE_FILE_MSG)])
    logo = FileField('Logo',
                     validators=[FileAllowed(IMAGE_EXTENSIONS + ['svg'], IMAGE_FILE_MSG)])
    cover = FileField('Bannière',
                      validators=[FileAllowed(IMAGE_EXTENSIONS, IMAGE_FILE_MSG)])
    submit = SubmitField('Enregistrer')


class PasswordForm(FlaskForm):
    current_password = PasswordField('Mot de passe actuel', validators=[DataRequired()])
    password = PasswordField('Nouveau mot de passe', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirmer', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Modifier le mot de passe')


