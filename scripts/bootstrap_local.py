"""Create local development settings once; never replace keys or a database."""
from pathlib import Path
import base64
import secrets

settings = Path(__file__).resolve().parents[1] / "regulai/regulai/local_settings.py"
try:
    with settings.open("x", encoding="utf-8") as output:
        output.write(
            "# Local development only. Preserve this file and its encryption key.\n"
            f"SECRET_KEY = {secrets.token_urlsafe(48)!r}\n"
            f"ENCRYPTION_KEY = {base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()!r}\n"
            "DEBUG = True\n"
            "ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']\n"
            "ALLOW_REGISTRATION = False\n"
            "from pathlib import Path\n"
            "DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', "
            "'NAME': Path(__file__).resolve().parent.parent / 'community-local.sqlite3'}}\n"
        )
    print("Created local settings with new development keys (not displayed).")
except FileExistsError:
    print("Existing local settings preserved.")
