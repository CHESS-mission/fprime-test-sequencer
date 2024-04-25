from dataclasses import dataclass
from enum import Enum, auto
from typing import Self


class Keyword(Enum):
    TEST = auto()
    SEQ = auto()
    EXPECT = auto()
    NO = auto()
    COMMAND = auto()
    EVENT = auto()
    TELEMETRY = auto()
    RUNSEQ = auto()

    @classmethod
    def is_keyword(cls, word: str) -> bool:
        return word in cls.__members__.keys()

    @classmethod
    def from_str(cls, word: str) -> Self:
        return cls.__members__[word]


@dataclass
class IndentationToken:
    """Token representing an indentation level."""
    level: int


@dataclass
class NewLineToken:
    """Token representing a new line."""


@dataclass
class KeywordToken:
    """Token representing a keyword."""
    word: Keyword


@dataclass
class IdentifierToken:
    """Token representing an identifier."""
    name: str


@dataclass
class LitteralToken:
    """Token representing a litteral (string, regex or numerical)."""
    value: str
    is_regex: bool = False


@dataclass
class SyntaxToken:
    """Token representing a syntactic element."""
    value: str
