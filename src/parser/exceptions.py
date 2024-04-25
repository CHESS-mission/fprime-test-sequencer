class ParseError(Exception):
    def __init__(self, filename: str, line_no: int, offset: int, source: str, error: str) -> None:
        super().__init__()
        self.filename = filename
        self.line_no = line_no
        self.offset = offset
        self.source = source
        self.error = error

    def __str__(self) -> str:
        return (
            f"In file {self.filename}, line {self.line_no}\n"
            f"  {self.source.rstrip()}\n"
            f"  {' ' * (self.offset - 1)}^\n"
            f"Parsing error: {self.error}"
        )
