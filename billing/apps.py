from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'billing'
    verbose_name = '유료화/결제'

    def ready(self):
        import billing.signals  # noqa: F401
