#!python3

# bencode_stream is a library for parsing bencoded data in a streaming fashion,
# meant for handling large torrent files on memory-constrained platforms.

import enum, attr

from typing import List, Optional

class DataType(enum.Enum):
    INT = 0
    BYTES = 1
    LIST = 2
    DICT = 3
    END = 4

class DecodeError(Exception):
    pass

@attr.s(auto_attribs=True)
class DictParseState:
    latest_key: Optional[bytes] = None
    expect_key: bool = True

class StreamingDecoder:
    """This is a base class that streaming decoders should inherit from. bencoded
    data is fed to this class via the parse_data() method, and this class
    parses out the data and calls the appropriate handle_*() methods (which are
    noops in the base class).

    """

    def handle_dict_start(self) -> None:
        pass

    def handle_dict_key_start(self) -> None:
        pass

    def handle_dict_key_end(self, key: bytes) -> None:
        pass

    def handle_dict_value_start(self) -> None:
        pass

    def handle_dict_value_end(self) -> None:
        pass

    def handle_dict_end(self) -> None:
        pass

    def handle_list_start(self) -> None:
        pass

    def handle_list_value_start(self) -> None:
        pass

    def handle_list_value_end(self) -> None:
        pass

    def handle_list_end(self) -> None:
        pass

    def handle_bytes_start(self, blen: int) -> None:
        pass

    def handle_bytes_data(self, data: bytes) -> None:
        pass

    def handle_bytes_end(self) -> None:
        pass

    def handle_int(self, val: int) -> None:
        pass

    def handle_error(self, msg: str) -> None:
        emsg = f"Error: {msg} (at byte {self._byte_offset})"
        raise DecodeError(emsg)

    def __init__(self) -> None:
        # this is a stack representing the current parse state
        self._now_inside: List[DataType] = []
        # this has the byte offset of current parsing
        self._byte_offset: int = 0
        # this is a stack of parse states for each dict we're in -- note it
        # only has entries for dicts, so it will usually be shorter than
        # _now_inside
        self._dicts: List[DictParseState] = []

        # if an error is encountered, this is set: afterward, the parser cannot
        # parse any more
        self._error = False
        # if the top-level value finishes, this is set: afterward, cannot parse
        # any more
        self._finished = False

        # buffer for incomplete data -- this will only hold the middle part of
        # int parses, anything else gets represented in the parse state
        self._buf = b""

        self._cur_dict_key: Optional[bytes] = None

        self._bytes_expect_len: Optional[int] = None
        self._bytes_parsed_len: Optional[int] = None

    def _can_expect(self):
        # this function returns which types the parser can currently expect

        ALL_TYPES = (DataType.INT, DataType.BYTES, DataType.LIST,
                     DataType.DICT)
        # at the top level, we can parse any object but only one
        if len(self._now_inside) == 0:
            return ALL_TYPES

        # list can include any data type
        if self._now_inside[-1] == DataType.LIST:
            return (ALL_TYPES + (DataType.END,))

        if self._now_inside[-1] == DataType.DICT:
            curstate = self._dicts[-1]
            # if we need a key, it must be bytes
            if curstate.expect_key:
                return (DataType.BYTES, DataType.END)
            else:
                return ALL_TYPES

        # this exhausts all valid cases (can't be inside an int, if we're
        # inside a bytes then we don't use this method)
        raise ValueError("incorrect _now_inside tip value")

    def _check_dict_key(self) -> None:
        """This toggles the expect_key setting for the current dict, if the parser is
        currently directly under a dict. Should be called every time an object
        finished parsing.

        """
        if len(self._now_inside) == 0:
            self._finished = True
            return

        if self._now_inside[-1] == DataType.DICT:
            cv = self._dicts[-1]
            cv.expect_key = not cv.expect_key
            if not cv.expect_key:
                assert self._cur_dict_key is not None

                if (cv.latest_key is not None and
                    not self._cur_dict_key > cv.latest_key):
                    self._error = True
                    self.handle_error(f"invalid key ordering on key "
                                      f"{self._cur_dict_key.decode()!r}")
                    return

                cv.latest_key = self._cur_dict_key
            else:
                self.handle_dict_value_end()
        elif self._now_inside[-1] == DataType.LIST:
            self.handle_list_value_end()

    def _check_handle_dict(self, ctype: DataType) -> None:
        """This checks whether we're currently parsing a dict, and if so calls the
        appropriate handle_dict_key or handle_dict_value methods. It should be
        called before parsing any object.

        """
        if (len(self._now_inside) == 0 or
            ctype == DataType.END):
            return

        if self._now_inside[-1] == DataType.DICT:
            if self._dicts[-1].expect_key:
                self.handle_dict_key_start()
                self._cur_dict_key = b""
            else:
                self.handle_dict_value_start()
                self._cur_dict_key = None
        elif self._now_inside[-1] == DataType.LIST:
            self.handle_list_value_start()

    def _dict_key_data(self, s: bytes) -> None:
        if self._cur_dict_key is not None:
            self._cur_dict_key += s

    def parse_data(self, data: bytes) -> None:
        if self._error:
            raise DecodeError("parser in error state, cannot continue")
        if self._finished:
            raise DecodeError("parser finished with top-level object, "
                              "cannot continue")

        self._buf += data
        del data

        while True:
            if (len(self._now_inside) > 0 and
                self._now_inside[-1] == DataType.BYTES):
                assert self._bytes_expect_len is not None
                assert self._bytes_parsed_len is not None

                rem_bytes = self._bytes_expect_len - self._bytes_parsed_len
                th, self._buf = self._buf[:rem_bytes], self._buf[rem_bytes:]
                parsed_len = len(th)
                self.handle_bytes_data(th)
                self._dict_key_data(th)
                del th

                self._bytes_parsed_len += parsed_len
                self._byte_offset += parsed_len
                if self._bytes_parsed_len >= self._bytes_expect_len:
                    self._bytes_parsed_len = None
                    self._bytes_expect_len = None
                    self._now_inside.pop()
                    self.handle_bytes_end()
                    self._check_dict_key()
                    if self._cur_dict_key is not None:
                        self.handle_dict_key_end(self._cur_dict_key)
                    if len(self._buf) == 0:
                        break
                else:
                    # in this case, we consumed all available data and are
                    # still in the string; just break out of the parse loop and
                    # return to wait for more data
                    break

            good_types = self._can_expect()

            if len(self._buf) == 0:
                break

            if self._buf[0] == ord('i'):
                cur_type = DataType.INT
            elif self._buf[0] == ord('d'):
                cur_type = DataType.DICT
            elif self._buf[0] == ord('l'):
                cur_type = DataType.LIST
            elif self._buf[0:1].isdigit():
                cur_type = DataType.BYTES
            elif self._buf[0] == ord('e'):
                cur_type = DataType.END

            if cur_type not in good_types:
                self._error = True
                self.handle_error(f"unexpected object type {cur_type}")
                return

            self._check_handle_dict(cur_type)

            if cur_type == DataType.INT:
                i = 1
                while True:
                    if i >= len(self._buf):
                        # in this case, the buffer ends mid-int; break out and
                        # wait for more data
                        return
                    elif self._buf[i] == ord('e'):
                        end_ind = i
                        break
                    elif (not self._buf[i:i + 1].isdigit() and
                          self._buf[i] != ord('-')):
                        self._error = True
                        self.handle_error("invalid int")
                        return
                    i += 1
                num_b = self._buf[1:end_ind]
                val = int(num_b)
                self.handle_int(val)
                self._byte_offset += len(num_b) + 2
                self._buf = self._buf[end_ind + 1:]
                self._check_dict_key()
            elif cur_type == DataType.BYTES:
                i = 0
                while True:
                    if i >= len(self._buf):
                        # we're mid-int, return and wait for more data
                        return
                    elif self._buf[i] == ord(':'):
                        end_ind = i
                        break
                    elif not self._buf[i:i + 1].isdigit():
                        self._error = True
                        self.handle_error("invalid bytestring length")
                        return
                    i += 1
                num_b = self._buf[:end_ind]
                val = int(num_b)
                self._bytes_expect_len = val
                self._bytes_parsed_len = 0
                self._byte_offset += len(num_b) + 1
                self._buf = self._buf[end_ind + 1:]
                self._now_inside.append(DataType.BYTES)
                self.handle_bytes_start(val)
                # jump back and parse bytes data
                continue
            elif cur_type == DataType.LIST:
                self._now_inside.append(DataType.LIST)
                self._byte_offset += 1
                self._buf = self._buf[1:]
                self.handle_list_start()
            elif cur_type == DataType.DICT:
                self._now_inside.append(DataType.DICT)
                self._dicts.append(DictParseState())
                self._byte_offset += 1
                self._buf = self._buf[1:]
                self.handle_dict_start()
            elif cur_type == DataType.END:
                if self._now_inside[-1] == DataType.DICT:
                    self._now_inside.pop()
                    self._dicts.pop()
                    self.handle_dict_end()
                elif self._now_inside[-1] == DataType.LIST:
                    self._now_inside.pop()
                    self.handle_list_end()
                else:
                    self._error = True
                    self.handle_error("invalid end token")
                    return
                self._check_dict_key()
                self._byte_offset += 1
                self._buf = self._buf[1:]

    def end_data(self) -> None:
        if (len(self._now_inside) > 0 or len(self._dicts) > 0 or
            not self._finished):
            self._error = True
            self.handle_error("data ended with unfinished parse")
