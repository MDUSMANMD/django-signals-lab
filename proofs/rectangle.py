class Rectangle:
    """An iterable rectangle; integers only (bool is intentionally rejected)."""

    def __init__(self, length: int, width: int):
        if type(length) is not int or type(width) is not int:
            raise TypeError("length and width must be integers")
        self.length = length
        self.width = width

    def __iter__(self):
        yield {"length": self.length}
        yield {"width": self.width}
