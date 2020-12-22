"""
This package wraps the [`os.pipe`](https://docs.python.org/3/library/os.html#os.pipe)
simplex communication pipe so it can be used as part of the non-blocking
[`asyncio`](https://docs.python.org/3/library/asyncio.html) event loop. A duplex pipe
is also provided, which allows reading and writing on both ends.

## Simplex example

The following example opens a pipe with the write end in the child process and the read
end in the parent process.

```python3
>>> from multiprocessing import Process
>>> import asyncio
>>>
>>> from aiopipe import aiopipe
>>>
>>> async def main():
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
...     asyncio.run(childtask(tx))
>>>
>>> async def childtask(tx):
...     async with tx.open() as tx:
...         tx.write(b"hi from the child process\\n")
>>>
>>> asyncio.run(main())
b'hi from the child process\\n'
>>>
```

## Duplex example

The following example shows a parent and child process sharing a duplex pipe to exchange
messages.

```python3
>>> from multiprocessing import Process
>>> import asyncio
>>>
>>> from aiopipe import aioduplex
>>>
>>> async def main():
...     mainpipe, chpipe = aioduplex()
...
...     with chpipe.detach() as chpipe:
...         proc = Process(target=childproc, args=(chpipe,))
...         proc.start()
...
...     # The second pipe is now available in the child process
...     # and detached from the parent process.
...
...     async with mainpipe.open() as (rx, tx):
...         req = await rx.read(5)
...         tx.write(req + b" world\\n")
...         msg = await rx.readline()
...
...     proc.join()
...     return msg
>>>
>>> def childproc(pipe):
...     asyncio.run(childtask(pipe))
>>>
>>> async def childtask(pipe):
...     async with pipe.open() as (rx, tx):
...         tx.write(b"hello")
...         rep = await rx.readline()
...         tx.write(rep.upper())
>>>
>>> asyncio.run(main())
b'HELLO WORLD\\n'
>>>
```
"""

from asyncio import StreamReader, StreamWriter, StreamReaderProtocol, BaseTransport, \
        get_running_loop, sleep
from contextlib import contextmanager, asynccontextmanager
from typing import Tuple, Any, ContextManager, AsyncContextManager
import os

__pdoc__ = {}

def aiopipe() -> Tuple["AioPipeReader", "AioPipeWriter"]:
    """
    Create a new simplex multiprocess communication pipe.

    Return the read end and write end, respectively.
    """

    rx, tx = os.pipe()
    return AioPipeReader(rx), AioPipeWriter(tx)

def aioduplex() -> Tuple["AioDuplex", "AioDuplex"]:
    """
    Create a new duplex multiprocess communication pipe.

    Both returned pipes can write to and read from the other.
    """

    rxa, txa = aiopipe()
    rxb, txb = aiopipe()

    return AioDuplex(rxa, txb), AioDuplex(rxb, txa)

class AioPipeStream:
    """
    Abstract class for pipe readers and writers.
    """

    __pdoc__["AioPipeStream.__init__"] = None
    __pdoc__["AioPipeStream.open"] = None

    def __init__(self, fd):
        self._fd = fd

    @asynccontextmanager
    async def open(self):
        if self._fd is None:
            raise ValueError("File handle already closed")

        transport, stream = await self._open()

        try:
            yield stream
        finally:
            try:
                transport.close()
                self._fd = None
            except OSError:
                # The transport/protocol sometimes closes the fd before this is reached.
                pass

            # Allow event loop callbacks to run and handle closed transport.
            await sleep(0)

    async def _open(self) -> Tuple[BaseTransport, Any]:
        raise NotImplementedError()

    @contextmanager
    def detach(self) -> ContextManager["AioPipeStream"]:
        """
        Detach this end of the pipe from the current process in preparation for use in a
        child process.

        This returns a context manager, which must be used as part of a `with` context.
        When the context is entered, the stream is prepared for
        [inheritance](https://docs.python.org/3/library/os.html#fd-inheritance) by the
        child process and returned as the context variable. When the context is exited,
        the stream is closed in the parent process.
        """

        if self._fd is None:
            raise ValueError("File handle already closed")
        try:
            os.set_inheritable(self._fd, True)
            yield self
        finally:
            # NB: close and explicitly invalidate the file handle here. Any call
            # to os.pipe() after this point may create a new file handle with
            # the same value, which we will then happily close whenever the
            # interpreter happens to call __del__()
            self.close()

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __del__(self):
        try:
            self.close()
        except OSError:
            pass

class AioPipeReader(AioPipeStream):
    """
    The read end of a pipe.
    """

    __pdoc__["AioPipeReader.__init__"] = None
    __pdoc__["AioPipeReader.open"] = """
        Open the receive end on the current event loop.

        This returns an async context manager, which must be used as part of an `async
        with` context. When the context is entered, the receive end is opened and an
        instance of [`StreamReader`][stdlib] is returned as the context variable. When the
        context is exited, the receive end is closed.

        [stdlib]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader
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

    __pdoc__["AioPipeWriter.__init__"] = None
    __pdoc__["AioPipeWriter.open"] = """
        Open the transmit end on the current event loop.

        This returns an async context manager, which must be used as part of an `async
        with` context. When the context is entered, the transmit end is opened and an
        instance of [`StreamWriter`][stdlib] is returned as the context variable. When the
        context is exited, the transmit end is closed.

        [stdlib]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter
    """

    async def _open(self):
        rx = StreamReader()
        transport, proto = await get_running_loop().connect_write_pipe(
            lambda: StreamReaderProtocol(rx),
            os.fdopen(self._fd, "w"))
        tx = StreamWriter(transport, proto, rx, get_running_loop())

        return transport, tx

class AioDuplex:
    """
    Represents one end of a duplex pipe.
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
        When the context is entered, the pipe is prepared for
        [inheritance](https://docs.python.org/3/library/os.html#fd-inheritance) by the
        child process and returned as the context variable. When the context is exited,
        the stream is closed in the parent process.
        """

        with self._rx.detach(), self._tx.detach():
            yield self

    @asynccontextmanager
    async def open(self) -> AsyncContextManager[Tuple["StreamReader", "StreamWriter"]]:
        """
        Open this end of the duplex pipe on the current event loop.

        This returns an async context manager, which must be used as part of an `async
        with` context. When the context is entered, the pipe is opened and the underlying
        [`StreamReader`][reader] and [`StreamWriter`][writer] are returned as the context
        variable. When the context is exited, the pipe is closed.

        [reader]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamReader
        [writer]: https://docs.python.org/3/library/asyncio-stream.html#asyncio.StreamWriter
        """

        async with self._rx.open() as rx, self._tx.open() as tx:
            yield rx, tx
