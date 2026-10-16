"""Test ortak yardımcıları."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class FakeKeyring:
    """Bellek içi sahte keyring (Windows Credential Manager taklidi)."""

    def __init__(self):
        self.store: dict[tuple[str, str], str] = {}

    def set_password(self, service, key, value):
        self.store[(service, key)] = value

    def get_password(self, service, key):
        return self.store.get((service, key))

    def delete_password(self, service, key):
        if (service, key) not in self.store:
            import keyring.errors

            raise keyring.errors.PasswordDeleteError("olmayan kayıt")
        self.store.pop((service, key))


@pytest.fixture()
def fake_keyring():
    from evren_studio import secrets

    fake = FakeKeyring()
    secrets._set_backend(fake)
    yield fake
    secrets._set_backend(None)
