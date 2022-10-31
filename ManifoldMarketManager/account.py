"""Contains information needed to manage accounts."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from os import getenv
from pickle import dumps, loads
from typing import cast

from cryptography.fernet import Fernet

prop_to_env = {
    "ManifoldToken": "ManifoldAPIKey",
    "GithubToken": "GithubAccessToken",
}


@dataclass
class Account:
    """Represent a Manifold account and its related API access keys."""

    # Section: Manifold
    ManifoldToken: str
    ManifoldUsername: str = ''

    # Section: GitHub
    GithubUsername: str = ''
    GithubToken: str = ''

    # Section: Telegram
    TelegramAPIKey: str = ''
    TelegramChatID: str = ''

    # Internals section
    key: bytes = field(default_factory=Fernet.generate_key, compare=False, repr=False)

    def to_bytes(self) -> bytes:
        """Generate encrypted bytes to represent this account."""
        return Fernet(self.key).encrypt(dumps(self))

    @staticmethod
    def from_bytes(buff: bytes, key: bytes) -> 'Account':
        """Decrypt and deserialize an Account from an encrypted bytestring."""
        return cast(Account, loads(Fernet(key).decrypt(buff)))

    @staticmethod
    def from_env() -> 'Account':
        """Try to infer an account from environment variables."""
        kwargs = {}
        for f in fields(Account):
            if f.init:
                value = getenv(prop_to_env.get(f.name, f.name), None)
                if value is not None:
                    kwargs[f.name] = value
        return Account(key=Fernet.generate_key(), **kwargs)
