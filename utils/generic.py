from django.apps import apps as django_apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models import Model


def get_gateway(gateway):
    """
    Returns a PaymentGateway instance for the given gateway name.
    Import is done inside the function to avoid circular imports.
    """
    from airpay.models import PaymentGateway
    try:
        gateway, _ = PaymentGateway.objects.get_or_create(defaults={
            'name': gateway
        })
        return gateway
    except PaymentGateway.DoesNotExist:
        return None


def get_purchase_model() -> Model or None:
    try:
        return django_apps.get_model(settings.AIRPAY.get("PURCHASE_MODEL"), require_ready=False)
    except ValueError:
        raise ImproperlyConfigured(
            "PURCHASE_MODEL must be of the form 'app_label.model_name'"
        )

    except LookupError:
        raise ImproperlyConfigured(
            "PURCHASE_MODEL refers to model '%s' that has not been installed"
            % settings.AIRPAY.get("PURCHASE_MODEL")
        )

def get_base_model():
    """
    Returns the base model class as defined in settings.py under AIRPAY['BASE_MODEL'].
    Since this is typically an abstract model, we import it directly rather than using get_model().

    Expected format: 'module.path.ClassName' (e.g., 'helpers.models.BaseModel')
    """
    model_path = getattr(settings, "AIRPAY", {}).get("BASE_MODEL", None)
    if not model_path:
        raise ImproperlyConfigured("BASE_MODEL must be set in AIRPAY settings")

    try:
        # Split into module path and class name
        parts = model_path.split('.')
        if len(parts) < 2:
            raise ValueError("Invalid format")

        class_name = parts[-1]
        module_path = '.'.join(parts[:-1])

        # Import the module
        import importlib
        module = importlib.import_module(module_path)

        # Get the class from the module
        base_model = getattr(module, class_name)

        # Verify it's a model class
        if not issubclass(base_model, models.Model):
            raise ImproperlyConfigured(
                f"BASE_MODEL '{model_path}' must be a subclass of django.db.models.Model"
            )

        return base_model

    except (ValueError, AttributeError, ImportError) as e:
        raise ImproperlyConfigured(
            f"BASE_MODEL '{model_path}' could not be imported. "
            f"Expected format: 'module.path.ClassName' (e.g., 'helpers.models.BaseModel'). "
            f"Error: {str(e)}"
        )

class Wrapper:
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

def get_cache_middleware() -> type:
    """
    Returns the cache middleware class from settings.
    Defaults to django.middleware.cache.CacheMiddleware if not specified.
    """
    middle_ware_path =  getattr(settings, "AIRPAY", {}).get("CACHE_MIDDLEWARE")
    if not middle_ware_path:
        return Wrapper

    try:
        parts = middle_ware_path.split('.')
        if len(parts) < 2:
            raise ValueError("Invalid format")
        class_name = parts[-1]
        module_path = '.'.join(parts[:-1])
        import importlib
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ValueError, AttributeError, ImportError) as e:
        raise ImproperlyConfigured(
            f"CACHE_MIDDLEWARE '{middle_ware_path}' could not be imported. "
            f"Expected format: 'module.path.ClassName' (e.g., 'django.middleware.cache.CacheMiddleware'). "
            f"Error: {str(e)}"
        )


def get_create_date_field() -> str:
    """
    Returns the name of the creation date field from AIRPAY settings.
    Defaults to 'create_date' if not specified.
    """
    return getattr(settings, "AIRPAY", {}).get("CREATE_DATE_FIELD", "create_date")


def get_update_date_field() -> str:
    """
    Returns the name of the update date field from AIRPAY settings.
    Defaults to 'update_date' if not specified.
    """
    return getattr(settings, "AIRPAY", {}).get("UPDATE_DATE_FIELD", "update_date")

def get_app_name() -> str:
    """
    Returns the name of the app from settings.py.
    Defaults to 'airpay' if not specified.
    """
    return getattr(settings, "AIRPAY", {}).get("APP_NAME", "Airpay")
