"""Contains information needed to manage accounts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pickle import dumps, loads
from typing import cast

from cryptography.fernet import Fernet


@dataclass
class Account:
    """Represent a Manifold account and its related API access keys."""

    # Section: Manifold
    ManifoldUsername: str
    ManifoldToken: str

    # Section: GitHub
    GithubUsername: str
    GithubToken: str

    # Section: Telegram
    TelegramAPIKey: str
    TelegramChatID: str

    # Internals section
    key: bytes = field(default_factory=Fernet.generate_key)

    def to_bytes(self) -> bytes:
        """Generate encrypted bytes to represent this account."""
        return Fernet(self.key).encrypt(dumps(self))

    @staticmethod
    def from_bytes(buff: bytes, key: bytes) -> 'Account':
        """Decrypt and deserialize an Account from an encrypted bytestring."""
        return cast(Account, loads(Fernet(key).decrypt(buff)))
