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
>>> asyncio.run(maintask())
b'hi from the child process\\n'
>>>
```
"""

from asyncio import StreamReader, StreamWriter, StreamReaderProtocol, get_running_loop
from contextlib import contextmanager, asynccontextmanager
from typing import Tuple
import os

__pdoc__ = {}

def aiopipe():
    """
    Create a new multiprocess communication pipe, returning `(rx, tx)`, where `rx` is an
    instance of `AioPipeReader` and `tx` is an instance of `AioPipeWriter`.
    """

    rx, tx = os.pipe()
    return AioPipeReader(rx), AioPipeWriter(tx)

class _AioPipeStream:
    def __init__(self, fd):
        self._fd = fd
        self._moved = False
        """
        Tracks if the fd is controlled by asyncio.

        This object will only close the fd if it's not controlled by asyncio. Otherwise,
        asyncio throws an error when it tries to close the fd itself.
        """

    @asynccontextmanager
    async def open(self):
        transport, stream = await self._open()
        self._moved = True

        try:
            yield stream
        finally:
            try:
                transport.close()
            except OSError:
                # The transport/protocol sometimes closes the fd before this is reached.
                pass

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
        if self._moved:
            return

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
        transport, _ = await get_running_loop().connect_read_pipe(
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
        transport, proto = await get_running_loop().connect_write_pipe(
            lambda: StreamReaderProtocol(rx),
            os.fdopen(self._fd, "w"))
        tx = StreamWriter(transport, proto, rx, None)

        return transport, tx

class AioDuplexConnection:
    def __init__(self, rx: StreamReader, tx: StreamWriter):
        self._rx = rx
        self._tx = tx

    def reader(self) -> StreamReader:
        return self._rx

    def writer(self) -> StreamWriter:
        return self._tx

    async def write(self, buf: bytes):
        self._tx.write(buf)
        await self._tx.drain()

    async def read(self, n=-1) -> bytes:
        return await self._rx.read(n)

class AioDuplex:
    def __init__(self, rx: AioPipeReader, tx: AioPipeWriter):
        self._rx = rx
        self._tx = tx

    @contextmanager
    def detach(self) -> "AioDuplex":
        with self._rx.detach(), self._tx.detach():
            yield self

    @asynccontextmanager
    async def open(self) -> AioDuplexConnection:
        async with self._rx.open() as rx, self._tx.open() as tx:
            yield AioDuplexConnection(rx, tx)

def aioduplex() -> Tuple[AioDuplex, AioDuplex]:
    rxa, txa = aiopipe()
    rxb, txb = aiopipe()

    return AioDuplex(rxa, txb), AioDuplex(rxb, txa)
