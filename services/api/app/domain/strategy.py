import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MethodName = Literal["economy", "premium", "deterministic"]
KnownCategory = Literal["routine", "ambiguous", "privileged"]


class RuleWhen(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observed_category_in: list[KnownCategory] = Field(min_length=1)

    @field_validator("observed_category_in")
    @classmethod
    def unique_categories(cls, categories: list[str]) -> list[str]:
        if len(set(categories)) != len(categories):
            raise ValueError("duplicate category in observed_category_in")
        return categories


class PolicyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str = Field(min_length=1, max_length=64)
    priority: int = Field(ge=0, le=10000)
    when: RuleWhen
    method: MethodName


class StrategyDocument(BaseModel):
    """Proposed strategy body. The server assigns the SHA-256 revision."""

    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1"]
    workflow_id: Literal["service-desk"]
    rules: list[PolicyRule]
    default_method: MethodName
    fallback_method: MethodName

    @model_validator(mode="after")
    def unique_rule_identity(self) -> "StrategyDocument":
        rule_ids = [rule.rule_id for rule in self.rules]
        priorities = [rule.priority for rule in self.rules]
        if len(set(rule_ids)) != len(rule_ids):
            raise ValueError("duplicate rule_id")
        if len(set(priorities)) != len(priorities):
            raise ValueError("duplicate priority")
        return self


def canonical_json(document: StrategyDocument) -> str:
    """Priority is the evaluation order. Array order in the request is not part of the hash."""
    ordered = sorted(document.rules, key=lambda rule: rule.priority)
    payload = {
        "default_method": document.default_method,
        "fallback_method": document.fallback_method,
        "rules": [
            {
                "method": rule.method,
                "priority": rule.priority,
                "rule_id": rule.rule_id,
                "when": {"observed_category_in": list(rule.when.observed_category_in)},
            }
            for rule in ordered
        ],
        "schema_version": document.schema_version,
        "workflow_id": document.workflow_id,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def revision_sha256(document: StrategyDocument) -> str:
    digest = hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
