"""Store constants, shared values, and enumerations."""

from __future__ import annotations

from enum import Enum, IntEnum, auto, unique
from typing import TYPE_CHECKING, Literal, Mapping, TypeVar, Union

if TYPE_CHECKING:  # pragma: no cover
    from typing import Sequence


# type aliases for resolution values
BinaryResolution = Union[Literal["CANCEL"], bool, float]
PseudoNumericResolution = Union[Literal["CANCEL"], float]
FreeResponseResolution = Union[Literal["CANCEL"], Mapping[str, float], Mapping[int, float], Mapping[float, float]]
MultipleChoiceResolution = FreeResponseResolution
AnyResolution = Union[BinaryResolution, PseudoNumericResolution, FreeResponseResolution, MultipleChoiceResolution]
T = TypeVar("T", bound=Union[None, AnyResolution])

# constants, and associated enums
AVAILABLE_RULES = [
    "generic.NegateRule",
    "generic.EitherRule",
    "generic.BothRule",
    "generic.NANDRule",
    "generic.NeitherRule",
    "generic.XORRule",
    "generic.XNORRule",
    "generic.ImpliesRule",
    "generic.ConditionalRule",
    "generic.ResolveAtTime",
    "generic.ResolveToValue",
    "generic.AdditiveRule",
    "generic.MultiplicitiveRule",
    "generic.ModulusRule",
    "generic.ResolveRandomSeed",
    "generic.ResolveRandomIndex",
    "generic.ResolveMultipleValues",
    "github.ResolveWithPR",
    "github.ResolveToPR",
    "github.ResolveToPRDelta",
    "manifold.this.CurrentValueRule",
    "manifold.this.FibonacciValueRule",
    "manifold.this.PopularValueRule",
    "manifold.this.ThisMarketClosed",
    "manifold.other.AmplifiedOddsRule",
    "manifold.other.OtherMarketClosed",
    "manifold.other.OtherMarketResolved",
    "manifold.other.OtherMarketValue",
    "manifold.user.ResolveToUserProfit",
    "manifold.user.ResolveToUserCreatedVolume"
]


class EnvironmentVariable(str, Enum):
    """Represents an Environment Variable that is used by this program."""

    ManifoldAPIKey = "ManifoldAPIKey"        # REQUIRED. Allows trades, market creation, market resolution
    GithubUsername = "GithubUsername"        # Optional. Allows you have a higher rate limit, make authorized requests
    GithubAccessToken = "GithubAccessToken"  # Optional. See above
    DBName = "DBName"                        # REQUIRED. The name of the database you wish to use
    TelegramAPIKey = "TelegramAPIKey"        # Optional. Run --console-only if you don't want to use a Telegram channel
    TelegramChatID = "TelegramChatID"        # Optional. See above
    LogFile = "LogFile"                      # REQUIRED. What file to put the log in


class MarketStatus(Enum):
    """Represent the status of a market at a high level."""

    OPEN = auto()
    CLOSED = auto()
    RESOLVED = auto()


@unique
class Outcome(str, Enum):  # officially supported in python3.11+
    """Represent possible outcomes of markets, and exposing groups of related types."""

    BINARY = 'BINARY'
    FREE_RESPONSE = 'FREE_RESPONSE'
    PSEUDO_NUMERIC = 'PSEUDO_NUMERIC'
    MULTIPLE_CHOICE = 'MULTIPLE_CHOICE'

    @staticmethod
    def BINARY_LIKE() -> Sequence[OutcomeType]:
        """Return the group of markets that resolves using the binary market API."""
        return (Outcome.BINARY, Outcome.PSEUDO_NUMERIC)

    @staticmethod
    def MC_LIKE() -> Sequence[OutcomeType]:
        """Return the group of markets that resolves using the free response market API."""
        return (Outcome.FREE_RESPONSE, Outcome.MULTIPLE_CHOICE)


OutcomeType = Union[Outcome, Literal["BINARY", "FREE_RESPONSE", "PSEUDO_NUMERIC", "MULTIPLE_CHOICE"]]
OUTCOMES: Sequence[OutcomeType] = ("BINARY", "FREE_RESPONSE", "PSEUDO_NUMERIC", "MULTIPLE_CHOICE")

FieldType = Literal["allTime", "daily", "weekly", "monthly"]
FIELDS: Sequence[FieldType] = ("allTime", "daily", "weekly", "monthly")


class Response(IntEnum):
    """Possible responses from the Telegram Bot, other than YES or NO."""

    NO_ACTION = 1
    USE_DEFAULT = 2
    CANCEL = 3
