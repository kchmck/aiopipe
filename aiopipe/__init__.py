"""
This package wraps the [`os.pipe`](https://docs.python.org/3/library/os.html#os.pipe)
simplex communication pipe so it can be used as part of the non-blocking
[`asyncio`](https://docs.python.org/3/library/asyncio.html) event loop.

#### Example

The following example opens a pipe with the write end in the child process and the read
end in the parent process:

```python3
>>> from multiprocessing import Process
>>> import asyncio
>>>
>>> from aiopipe import aiopipe
>>>
>>> async def maintask():
...     rx, tx = aiopipe()
...
...     with tx.detach() as tx:
...         proc = Process(target=childproc, args=(tx,))
...         proc.start()
...
...     # The write end is now available in the child process
...     # and detached from the parent process.
...
...     async with rx.open() as rx:
...         msg = await rx.readline()
...
...     proc.join()
...     return msg
>>>
>>> def childproc(tx):
...     asyncio.new_event_loop().run_until_complete(childtask(tx))
>>>
>>> async def childtask(tx):
...     async with tx.open() as tx:
...         tx.write(b"hi from the child process\\n")
>>>
>>> asyncio.new_event_loop().run_until_complete(maintask())
b'hi from the child process\\n'
>>>
```
"""

from asyncio import StreamReader, StreamWriter, StreamReaderProtocol, get_event_loop
from contextlib import contextmanager
import os

__pdoc__ = {}

def aiopipe():
    """
    Create a new multiprocess communication pipe, returning `(rx, tx)`, where `rx` is an
    instance of `AioPipeReader` and `tx` is an instance of `AioPipeWriter`.
    """

    rx, tx = os.pipe()
    return AioPipeReader(rx), AioPipeWriter(tx)

class AioPipeGuard:
    """
    Created by `AioPipeReader` / `AioPipeWriter` for ensuring the associated pipe end is
    closed after the context is exited.
    """

    __pdoc__["AioPipeGuard.__init__"] = None

    def __init__(self, stream):
        self._stream = stream
        self._transport = None

    async def __aenter__(self):
        transport, stream = await self._stream._open()
        self._transport = transport

        return stream

    async def __aexit__(self, *args):
        try:
            self._transport.close()
        except OSError:
            # The transport/protocol sometimes closes the fd before this is reached.
            pass

class _AioPipeStream:
    def __init__(self, fd):
        self._fd = fd

    def open(self):
        return AioPipeGuard(self)

    async def _open(self):
        raise NotImplementedError()

    @contextmanager
    def detach(self):
        """
        Detach this end of the pipe from the current process in preparation for use in a
        child process.

        This returns a context manager, which must be used as part of a `with` context.
        When the context is entered, the stream is prepared for inheritance by the child
        process and returned as the context variable. When the context is exited, the
        stream is closed in the parent process.
        """

        try:
            os.set_inheritable(self._fd, True)
            yield self
        finally:
            os.close(self._fd)

    def __del__(self):
        try:
            os.close(self._fd)
        except OSError:
            pass

class AioPipeReader(_AioPipeStream):
    """
    The read end of a pipe.
    """

    __pdoc__["AioPipeReader.__init__"] = None

    __pdoc__["AioPipeReader.open"] = """
        Open the receive end on the current event loop, returning an instance of
        `AioPipeGuard`.

        This object must be used as part of a `async with` context. When the context is
        entered, the receive end is opened and an instance of
        [`asyncio.StreamReader`][stdlib] is returned as the context variable. When the
        context is exited, the receive end is closed.

        [stdlib]: https://docs.python.org/3/library/asyncio-stream.html#streamreader
    """

    async def _open(self):
        rx = StreamReader()
        transport, _ = await get_event_loop().connect_read_pipe(
            lambda: StreamReaderProtocol(rx),
            os.fdopen(self._fd))

        return transport, rx

class AioPipeWriter(_AioPipeStream):
    """
    The write end of a pipe.
    """

    __pdoc__["AioPipeWriter.__init__"] = None

    __pdoc__["AioPipeWriter.open"] = """
        Open the transmit end on the current event loop, returning an instance of
        `AioPipeGuard`.

        This object must be used as part of a `async with` context. When the context is
        entered, the transmit end is opened and an instance of
        [`asyncio.StreamWriter`][stdlib] is returned as the context variable. When the
        context is exited, the transmit end is closed.

        [stdlib]: https://docs.python.org/3/library/asyncio-stream.html#streamwriter
    """

    async def _open(self):
        rx = StreamReader()
        transport, proto = await get_event_loop().connect_write_pipe(
            lambda: StreamReaderProtocol(rx),
            os.fdopen(self._fd, "w"))
        tx = StreamWriter(transport, proto, rx, None)

        return transport, tx
