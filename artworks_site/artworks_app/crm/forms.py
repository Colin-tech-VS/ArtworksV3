from flask_wtf import FlaskForm
from wtforms import (BooleanField, IntegerField, SelectField, SelectMultipleField,
                     StringField, SubmitField, TextAreaField)
from wtforms.validators import DataRequired, Length, Optional, Regexp


class CmsPageForm(FlaskForm):
    title = StringField('Titre', validators=[DataRequired(), Length(max=200)])
    slug = StringField('Slug URL', validators=[
        DataRequired(), Length(max=120),
        Regexp(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', message='Slug : minuscules, chiffres et tirets uniquement.'),
    ])
    excerpt = StringField('Extrait', validators=[Optional(), Length(max=500)])
    body = TextAreaField('Contenu (HTML autorisé)')
    meta_title = StringField('Meta titre SEO', validators=[Optional(), Length(max=200)])
    meta_description = StringField('Meta description', validators=[Optional(), Length(max=320)])
    published = BooleanField('Publiée')
    show_in_nav = BooleanField('Afficher dans le menu')
    submit = SubmitField('Enregistrer')


class SegmentForm(FlaskForm):
    name = StringField('Nom du segment', validators=[DataRequired(), Length(max=120)])
    description = TextAreaField('Description', validators=[Optional()])
    role = SelectField('Rôle', choices=[
        ('all', 'Tous les rôles'),
        ('artiste', 'Artistes'),
        ('galerie', 'Galeries'),
        ('collectionneur', 'Collectionneurs'),
    ])
    plan = SelectField('Formule', choices=[
        ('all', 'Toutes les formules'),
        ('free', 'Compte / Découverte'),
        ('portfolio', 'Portfolio Marketplace'),
        ('essentiel', 'Essentiel (legacy)'),
        ('pro', 'Pro'),
        ('galerie_pro', 'Galerie Pro'),
        ('premium', 'Premium'),
        ('membre', 'Membre'),
        ('patron', 'Patron'),
    ])
    subscription_status = SelectField('Statut abonnement', choices=[
        ('all', 'Tous'),
        ('active', 'Actif'),
        ('cancelled', 'Annulé'),
        ('past_due', 'Impayé'),
        ('expired', 'Expiré'),
    ])
    paid_only = BooleanField('Abonnés payants uniquement')
    min_artworks = IntegerField('Minimum d\'œuvres publiées', validators=[Optional()])
    has_stripe = BooleanField('Client Stripe enregistré')
    submit = SubmitField('Enregistrer le segment')


class CampaignForm(FlaskForm):
    name = StringField('Nom interne', validators=[DataRequired(), Length(max=160)])
    subject = StringField('Objet', validators=[DataRequired(), Length(max=200)])
    preview_text = StringField('Aperçu (preheader)', validators=[Optional(), Length(max=200)])
    recipient_mode = SelectField('Destinataires', choices=[
        ('segment', 'Segment existant'),
        ('role', 'Groupe par rôle'),
        ('users', 'Utilisateurs sélectionnés'),
    ])
    segment_id = SelectField('Segment', coerce=int, validators=[Optional()])
    recipient_role = SelectField('Groupe', choices=[
        ('artiste', 'Artistes'),
        ('galerie', 'Galeries'),
        ('collectionneur', 'Collectionneurs'),
    ], validators=[Optional()])
    recipient_user_ids = SelectMultipleField('Utilisateurs', coerce=int, validators=[Optional()])
    body_html = TextAreaField('Corps HTML', validators=[DataRequired()])
    body_text = TextAreaField('Version texte (optionnel)', validators=[Optional()])
    submit = SubmitField('Enregistrer et prévisualiser')


class EmailTemplateForm(FlaskForm):
    name = StringField('Nom', validators=[DataRequired(), Length(max=160)])
    subject = StringField('Objet', validators=[DataRequired(), Length(max=200)])
    preview_text = StringField('Aperçu (preheader)', validators=[Optional(), Length(max=200)])
    body_html = TextAreaField('Corps HTML', validators=[DataRequired()])
    active = BooleanField('Actif')
    auto_send = BooleanField('Envoi automatique (transactionnel)')
    submit = SubmitField('Enregistrer')


class EmailAiForm(FlaskForm):
    ai_brief = TextAreaField('Brief email', validators=[DataRequired(), Length(min=5, max=2000)])
    ai_tone = SelectField('Ton', choices=[
        ('editorial', 'Éditorial'),
        ('conversion', 'Conversion & CTA'),
        ('warm', 'Chaleureux & accueil'),
    ])
    submit = SubmitField('Générer avec Mistral')


class SocialAiForm(FlaskForm):
    ai_subject = StringField('Sujet du post', validators=[DataRequired(), Length(min=3, max=300)])
    ai_keywords = StringField('Mots-clés', validators=[Optional(), Length(max=300)])
    ai_tone = SelectField('Ton', choices=[
        ('inspirant', 'Inspirant'),
        ('editorial', 'Éditorial'),
        ('conversion', 'Conversion & CTA'),
        ('chaleureux', 'Chaleureux'),
    ])
    ai_language = SelectField('Langue', choices=[('fr', 'Français'), ('en', 'English')])
    submit = SubmitField('Générer avec Mistral')


class SocialPostForm(FlaskForm):
    name = StringField('Nom interne', validators=[DataRequired(), Length(max=160)])
    subject = StringField('Sujet', validators=[DataRequired(), Length(max=300)])
    keywords = StringField('Mots-clés', validators=[Optional(), Length(max=300)])
    tone = SelectField('Ton', choices=[
        ('inspirant', 'Inspirant'),
        ('editorial', 'Éditorial'),
        ('conversion', 'Conversion'),
    ])
    destination_url = StringField('Lien destination (optionnel)', validators=[Optional(), Length(max=512)])
    target_mode = SelectField('Clients mis en avant', choices=[
        ('segment', 'Segment'),
        ('role', 'Type de client'),
        ('users', 'Client(s) spécifique(s)'),
    ])
    segment_id = SelectField('Segment', coerce=int, validators=[Optional()])
    target_role = SelectField('Type', choices=[('artiste', 'Artistes'), ('galerie', 'Galeries')])
    target_user_ids = SelectMultipleField('Clients', coerce=int, validators=[Optional()])
    platform_facebook = BooleanField('Facebook')
    platform_instagram = BooleanField('Instagram')
    platform_pinterest = BooleanField('Pinterest')
    platform_deviantart = BooleanField('DeviantArt')
    facebook_text = TextAreaField('Texte Facebook', validators=[Optional()])
    instagram_text = TextAreaField('Caption Instagram', validators=[Optional()])
    pinterest_text = TextAreaField('Description Pinterest', validators=[Optional()])
    deviantart_title = StringField('Titre DeviantArt', validators=[Optional(), Length(max=100)])
    deviantart_description = TextAreaField('Description DeviantArt', validators=[Optional()])
    submit = SubmitField('Enregistrer')
    submit_publish = SubmitField('Publier maintenant')


class UserAdminForm(FlaskForm):
    display_name = StringField('Nom affiché', validators=[Optional(), Length(max=120)])
    email = StringField('Email', validators=[DataRequired(), Length(max=120)])
    role = SelectField('Rôle', choices=[
        ('artiste', 'Artiste'),
        ('galerie', 'Galerie'),
        ('collectionneur', 'Collectionneur'),
        ('admin', 'Administrateur CRM'),
    ])
    subscription_plan = SelectField('Formule', choices=[
        ('free', 'Compte / Découverte'),
        ('portfolio', 'Portfolio Marketplace'),
        ('essentiel', 'Essentiel (legacy)'),
        ('pro', 'Pro'),
        ('galerie_pro', 'Galerie Pro'),
        ('premium', 'Premium'),
        ('membre', 'Membre'),
        ('patron', 'Patron'),
    ])
    subscription_status = SelectField('Statut abo', choices=[
        ('active', 'Actif'),
        ('cancelled', 'Annulé'),
        ('past_due', 'Impayé'),
        ('expired', 'Expiré'),
    ])
    is_staff = BooleanField('Accès CRM (admin)')
    submit = SubmitField('Mettre à jour')


class CmsPageAiForm(FlaskForm):
    ai_topic = TextAreaField('Brief SEO / sujet de la page', validators=[DataRequired(), Length(min=5, max=2000)])
    ai_keywords = StringField('Mots-clés cibles', validators=[Optional(), Length(max=300)])
    ai_tone = SelectField('Ton', choices=[
        ('expert', 'Expert & crédible'),
        ('editorial', 'Éditorial magazine'),
        ('conversion', 'Conversion & CTA'),
    ])
    submit = SubmitField('Générer avec Mistral')
