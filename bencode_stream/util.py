#!python3

import click, json
from base64 import b64encode

from . import stream

from typing import IO, Optional

def parse_file(dec: stream.StreamingDecoder, inp: IO,
               chunk_size: int = 1024) -> None:
    while True:
        data = inp.read(chunk_size)
        if len(data) == 0:
            break
        if not isinstance(data, bytes):
            data = data.encode()
        dec.parse_data(data)
    dec.end_data()

class PrintingDecoder(stream.StreamingDecoder):
    def handle_dict_start(self) -> None:
        print("handle_dict_start")

    def handle_dict_key_start(self) -> None:
        print("handle_dict_key_start")

    def handle_dict_key_end(self, key: bytes) -> None:
        print(f"handle_dict_key_end: {key!r}")

    def handle_dict_value_start(self) -> None:
        print("handle_dict_value_start")

    def handle_dict_value_end(self) -> None:
        print("handle_dict_value_end")

    def handle_dict_end(self) -> None:
        print("handle_dict_end")

    def handle_list_start(self) -> None:
        print("handle_list_start")

    def handle_list_value_start(self) -> None:
        print("handle_list_value_start")

    def handle_list_value_end(self) -> None:
        print("handle_list_value_end")

    def handle_list_end(self) -> None:
        print("handle_list_end")

    def handle_bytes_start(self, blen: int) -> None:
        print(f"handle_bytes_start: {blen}")

    def handle_bytes_data(self, data: bytes) -> None:
        print(f"handle_bytes_data: {data!r}")

    def handle_bytes_end(self) -> None:
        print("handle_bytes_end")

    def handle_int(self, val: int) -> None:
        print(f"handle_int: {val}")

class ToJSONDecoder(stream.StreamingDecoder):
    def __init__(self) -> None:
        super().__init__()

        self.bytes_accum: Optional[bytes] = None
        self.in_dict_key = False
        self.first_key = True

    def handle_dict_start(self) -> None:
        print("{", end='')
        self.first_key = True

    def handle_dict_key_start(self) -> None:
        self.in_dict_key = True
        if not self.first_key:
            print(", ", end='')
        self.first_key = False

    def handle_dict_key_end(self, key: bytes) -> None:
        self.in_dict_key = False
        print(": ", end='')

    def handle_dict_end(self) -> None:
        print("}", end='')

    def handle_list_start(self) -> None:
        print("[", end='')
        self.first_key = True

    def handle_list_value_start(self) -> None:
        if not self.first_key:
            print(", ", end='')
        self.first_key = False

    def handle_list_end(self) -> None:
        print("]", end='')

    def handle_bytes_start(self, l: int) -> None:
        self.bytes_accum = b""

    def handle_bytes_data(self, data: bytes) -> None:
        assert self.bytes_accum is not None
        self.bytes_accum += data

    def handle_bytes_end(self) -> None:
        assert self.bytes_accum is not None
        try:
            s = self.bytes_accum.decode('ascii')
        except UnicodeDecodeError:
            if self.in_dict_key:
                raise ValueError("no base64 dict key")
            s = 'base64:' + b64encode(self.bytes_accum).decode('ascii')
        print(json.dumps(s), end='')
        self.bytes_accum = None

    def handle_int(self, val: int) -> None:
        print(val, end='')

@click.command()
@click.argument('inp', type=click.Path(exists=True))
@click.option('--json/--no-json')
def bencode_test(inp: str, json: bool) -> None:
    dec: stream.StreamingDecoder
    if json:
        dec = ToJSONDecoder()
    else:
        dec = PrintingDecoder()
    with open(inp, 'rb') as infile:
        parse_file(dec, infile)
