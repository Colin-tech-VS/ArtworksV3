from . import db, login
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=True)
    google_sub = db.Column(db.String(64), unique=True, nullable=True, index=True)
    role = db.Column(db.String(20), default='collectionneur')  # collectionneur / galerie / artiste / admin

    # --- Artist profile ---
    display_name = db.Column(db.String(120), nullable=True)
    discipline = db.Column(db.String(120), nullable=True)
    location = db.Column(db.String(120), nullable=True)
    gallery = db.Column(db.String(120), nullable=True)
    statement = db.Column(db.Text, nullable=True)
    bio = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    curatorial_note = db.Column(db.Text, nullable=True)
    curatorial_note_at = db.Column(db.DateTime, nullable=True)
    avatar = db.Column(db.String(256), nullable=True)
    cover = db.Column(db.String(256), nullable=True)
    logo = db.Column(db.String(256), nullable=True)
    since = db.Column(db.Integer, nullable=True)
    followers = db.Column(db.Integer, default=0)
    expos = db.Column(db.Integer, default=0)

    # --- Subscription ---
    subscription_plan = db.Column(db.String(32), default='free')
    subscription_status = db.Column(db.String(20), default='active')  # active / cancelled / expired / past_due
    subscription_since = db.Column(db.DateTime, nullable=True)
    subscription_period_end = db.Column(db.DateTime, nullable=True)
    stripe_customer_id = db.Column(db.String(64), nullable=True)
    stripe_subscription_id = db.Column(db.String(64), nullable=True)
    stripe_connect_id = db.Column(db.String(64), nullable=True)
    stripe_connect_charges_enabled = db.Column(db.Boolean, default=False)
    stripe_connect_payouts_enabled = db.Column(db.Boolean, default=False)
    stripe_connected_at = db.Column(db.DateTime, nullable=True)

    # --- Quotas & collectionneur ---
    curatorial_quota_month = db.Column(db.String(7), nullable=True)  # YYYY-MM
    curatorial_quota_used = db.Column(db.Integer, default=0)
    wishlist_share_token = db.Column(db.String(32), nullable=True, unique=True)
    is_staff = db.Column(db.Boolean, default=False)

    artworks = db.relationship('Artwork', backref='owner', lazy=True)
    series = db.relationship('Series', backref='owner', lazy=True,
                             cascade='all, delete-orphan')
    gallery_artists = db.relationship('GalleryArtist', backref='gallery', lazy=True,
                                      cascade='all, delete-orphan',
                                      foreign_keys='GalleryArtist.gallery_id')
    price_alerts = db.relationship('PriceAlert', backref='user', lazy=True,
                                   cascade='all, delete-orphan')

    @property
    def name(self):
        return self.display_name or self.username

    @property
    def is_admin(self):
        return self.role == 'admin' or bool(self.is_staff)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def uses_google_auth(self) -> bool:
        return bool(self.google_sub)


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class Series(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=True)
    cover = db.Column(db.String(256), nullable=True)
    year = db.Column(db.Integer, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    artworks = db.relationship('Artwork', backref='series', lazy=True)


class Artwork(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=True)
    image = db.Column(db.String(256), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    series_id = db.Column(db.Integer, db.ForeignKey('series.id'), nullable=True)

    # --- Cartel / metadata ---
    year = db.Column(db.Integer, nullable=True)
    discipline = db.Column(db.String(64), nullable=True)
    style = db.Column(db.String(64), nullable=True)
    medium = db.Column(db.String(64), nullable=True)
    technique = db.Column(db.String(160), nullable=True)
    dimensions = db.Column(db.String(80), nullable=True)
    format = db.Column(db.String(32), nullable=True)         # portrait / paysage / carré / panoramique
    size = db.Column(db.String(16), nullable=True)
    color = db.Column(db.String(16), nullable=True)
    status = db.Column(db.String(16), default='dispo')
    signed = db.Column(db.Boolean, default=True)
    certificate = db.Column(db.Boolean, default=True)
    condition = db.Column(db.String(120), nullable=True)
    framing = db.Column(db.String(160), nullable=True)
    created_at = db.Column(db.DateTime, nullable=True)
    view_count = db.Column(db.Integer, default=0)
    early_access = db.Column(db.Boolean, default=False)  # réservé ventes privées / avant-première

    category = db.Column(db.String(64), nullable=True)

    # Syndication réseaux sociaux (DeviantArt auto-publish)
    deviantart_deviation_id = db.Column(db.String(64), nullable=True)
    deviantart_url = db.Column(db.String(512), nullable=True)
    deviantart_views = db.Column(db.Integer, default=0)
    deviantart_favorites = db.Column(db.Integer, default=0)
    pinterest_pin_id = db.Column(db.String(64), nullable=True)
    pinterest_saves = db.Column(db.Integer, default=0)
    pinterest_impressions = db.Column(db.Integer, default=0)
    social_published_at = db.Column(db.DateTime, nullable=True)

    @property
    def social_views_cumul(self):
        return (self.view_count or 0) + (self.deviantart_views or 0) + (self.pinterest_impressions or 0)

    @property
    def social_likes_cumul(self):
        return (self.deviantart_favorites or 0) + (self.pinterest_saves or 0)

    @property
    def price_str(self):
        if not self.price:
            return "Prix sur demande"
        return "{:,.0f} €".format(self.price).replace(",", " ")

    @property
    def price_bucket(self):
        p = self.price or 0
        if p < 2000:
            return "p1"
        if p < 4000:
            return "p2"
        if p < 6000:
            return "p3"
        return "p4"

    @property
    def tags(self):
        parts = [self.discipline, self.style, self.medium, self.price_bucket,
                 self.size, self.color, self.status]
        return " ".join(p for p in parts if p)


class GalleryArtist(db.Model):
    """Artistes rattachés à une galerie (formules Pro / Premium)."""
    id = db.Column(db.Integer, primary_key=True)
    gallery_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    discipline = db.Column(db.String(120), nullable=True)
    linked_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=True)


class PriceAlert(db.Model):
    """Alertes prix pour collectionneurs Membre / Patron."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    artwork_id = db.Column(db.Integer, db.ForeignKey('artwork.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=True)
    artwork = db.relationship('Artwork', backref='price_alerts')


class CmsPage(db.Model):
    """Pages éditoriales gérées depuis le CRM."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    excerpt = db.Column(db.String(500), nullable=True)
    body = db.Column(db.Text, nullable=True)
    meta_title = db.Column(db.String(200), nullable=True)
    meta_description = db.Column(db.String(320), nullable=True)
    published = db.Column(db.Boolean, default=False)
    show_in_nav = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    author = db.relationship('User', foreign_keys=[author_id])


class AnalyticsEvent(db.Model):
    """Événements analytics (style GA4)."""
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(32), default='page_view')  # page_view, artwork_view, signup, ...
    path = db.Column(db.String(256), nullable=True)
    page_title = db.Column(db.String(200), nullable=True)
    session_id = db.Column(db.String(32), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    referrer = db.Column(db.String(500), nullable=True)
    source = db.Column(db.String(32), default='direct')  # direct / google / referral / internal
    artwork_id = db.Column(db.Integer, db.ForeignKey('artwork.id'), nullable=True)
    meta_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class EmailSegment(db.Model):
    """Segment d'audience pour campagnes email."""
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_system = db.Column(db.Boolean, default=False)
    # JSON: {role, plan, status, min_artworks, has_subscription, ...}
    filters_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    campaigns = db.relationship('EmailCampaign', backref='segment', lazy=True)
    memberships = db.relationship('UserSegmentMembership', backref='segment', lazy=True)

    @property
    def filters(self):
        try:
            return json.loads(self.filters_json or '{}')
        except (TypeError, ValueError):
            return {}

    @filters.setter
    def filters(self, value):
        self.filters_json = json.dumps(value or {})


class UserSegmentMembership(db.Model):
    """Appartenance utilisateur ↔ segment (classification automatique)."""
    __table_args__ = (db.UniqueConstraint('user_id', 'segment_id', name='uq_user_segment'),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    segment_id = db.Column(db.Integer, db.ForeignKey('email_segment.id'), nullable=False, index=True)
    auto_assigned = db.Column(db.Boolean, default=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('segment_memberships', lazy=True))


class EmailTemplate(db.Model):
    """Modèle d'email (transactionnel ou marketing), éditable CRM / IA."""
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    kind = db.Column(db.String(20), default='transactional')  # transactional / marketing
    subject = db.Column(db.String(200), nullable=False)
    preview_text = db.Column(db.String(200), nullable=True)
    body_html = db.Column(db.Text, nullable=True)
    body_text = db.Column(db.Text, nullable=True)
    active = db.Column(db.Boolean, default=True)
    auto_send = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    author = db.relationship('User', foreign_keys=[author_id])


class EmailCampaign(db.Model):
    """Campagne email marketing (style Brevo)."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    preview_text = db.Column(db.String(200), nullable=True)
    body_html = db.Column(db.Text, nullable=True)
    body_text = db.Column(db.Text, nullable=True)
    segment_id = db.Column(db.Integer, db.ForeignKey('email_segment.id'), nullable=True)
    recipient_mode = db.Column(db.String(20), default='segment')  # segment / role / users
    recipient_role = db.Column(db.String(20), nullable=True)
    recipient_user_ids_json = db.Column(db.Text, default='[]')
    preview_confirmed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='draft')  # draft / sending / sent / failed
    recipient_count = db.Column(db.Integer, default=0)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    author = db.relationship('User', foreign_keys=[author_id])

    @property
    def recipient_user_ids(self):
        try:
            return json.loads(self.recipient_user_ids_json or '[]')
        except (TypeError, ValueError):
            return []

    @recipient_user_ids.setter
    def recipient_user_ids(self, value):
        self.recipient_user_ids_json = json.dumps(list(value or []))


class PlatformSetting(db.Model):
    """Réglages plateforme éditables depuis le CRM (prix, commission…)."""
    key = db.Column(db.String(64), primary_key=True)
    value_json = db.Column(db.Text, nullable=False, default='{}')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])


class SocialToken(db.Model):
    """OAuth tokens DeviantArt / Pinterest (comme V2 social_tokens)."""
    platform = db.Column(db.String(32), primary_key=True)
    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    account_username = db.Column(db.String(120), nullable=True)
    account_id = db.Column(db.String(64), nullable=True)
    scopes = db.Column(db.String(256), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SocialPost(db.Model):
    """Post CRM — publication manuelle ou IA vers FB/IG/Pinterest/DeviantArt."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    subject = db.Column(db.String(300), nullable=False)
    keywords = db.Column(db.String(300), nullable=True)
    tone = db.Column(db.String(32), default='inspirant')
    language = db.Column(db.String(8), default='fr')
    destination_url = db.Column(db.String(512), nullable=True)
    image_url = db.Column(db.String(512), nullable=True)
    facebook_text = db.Column(db.Text, nullable=True)
    instagram_text = db.Column(db.Text, nullable=True)
    pinterest_text = db.Column(db.Text, nullable=True)
    deviantart_title = db.Column(db.String(100), nullable=True)
    deviantart_description = db.Column(db.Text, nullable=True)
    platforms_json = db.Column(db.Text, default='["facebook","instagram"]')
    target_mode = db.Column(db.String(20), default='role')
    segment_id = db.Column(db.Integer, db.ForeignKey('email_segment.id'), nullable=True)
    target_role = db.Column(db.String(20), nullable=True)
    target_user_ids_json = db.Column(db.Text, default='[]')
    status = db.Column(db.String(20), default='draft')
    publish_results_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    published_at = db.Column(db.DateTime, nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    author = db.relationship('User', foreign_keys=[author_id])
    segment = db.relationship('EmailSegment', foreign_keys=[segment_id])

    @property
    def platforms(self):
        try:
            return json.loads(self.platforms_json or '[]')
        except (TypeError, ValueError):
            return []

    @platforms.setter
    def platforms(self, value):
        self.platforms_json = json.dumps(list(value or []))

    @property
    def target_user_ids(self):
        try:
            return json.loads(self.target_user_ids_json or '[]')
        except (TypeError, ValueError):
            return []

    @target_user_ids.setter
    def target_user_ids(self, value):
        self.target_user_ids_json = json.dumps(list(value or []))

    @property
    def publish_results(self):
        try:
            return json.loads(self.publish_results_json or '{}')
        except (TypeError, ValueError):
            return {}


class SocialPublishLog(db.Model):
    """Historique publications (auto œuvre + posts CRM)."""
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(32), nullable=False)
    post_id = db.Column(db.String(128), nullable=True)
    artwork_id = db.Column(db.Integer, db.ForeignKey('artwork.id'), nullable=True)
    social_post_id = db.Column(db.Integer, db.ForeignKey('social_post.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    content_preview = db.Column(db.String(300), nullable=True)
    image_url = db.Column(db.String(512), nullable=True)
    destination_url = db.Column(db.String(512), nullable=True)
    status = db.Column(db.String(20), default='published')
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    artwork = db.relationship('Artwork', foreign_keys=[artwork_id])
    social_post = db.relationship('SocialPost', foreign_keys=[social_post_id])
