from dataclasses import dataclass, field
from datetime import date, datetime
from inspect import signature
from json import dump, load
from re import match
from typing import Any, Dict, List, Literal, Optional, Union

from src import rule
from src.rule import explain_abstract, DoResolveRule, ResolutionValueRule
from src.market import Market, get_client
from example import register_db

from pymanifold.types import DictDeserializable


def main():
    with open('example.json', 'r') as f:
        obj: list = load(f, object_hook=date_deserialization_hook)
    db = register_db()
    try:
        for mkt in obj.copy():
            my_mkt = CreationRequest.from_dict(mkt).create()
            db.execute("INSERT INTO markets VALUES ( (SELECT MAX(id)+1 from markets), ?, 3, NULL);", (my_mkt, ))
            obj.remove(mkt)
    finally:
        db.commit()
        db.close()
        with open('example.json', 'w') as f:
            dump(obj, default=date_serialization_hook)


def date_serialization_hook(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type ${type(obj)} not serializable")


def date_deserialization_hook(json_dict):
    for key, value in json_dict.items():
        if isinstance(value, str):
            if match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d*$', value):
                json_dict[key] = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f")
            elif match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$', value):
                json_dict[key] = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            elif match(r'^\d{4}-\d{2}-\d{2}$', value):
                json_dict[key] = datetime.strptime(value, "%Y-%m-%d")

    return json_dict


@dataclass
class ManifoldRequest(DictDeserializable):
    outcomeType: Literal["BINARY", "PSEUDO_NUMERIC", "FREE_RESPONSE", "MULTIPLE_CHOICE"]
    question: str
    description: Union[str, Any]
    closeTime: int

    initialProb: Optional[float]  # Note: probability is multiplied by 100, may only allow integers in binary market

    minValue: Optional[float]
    maxValue: Optional[float]
    isLogScale: Optional[bool]
    initialValue: Optional[float]
    groups: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.outcomeType == "BINARY":
            if self.initialProb is None:
                raise ValueError("Missing initial probability")

        if self.outcomeType == "PSEUDO_NUMERIC":
            if None in (self.minValue, self.maxValue, self.isLogScale, self.initialValue):
                raise ValueError("Need a minValue, maxValue, isLogScale, and initialValue")

        if isinstance(self.closeTime, datetime):
            self.closeTime = round(self.closeTime.timestamp() * 1000)

    def to_dict(self) -> Dict[str, Any]:
        return {
            k: v for k, v in self.__dict__.items()
            if k in signature(type(self)).parameters and v is not None and k != "outcomeType"
        }


@dataclass
class CreationRequest:
    manifold: ManifoldRequest
    time_rules: List[DoResolveRule]
    value_rules: List[ResolutionValueRule]
    notes: str = ""
    initial_values: Dict[str, int] = field(default_factory=dict)

    def __postinit__(self):
        if not self.manifold.description.get("processed"):
            for paragraph in explain_abstract(
                time_rules=self.time_rules, value_rules=self.value_rules
            ).splitlines():
                # if not paragraph:
                #     continue
                self.manifold.description["content"].append({
                    "type": "paragraph",
                    "content": [{
                        "type": "text",
                        "text": paragraph
                    }]
                })
            self.manifold.description["processed"] = True

    @classmethod
    def from_dict(cls, obj: Dict[str, Any]) -> 'CreationRequest':
        obj = obj.copy()
        manifold = ManifoldRequest.from_dict(obj.pop('manifold'))
        time_rules = [getattr(rule, type_).from_dict(kwargs) for type_, kwargs in obj.pop('time_rules')]
        value_rules = [getattr(rule, type_).from_dict(kwargs) for type_, kwargs in obj.pop('value_rules')]
        return cls(
            manifold=manifold,
            time_rules=time_rules,
            value_rules=value_rules,
            **obj
        )

    def create(self):
        client = get_client()
        if self.manifold.outcomeType == "BINARY":
            market = client.create_binary_market(**self.manifold.to_dict())

        elif self.manifold.outcomeType == "PSEUDO_NUMERIC":
            market = client.create_numeric_market(**self.manifold.to_dict())

        elif self.manifold.outcomeType == "FREE_RESPONSE":
            market = client.create_free_response_market(**self.manifold.to_dict())
            for answer, weight in self.initial_values.items():
                client.create_bet(market.id, weight, answer)

        elif self.manifold.outcomeType == "MULTIPLE_CHOICE":
            raise NotImplementedError()

        else:
            raise ValueError()

        return Market(market, do_resolve_rules=self.time_rules, resolve_to_rules=self.value_rules, notes=self.notes)


if __name__ == '__main__':
    main()