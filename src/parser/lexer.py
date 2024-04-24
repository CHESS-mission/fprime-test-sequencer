from tokens import *
import abc


INDENTATION_SIZE = 2


class Reader(abc.ABC):
    @abc.abstractmethod
    def peek(self, k: int = 1) -> str:
        """Peek the next k characters."""

    @abc.abstractmethod
    def read(self, k: int = 1) -> str:
        """Read (consume) the next k characters."""


class Lexer:
    def __init__(self, reader: Reader) -> None:
        self.reader = reader
        self.is_new_line = True

    def next_token(self):
        return self.process_new_line() if self.is_new_line else self.process_default()

    def process_new_line(self):
        self.is_new_line = False

        indentation_level = 0
        while self.reader.peek(INDENTATION_SIZE) == ' ' * INDENTATION_SIZE:
            self.reader.read(INDENTATION_SIZE) # Discard indent
            indentation_level += 1

        return IndentationToken(indentation_level) if indentation_level != 0 else self.process_default()

    def process_default(self):
        match self.reader.peek():
            case " ":
                self.reader.read() # Skip whitespace
                return self.process_default() # Recurse
            case "#":
                return self.process_comment()
            case _:
                return SyntaxToken("TODO")

    def process_comment(self):
        match self.reader.read():
            case "\n":
                return self.process_new_line()
            case _:
                return self.process_comment() # Recurse

    # def process_string(self):
    #     pass
