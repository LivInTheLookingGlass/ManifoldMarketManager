from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from inspect import signature
from json import dump, load
from re import match
from typing import TYPE_CHECKING

from src.application import register_db
from src.market import Market
from src.rule import get_rule
from src.util import explain_abstract, get_client

from pymanifold.types import DictDeserializable

if TYPE_CHECKING:  # pragma: no cover
    from typing import Any, Literal, Mapping, Optional

    from src import Rule
    from src.rule import ResolutionValueRule


def main():
    with open('example.json', 'r') as f:
        obj: list = load(f, object_hook=date_deserialization_hook)
    db = register_db()
    try:
        for mkt in obj.copy():
            my_mkt = CreationRequest.from_dict(mkt).create()
            db.execute("INSERT INTO markets VALUES ( (SELECT MAX(id)+1 from markets), ?, 3, NULL);", (my_mkt, ))
            ((new_id, ), ) = db.execute("SELECT MAX(id) from markets;")
            print(f"Added as ID {new_id}")
            print(my_mkt.market.url)
            obj.remove(mkt)
    finally:
        db.commit()
        db.close()
        with open('example.json', 'w') as f:
            dump(obj, f, default=date_serialization_hook, indent="\t")


def date_serialization_hook(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type ${type(obj)} not serializable")


def date_deserialization_hook(json_dict):
    """JSON deserializer for datetime objects."""
    for key, value in json_dict.items():
        if isinstance(value, str):
            if match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', value):
                json_dict[key] = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            elif match(r'^\d{4}-\d{2}-\d{2}$', value):
                json_dict[key] = datetime.strptime(value, "%Y-%m-%d")

    return json_dict


@dataclass
class ManifoldRequest(DictDeserializable):
    outcomeType: Literal["BINARY", "PSEUDO_NUMERIC", "FREE_RESPONSE", "MULTIPLE_CHOICE"]
    question: str
    description: str | Any
    closeTime: int

    initialProb: Optional[float] = None  # Note: probability is multiplied by 100, may only allow integers

    minValue: Optional[float] = None
    maxValue: Optional[float] = None
    isLogScale: Optional[bool] = None
    initialValue: Optional[float] = None
    tags: list[str] = field(default_factory=list)
    answers: Optional[list[str]] = None

    def __post_init__(self):
        if isinstance(self.closeTime, datetime):
            self.closeTime = round(self.closeTime.timestamp() * 1000)

        if self.outcomeType == "BINARY":
            self._validate_binary()
        elif self.outcomeType == "PSEUDO_NUMERIC":
            self.validate_pseudo_numeric()
        elif self.outcomeType == "MULTIPLE_CHOICE":
            self._validate_multiple_choice()

    def _validate_binary(self) -> None:
        if self.initialProb is None:
            raise ValueError("Missing initial probability")

    def _validate_pseudo_numeric(self) -> None:
        if None in (self.minValue, self.maxValue, self.isLogScale, self.initialValue):
            raise ValueError("Need a minValue, maxValue, isLogScale, and initialValue")

    def _validate_multiple_choice(self) -> None:
        if self.answers is None or len(self.answers) < 2 or any(len(x) < 1 for x in self.answers):
            raise ValueError("Invalid answers list")

    def to_dict(self) -> dict[str, Any]:
        return {
            k: v for k, v in self.__dict__.items()
            if k in signature(type(self)).parameters and v is not None and k != "outcomeType"
        }


@dataclass
class CreationRequest:
    manifold: ManifoldRequest
    time_rules: list[Rule[Optional[bool]]]
    value_rules: list[ResolutionValueRule]
    notes: str = ""
    initial_values: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if not self.manifold.description.get("processed"):
            explanation = "\n" + explain_abstract(
                time_rules=self.time_rules, value_rules=self.value_rules
            )
            for paragraph in explanation.splitlines():
                # if paragraph:
                s_par = paragraph.lstrip()
                self.manifold.description["content"].append({
                    "type": "paragraph",
                    "content": [{
                        "type": "text",
                        "text": "-" * (len(paragraph) - len(s_par)) + s_par
                    }]
                })
                # else:
                #     self.manifold.description["content"].append({"type": "paragraph"})
            self.manifold.description["processed"] = True

    @classmethod
    def from_dict(cls, obj: Mapping[str, Any]) -> 'CreationRequest':
        """Take a dictionary and return an instance of the associated class."""
        obj = dict(obj)
        manifold = ManifoldRequest.from_dict(obj.pop('manifold'))
        time_rules = [
            get_rule(type_).from_dict(kwargs)
            for type_, kwargs in obj.pop('time_rules')
        ]
        value_rules = [
            get_rule(type_).from_dict(kwargs)
            for type_, kwargs in obj.pop('value_rules')
        ]
        return cls(
            manifold=manifold,
            time_rules=time_rules,
            value_rules=value_rules,
            **obj
        )

    def create(self):
        """Create a market, given its request object."""
        client = get_client()
        if self.manifold.outcomeType == "FREE_RESPONSE":  # requires extra actions
            market = client.create_free_response_market(**self.manifold.to_dict())
            for answer, weight in self.initial_values.items():
                client.create_bet(market.id, weight, answer)

        elif self.manifold.outcomeType in ("BINARY", "PSEUDO_NUMERIC", "MULTIPLE_CHOICE"):  # simple markets
            func = {
                "BINARY": client.create_binary_market,
                "PSEUDO_NUMERIC": client.create_numeric_market,
                "MULTIPLE_CHOICE": client.create_multiple_choice_market
            }[self.manifold.outcomeType]
            market = func(**self.manifold.to_dict())

        else:
            raise ValueError()

        return Market(
            client.get_market_by_id(market.id),
            do_resolve_rules=self.time_rules,
            resolve_to_rules=self.value_rules,
            notes=self.notes
        )


if __name__ == '__main__':
    main()
