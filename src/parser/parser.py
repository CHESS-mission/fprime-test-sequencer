from tokens import *
from lexer import Lexer
from dataclasses import dataclass, field
from typing import Self
import abc


class TokenSlot:
    """Represent a token slot in the structure of an instruction."""

    def __init__(self, expected_token, filter=lambda x: x, optional: bool=False, any_nb: bool=False) -> None:
        self.expected_token = expected_token
        self.filter = filter
        self.optional = optional
        self.any_nb = any_nb

    def match(self, token) -> bool:
        if not self.filter(token):
            return False

        if isinstance(self.expected_token, type):
            return isinstance(token, self.expected_token)
        else:
            return token == self.expected_token


class Instruction(abc.ABC):

    @classmethod
    @abc.abstractmethod
    def get_structure(cls) -> list[tuple[str | None, TokenSlot]]:
        """Return the expected structure of the instruction."""

    @classmethod
    @abc.abstractmethod
    def from_token_dict(cls, token_dict: dict) -> Self:
        """Construct the instruction from the token dictionnary returned by Instruction.parse."""

    @classmethod
    def parse(cls, tokens: list) -> dict | None:
        slots = cls.get_structure()
        instruction_dict = {}
        token_idx = 0
        slot_idx = 0
        while True:
            token = tokens[token_idx] if token_idx < len(tokens) else None
            token_name, token_slot = slots[slot_idx] if slot_idx < len(slots) else (None, None)

            if token_slot == None:
                if token == None:
                    break
                else:
                    return None

            elif token_slot.match(token):
                if token_slot.any_nb:
                    if token_name != None:
                        instruction_dict.setdefault(token_name, [])
                        instruction_dict[token_name] += [token]
                    token_idx += 1
                else:
                    if token_name != None:
                        instruction_dict[token_name] = token
                    token_idx += 1
                    slot_idx += 1

            elif token_slot.any_nb:
                if token_name != None:
                    instruction_dict.setdefault(token_name, [])
                slot_idx += 1

            elif token_slot.optional:
                if token_name != None:
                    instruction_dict[token_name] = None
                slot_idx += 1

            else:
                return None

        return instruction_dict


@dataclass
class SeqInstruction(Instruction):
    seq_name: str
    is_test: bool = False

    @classmethod
    def get_structure(cls) -> list[tuple[str | None, TokenSlot]]:
        return [
            ("is_test", TokenSlot(KeywordToken(Keyword.TEST), optional=True)),
            (None, TokenSlot(KeywordToken(Keyword.SEQ))),
            ("seq_name", TokenSlot(IdentifierToken))
        ]

    @classmethod
    def from_token_dict(cls, token_dict: dict) -> Self:
        return cls(
            seq_name = token_dict["seq_name"].name,
            is_test = token_dict["is_test"] != None
        )

@dataclass
class CommandInstruction(Instruction):
    command: str
    send_time_ms: int
    args: list[str] = field(default_factory=list)

    @classmethod
    def get_structure(cls) -> list[tuple[str | None, TokenSlot]]:
        return [
            (None, TokenSlot(SyntaxToken('['))),
            ("send_time_ms", TokenSlot(LitteralToken, filter=lambda x: x.value.isdigit())),
            (None, TokenSlot(SyntaxToken(']'))),
            (None, TokenSlot(KeywordToken(Keyword.COMMAND))),
            ("command", TokenSlot(IdentifierToken)),
            ("args", TokenSlot(LitteralToken, any_nb=True))
        ]

    @classmethod
    def from_token_dict(cls, token_dict: dict) -> Self:
        return cls(
            command = token_dict["command"].name,
            send_time_ms = int(token_dict["send_time_ms"].value),
            args = [token.value for token in token_dict["args"]]
        )


@dataclass
class ExpectEventInstruction(Instruction):
    event: str
    start_time_ms: int | None = None
    end_time_ms: int | None = None
    expected_value: str | None = None
    is_regex: bool = False
    is_expected: bool = True

    @classmethod
    def get_structure(cls) -> list[tuple[str | None, TokenSlot]]:
        return [
            (None, TokenSlot(SyntaxToken('['))),
            ("start_time_ms", TokenSlot(LitteralToken, filter=lambda x: x.value.isdigit(), optional=True)),
            (None, TokenSlot(SyntaxToken(':'))),
            ("end_time_ms", TokenSlot(LitteralToken, filter=lambda x: x.value.isdigit(), optional=True)),
            (None, TokenSlot(SyntaxToken(']'))),
            (None, TokenSlot(KeywordToken(Keyword.EXPECT))),
            ("is_not_expected", TokenSlot(KeywordToken(Keyword.NO), optional=True)),
            (None, TokenSlot(KeywordToken(Keyword.EVENT))),
            ("event", TokenSlot(IdentifierToken)),
            ("expected_value", TokenSlot(LitteralToken, optional=True))
        ]

    @classmethod
    def from_token_dict(cls, token_dict: dict) -> Self:
        return cls(
            event = token_dict["event"].name,
            start_time_ms = int(token_dict["start_time_ms"].value) if token_dict["start_time_ms"] != None else None,
            end_time_ms = int(token_dict["end_time_ms"].value) if token_dict["end_time_ms"] != None else None,
            expected_value = token_dict["expected_value"].value if token_dict["expected_value"] != None else None,
            is_regex = token_dict["expected_value"].is_regex if token_dict["expected_value"] != None else False,
            is_expected = token_dict["is_not_expected"] == None
        )


@dataclass
class ExpectTelemetryInstruction(Instruction):
    channel: str
    start_time_ms: int | None = None
    end_time_ms: int | None = None
    expected_value: str | None = None
    is_regex: bool = False
    is_expected: bool = True

    @classmethod
    def get_structure(cls) -> list[tuple[str | None, TokenSlot]]:
        return [
            (None, TokenSlot(SyntaxToken('['))),
            ("start_time_ms", TokenSlot(LitteralToken, filter=lambda x: x.value.isdigit(), optional=True)),
            (None, TokenSlot(SyntaxToken(':'))),
            ("end_time_ms", TokenSlot(LitteralToken, filter=lambda x: x.value.isdigit(), optional=True)),
            (None, TokenSlot(SyntaxToken(']'))),
            (None, TokenSlot(KeywordToken(Keyword.EXPECT))),
            ("is_not_expected", TokenSlot(KeywordToken(Keyword.NO), optional=True)),
            (None, TokenSlot(KeywordToken(Keyword.TELEMETRY))),
            ("channel", TokenSlot(IdentifierToken)),
            ("expected_value", TokenSlot(LitteralToken, optional=True))
        ]

    @classmethod
    def from_token_dict(cls, token_dict: dict) -> Self:
        return cls(
            channel = token_dict["channel"].name,
            start_time_ms = int(token_dict["start_time_ms"].value) if token_dict["start_time_ms"] != None else None,
            end_time_ms = int(token_dict["end_time_ms"].value) if token_dict["end_time_ms"] != None else None,
            expected_value = token_dict["expected_value"].value if token_dict["expected_value"] != None else None,
            is_regex = token_dict["expected_value"].is_regex if token_dict["expected_value"] != None else False,
            is_expected = token_dict["is_not_expected"] == None,
        )


@dataclass
class RunSeqInstruction(Instruction):
    seq_name: str
    start_time_ms: int

    @classmethod
    def get_structure(cls) -> list[tuple[str | None, TokenSlot]]:
        return [
            (None, TokenSlot(SyntaxToken('['))),
            ("start_time_ms", TokenSlot(LitteralToken, filter=lambda x: x.value.isdigit(), optional=True)),
            (None, TokenSlot(SyntaxToken(']'))),
            (None, TokenSlot(KeywordToken(Keyword.RUNSEQ))),
            ("seq_name", TokenSlot(IdentifierToken))
        ]

    @classmethod
    def from_token_dict(cls, token_dict: dict) -> Self:
        return cls(
            seq_name = token_dict["seq_name"].name,
            start_time_ms = int(token_dict["start_time_ms"].value)
        )


class Parser:
    def __init__(self, lexer: Lexer) -> None:
        self.lexer = lexer

    def match_instruction(self, tokens: list):
        for instruction_type in Instruction.__subclasses__():
            if (token_dict := instruction_type.parse(tokens)) != None:
                return instruction_type.from_token_dict(token_dict)
        return None

    def parse(self):
        current_line = []
        indentation = 0
        while (token := self.lexer.next_token()) != None:
            match token:
                case IndentationToken(level):
                    indentation = level
                case NewLineToken():
                    if (instruction := self.match_instruction(current_line)) != None:
                        print(f"{'  '*indentation} {instruction}")
                    elif len(current_line) != 0:
                        print("==== ERROR ====")
                    current_line = []
                case _:
                    current_line += [token]
