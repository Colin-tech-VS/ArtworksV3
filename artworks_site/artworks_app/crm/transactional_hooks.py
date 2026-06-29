
def notify_subscription_email(user, event: str) -> None:
    """Envoie un email transactionnel après changement d'abonnement."""
    slug_map = {
        'activated': 'subscription_activated',
        'cancelled': 'subscription_cancelled',
        'past_due': 'subscription_past_due',
    }
    slug = slug_map.get(event)
    if not slug:
        return
    try:
        from .email_templates_seed import ensure_default_email_templates
        from .email_service import send_transactional
        from .auto_segments import classify_user

        ensure_default_email_templates()
        classify_user(user)
        send_transactional(slug, user)
    except Exception:
        pass
