import os

_THIS_DIR = os.path.dirname(os.path.realpath(__file__))


def read_file(filename: str) -> str:
    with open(os.path.join(_THIS_DIR, filename), encoding="utf-8") as file:
        return file.read()
