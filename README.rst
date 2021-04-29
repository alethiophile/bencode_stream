bencode_stream
=======

bencode_stream is a library for parsing bencoded data in a streaming fashion. It
is intended for handling large torrent files on memory-constrained platforms.

Usage
=====

The parser is implemented in the class ``StreamingDecoder`` under stream.py.
Parser implementation classes should subclass this.

Data is fed to the parser via the ``parse_data`` method, which accepts bytes.
Byte strings of any length can be fed to ``parse_data``; the raw parser does not
internally buffer any data except the current parse state. This allows very
large bencoded documents to be parsed in limited memory.

Document contents are handled using a set of handler functions which are called
at the appropriate times by ``parse_data``. These functions are noops by
default; a concrete parser class should override the appropriate functions. For
examples, see the ``PrintingDecoder`` and ``ToJSONDecoder`` classes in util.py.

Due to the streaming nature of the decoding, many decoding tasks must be
implemented as state machines. Subclasses of ``StreamingDecoder`` may use any
variable name under ``self``, other than the public method API names; all
``StreamingDecoder`` internal data variables are underscore-prefixed.

Performance
======

bencode_stream aims to minimize its internal memory overhead to the greatest
possible degree. Usually, it requires only constant memory regardless of the
input data. There are three currently known exceptions:

1. The parser state contains a stack that tracks the current recursion depth of
   data structures. This is O(1) in the data structure recursion depth.
2. In order to correctly validate bencoded data, the parser needs to store the
   entirety of every dict key for long enough to compare it to the previous one.
   This is O(1) in the length of the longest dict key in the structure.
3. The parser stores the entirety of the string representation of every integer
   in the data structure, for long enough to parse it. This is O(log(N)) in the
   size of the largest integer stored.

For non-pathological data, I expect that all of these should impose minimal
memory overhead.
