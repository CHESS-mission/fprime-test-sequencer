from tokens import *
from exceptions import ParseError
from dataclasses import dataclass, replace
import abc


INDENTATION_SIZE = 2


class Reader(abc.ABC):
    @abc.abstractmethod
    def peek(self, k: int = 1) -> str:
        """Peek the next k characters."""

    @abc.abstractmethod
    def read(self, k: int = 1) -> str:
        """Read (consume) the next k characters."""

    @abc.abstractmethod
    def source_name(self) -> str:
        """Return source filename."""

    @abc.abstractmethod
    def current_line(self) -> str:
        """Return current source line."""

    @abc.abstractmethod
    def current_line_no(self) -> int:
        """Return current line number."""

    @abc.abstractmethod
    def current_offset(self) -> int:
        """Return current character offset (start at 1)."""


class FileReader(Reader):

    @dataclass
    class Cursor:
        line: int
        col: int

    def __init__(self, filename) -> None:
        super().__init__()
        self.cursor = self.Cursor(0, 0)
        self.filename = filename
        with open(self.filename, 'r') as f:
            self.lines = f.readlines()

    def _step_cursor(self, k: int = 1) -> None:
        for _ in range(k):
            self.cursor.col += 1
            if self.cursor.col >= len(self.current_line()):
                self.cursor.line += 1
                self.cursor.col = 0
                if self.cursor.line >= len(self.lines):
                    # EOF position
                    self.cursor.line = len(self.lines) - 1
                    self.cursor.col = len(self.current_line())

    def at_eof(self) -> bool:
        return self.cursor.line >= len(self.lines) - 1 and self.cursor.col >= len(self.current_line())

    def peek(self, k: int = 1) -> str:
        initial_cursor = replace(self.cursor)
        chars = self.read(k)
        self.cursor = replace(initial_cursor)
        return chars

    def read(self, k: int = 1) -> str:
        chars = ""
        for _ in range(k):
            if self.at_eof():
                break
            chars += self.current_line()[self.cursor.col]
            self._step_cursor()
        return chars

    def source_name(self) -> str:
        return self.filename

    def current_line(self) -> str:
        return self.lines[self.cursor.line]

    def current_line_no(self) -> int:
        return self.cursor.line + 1

    def current_offset(self) -> int:
        return self.cursor.col + 1


class Lexer:
    def __init__(self, reader: Reader) -> None:
        self.reader = reader

    def next_token(self):
        return self.process_new_line() if self.reader.current_offset() == 1 else self.process_default()

    def process_new_line(self):
        indentation_level = 0
        while self.reader.peek(INDENTATION_SIZE) == ' ' * INDENTATION_SIZE:
            self.reader.read(INDENTATION_SIZE) # Discard indent
            indentation_level += 1

        return IndentationToken(indentation_level) if indentation_level != 0 else self.process_default()

    def process_default(self):
        while (char := self.reader.peek()) != '':
            match char:
                case ' ':
                    self.reader.read() # Skip whitespace
                case '\n':
                    self.reader.read() # Skip whitespace
                    return NewLineToken()
                case '#':
                    return self.process_comment()
                case '"':
                    return self.process_string()
                case _ if char in "0123456789.-":
                    return self.process_number()
                case _ if char in "[:]":
                    return SyntaxToken(self.reader.read())
                case _ if char.isalpha() or char == '_':
                    return self.process_identifier()
                case _:
                    raise ParseError(self.reader.source_name(),
                                     self.reader.current_line_no(),
                                     self.reader.current_offset(),
                                     self.reader.current_line(),
                                     f"Unexpected character '{char}'")

        return None

    def process_comment(self):
        while (char := self.reader.read()) != '':
            if char == '\n':
                return NewLineToken()

        return None

    def process_string(self, is_regex=False):
        self.reader.read() # Skip opening "
        string = ""

        while (char := self.reader.peek()) != '':
            match char:
                case '"':
                    self.reader.read()
                    # If "", add a simple " to the string without closing it
                    if self.reader.peek() == '"':
                        string += self.reader.read()
                    else:
                        return LitteralToken(string, is_regex)
                case '\n':
                    break
                case _:
                    string += self.reader.read()

        raise ParseError(self.reader.source_name(),
                         self.reader.current_line_no(),
                         self.reader.current_offset(),
                         self.reader.current_line(),
                         "Expected closing '\"'")

    def process_number(self):
        number = self.reader.read()

        while (char := self.reader.peek()) != '':
            if char in "0123456789.":
                number += self.reader.read()
            else:
                break

        return LitteralToken(number, is_regex=False)

    def process_identifier(self):
        identifier = self.reader.read()

        while (char := self.reader.peek()) != '':
            if char.isalnum() or char in '_.':
                identifier += self.reader.read()
            elif char == '"' and identifier == "re":
                return self.process_string(True)
            else:
                break

        if Keyword.is_keyword(identifier):
            return KeywordToken(Keyword.from_str(identifier))

        return IdentifierToken(identifier)
