from tokens import *
from lexer import Lexer
from dataclasses import dataclass, field, replace
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

    def with_time_offset(self, time_offset: int) -> Self:
        copy = replace(self)
        copy.send_time_ms += time_offset
        return copy


@dataclass
class ExpectEventInstruction(Instruction):
    event: str
    start_time_ms: int = 0
    end_time_ms: int = -1
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
            start_time_ms = int(token_dict["start_time_ms"].value) if token_dict["start_time_ms"] != None else 0,
            end_time_ms = int(token_dict["end_time_ms"].value) if token_dict["end_time_ms"] != None else -1,
            expected_value = token_dict["expected_value"].value if token_dict["expected_value"] != None else None,
            is_regex = token_dict["expected_value"].is_regex if token_dict["expected_value"] != None else False,
            is_expected = token_dict["is_not_expected"] == None
        )

    def with_time_offset(self, time_offset: int) -> Self:
        copy = replace(self)
        copy.start_time_ms += time_offset
        copy.end_time_ms += time_offset if self.end_time_ms != -1 else 0
        return copy


@dataclass
class ExpectTelemetryInstruction(Instruction):
    channel: str
    start_time_ms: int = 0
    end_time_ms: int = -1
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
            start_time_ms = int(token_dict["start_time_ms"].value) if token_dict["start_time_ms"] != None else 0,
            end_time_ms = int(token_dict["end_time_ms"].value) if token_dict["end_time_ms"] != None else -1,
            expected_value = token_dict["expected_value"].value if token_dict["expected_value"] != None else None,
            is_regex = token_dict["expected_value"].is_regex if token_dict["expected_value"] != None else False,
            is_expected = token_dict["is_not_expected"] == None,
        )

    def with_time_offset(self, time_offset: int) -> Self:
        copy = replace(self)
        copy.start_time_ms += time_offset
        copy.end_time_ms += time_offset if self.end_time_ms != -1 else 0
        return copy


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


@dataclass
class EmptyInstruction(Instruction):

    @classmethod
    def get_structure(cls) -> list[tuple[str | None, TokenSlot]]:
        return []

    @classmethod
    def from_token_dict(cls, token_dict: dict) -> Self:
        return cls()


@dataclass
class Sequence:
    name: str
    is_test: bool
    command_instrs: list[CommandInstruction] = field(default_factory=list)
    event_instrs: list[ExpectEventInstruction] = field(default_factory=list)
    telemetry_instrs: list[ExpectTelemetryInstruction] = field(default_factory=list)

    def get_ordered_commands(self):
        return sorted(self.command_instrs, key=lambda ci: ci.send_time_ms)

    def get_duration(self):
        return max(
            max(self.command_instrs, key=lambda ci: ci.send_time_ms).send_time_ms,
            max(self.event_instrs, key=lambda ei: int(ei.end_time_ms)).end_time_ms,
            max(self.telemetry_instrs, key=lambda ti: ti.end_time_ms).end_time_ms
        )

    def merge(self, sequence: Self, time_offset: int=0):
        self.command_instrs += list(map(lambda ci: ci.with_time_offset(time_offset), sequence.command_instrs))
        self.event_instrs += list(map(lambda ei: ei.with_time_offset(time_offset), sequence.event_instrs))
        self.telemetry_instrs += list(map(lambda ti: ti.with_time_offset(time_offset), sequence.telemetry_instrs))


class Parser:
    def __init__(self, lexer: Lexer) -> None:
        self.lexer = lexer

    def match_instruction(self, tokens: list):
        for instruction_type in Instruction.__subclasses__():
            if (token_dict := instruction_type.parse(tokens)) != None:
                return instruction_type.from_token_dict(token_dict)
        return None

    def instruction_generator(self):
        current_line = []
        indentation = 0
        while (token := self.lexer.next_token()) != None:
            match token:
                case IndentationToken(level):
                    indentation = level
                case NewLineToken():
                    yield indentation, self.match_instruction(current_line)
                    indentation = 0
                    current_line = []
                case _:
                    current_line += [token]

    def flatten_seq(self,
                    seq_name: str,
                    named_sequences: dict[str, Sequence],
                    named_runsec_instrs: dict[str, list[RunSeqInstruction]],
                    seq_name_stack: list[str]=[]) -> Sequence:
        if seq_name in seq_name_stack:
            print("==== ERROR 5 ====")
            raise Exception()
        if not seq_name in named_sequences:
            print("==== ERROR 6 ====")
            raise Exception()
        sequence = replace(named_sequences[seq_name])
        for runseq in named_runsec_instrs[seq_name]:
            flattened_subseq = self.flatten_seq(runseq.seq_name, named_sequences, named_runsec_instrs, seq_name_stack + [seq_name])
            sequence.merge(flattened_subseq, runseq.start_time_ms)
        return sequence

    def parse(self):
        sequences: dict[str, Sequence] = {}
        runseqs: dict[str, list[RunSeqInstruction]] = {}
        current_sequence: Sequence | None = None
        timing_stack: list[int] = []

        for indentation, instruction in self.instruction_generator():
            match instruction:
                case SeqInstruction(seq_name, is_test):
                    if indentation != 0:
                        print("==== ERROR 1 ====")
                        return
                    if current_sequence != None:
                        sequences[current_sequence.name] = current_sequence
                    current_sequence = Sequence(seq_name, is_test)
                    runseqs[seq_name] = []
                    timing_stack = [0]

                case EmptyInstruction():
                    pass

                case None:
                    print("==== ERROR 4 ====")
                    return

                case _:
                    if current_sequence == None:
                        print("==== ERROR 2 ====")
                        return
                    if 1 <= indentation <= 1 + len(timing_stack):
                        timing_stack = timing_stack[:indentation]
                    else:
                        print("==== ERROR 3 ====")
                        return

                    match instruction:
                        case CommandInstruction():
                            current_sequence.command_instrs += [instruction.with_time_offset(timing_stack[-1])]
                            timing_stack += [timing_stack[-1] + instruction.send_time_ms]

                        case ExpectEventInstruction():
                            current_sequence.event_instrs += [instruction.with_time_offset(timing_stack[-1])]
                            timing_stack += [timing_stack[-1] + instruction.start_time_ms]

                        case ExpectTelemetryInstruction():
                            current_sequence.telemetry_instrs += [instruction.with_time_offset(timing_stack[-1])]
                            timing_stack += [timing_stack[-1] + instruction.start_time_ms]

                        case RunSeqInstruction():
                            instruction.start_time_ms += timing_stack[-1]
                            timing_stack += [instruction.start_time_ms]
                            runseqs[current_sequence.name] += [instruction]

        if current_sequence != None:
            sequences[current_sequence.name] = current_sequence

        flattened_sequences: dict[str, Sequence] = {}
        for seq_name in sequences.keys():
            flattened_sequences[seq_name] = self.flatten_seq(seq_name, sequences, runseqs)

        for seq_name, seq in flattened_sequences.items():
            print(f"{seq_name}:")
            print("\tCOMMANDS:")
            for command in seq.get_ordered_commands():
                print(f"\t[{command.send_time_ms}]: {command.command}")
            print()
            print("\tEVENTS:")
            for event in seq.event_instrs:
                print(f"\t[{event.start_time_ms}:{event.end_time_ms}]: {event.event}")
            print()
            print("\tTELEMETRY:")
            for telemetry in seq.telemetry_instrs:
                print(f"\t[{telemetry.start_time_ms}:{telemetry.end_time_ms}]: {telemetry.channel}")
            print()
            
        return flattened_sequences

