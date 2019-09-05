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

from asyncio import StreamReader, StreamWriter, StreamReaderProtocol, BaseTransport, \
        get_running_loop
from contextlib import contextmanager, asynccontextmanager
from typing import Tuple, Any, ContextManager, AsyncContextManager
import os

__pdoc__ = {}

def aiopipe() -> Tuple["AioPipeReader", "AioPipeWriter"]:
    """
    Create a new simplex multiprocess communication pipe, returning the read end and the
    write end.
    """

    rx, tx = os.pipe()
    return AioPipeReader(rx), AioPipeWriter(tx)

def aioduplex() -> Tuple["AioDuplex", "AioDuplex"]:
    """
    Create a new full-duplex multiprocess communication pipe.
    """

    rxa, txa = aiopipe()
    rxb, txb = aiopipe()

    return AioDuplex(rxa, txb), AioDuplex(rxb, txa)

class AioPipeStream:
    """
    Abstract class for pipe readers and writers.
    """

    __pdoc__["AioPipeStream.__init__"] = None

    def __init__(self, fd):
        self._fd = fd
        self._moved = False
        """
        Tracks if the fd is controlled by asyncio.

        This object will only close the fd if it's not controlled by asyncio. Otherwise,
        asyncio throws an error when it tries to close the fd itself.
        """

    @asynccontextmanager
    async def open(self) -> AsyncContextManager[Any]:
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

    async def _open(self) -> Tuple[BaseTransport, Any]:
        raise NotImplementedError()

    @contextmanager
    def detach(self) -> ContextManager["AioPipeStream"]:
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

class AioPipeReader(AioPipeStream):
    """
    The read end of a pipe.
    """

    __pdoc__["AioPipeReader.open"] = """
        Open the receive end on the current event loop.

        This returns an async context manager, which must be used as part of an `async
        with` context. When the context is entered, the receive end is opened and an
        instance of [`StreamReader`][stdlib] is returned as the context variable. When the
        context is exited, the receive end is closed.

        [stdlib]: https://docs.python.org/3/library/asyncio-stream.html#streamreader
    """

    async def _open(self):
        rx = StreamReader()
        transport, _ = await get_running_loop().connect_read_pipe(
            lambda: StreamReaderProtocol(rx),
            os.fdopen(self._fd))

        return transport, rx

class AioPipeWriter(AioPipeStream):
    """
    The write end of a pipe.
    """

    __pdoc__["AioPipeWriter.open"] = """
        Open the transmit end on the current event loop.

        This returns an async context manager, which must be used as part of an `async
        with` context. When the context is entered, the transmit end is opened and an
        instance of [`StreamWriter`][stdlib] is returned as the context variable. When the
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
    """
    Represents one end of an opened duplex pipe.
    """

    __pdoc__["AioDuplexConnection.__init__"] = None

    def __init__(self, rx: StreamReader, tx: StreamWriter):
        self._rx = rx
        self._tx = tx

    def reader(self) -> StreamReader:
        """
        Retrieve the underlying reader instance.
        """

        return self._rx

    def writer(self) -> StreamWriter:
        """
        Retrieve the underlying writer instance.
        """

        return self._tx

    async def write(self, buf: bytes):
        """
        Write the given bytes and wait for the stream to be drained.

        This is a convenience method, see
        [`StreamWriter.write()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter.write)
        for more information.
        """

        self._tx.write(buf)
        await self._tx.drain()

    async def read(self, n: int = -1) -> bytes:
        """
        Read the given number of bytes.

        This is a convenience method, see
        [`StreamReader.read()`](https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader.read)
        for more information.
        """

        return await self._rx.read(n)

class AioDuplex:
    """
    Represents one end of a duplex pipe,
    """

    __pdoc__["AioDuplex.__init__"] = None

    def __init__(self, rx: AioPipeReader, tx: AioPipeWriter):
        self._rx = rx
        self._tx = tx

    @contextmanager
    def detach(self) -> ContextManager["AioDuplex"]:
        """
        Detach this end of the duplex pipe from the current process in preparation for use
        in a child process.

        This returns a context manager, which must be used as part of a `with` context.
        When the context is entered, the pipe is prepared for inheritance by the child
        process and returned as the context variable. When the context is exited, the
        stream is closed in the parent process.
        """

        with self._rx.detach(), self._tx.detach():
            yield self

    @asynccontextmanager
    async def open(self) -> AsyncContextManager[AioDuplexConnection]:
        """"
        Open this end of the duplex pipe on the current event loop.

        This returns an async context manager, which must be used as part of an `async
        with` context. When the context is entered, the pipe is opened and an instance of
        `AioDuplexConnection` is returned as the context variable. When the context is
        exited, the pipe is closed.
        """

        async with self._rx.open() as rx, self._tx.open() as tx:
            yield AioDuplexConnection(rx, tx)
