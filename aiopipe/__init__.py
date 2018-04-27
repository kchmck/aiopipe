"""
This package wraps the [`os.pipe`](https://docs.python.org/3/library/os.html#os.pipe)
simplex communication pipe so it can be used as part of the non-blocking
[`asyncio`](https://docs.python.org/3/library/asyncio.html) event loop.

#### Example

The following example opens a pipe with the write end in the child process and the read
end in the parent process:

```python3
from contextlib import closing
from multiprocessing import Process
import asyncio

from aiopipe import aiopipe

async def mainTask(eventLoop):
    rx, tx = aiopipe()

    with tx.send() as tx:
        proc = Process(target=childProc, args=(tx,))
        proc.start()

    # The write end is now available in the child process
    # and invalidated in the parent process.

    stream = await rx.open(eventLoop)
    msg = await stream.readline()

    assert msg == b"hi from child process\\n"
    proc.join()

def childProc(tx):
    eventLoop = asyncio.new_event_loop()
    stream = eventLoop.run_until_complete(tx.open(eventLoop))

    with closing(stream):
        stream.write(b"hi from child process\\n")

eventLoop = asyncio.get_event_loop()
eventLoop.run_until_complete(mainTask(eventLoop))
```
"""

from asyncio import StreamReader, StreamWriter, StreamReaderProtocol
import asyncio
import os

__pdoc__ = {}

def aiopipe():
    """
    Create a new multiprocess communication pipe, returning `(rx, tx)`, where `rx` is an
    instace of `AioPipeReader` and `tx` is an instance of `AioPipeWriter`.
    """

    rxFd, txFd = os.pipe()
    return AioPipeReader(rxFd), AioPipeWriter(txFd)

class AioPipeGuard:
    """
    Created by `AioPipeReader` / `AioPipeWriter` for sending one end of a pipe to a child
    process.
    """

    __pdoc__["AioPipeGuard.__init__"] = None

    def __init__(self, stream):
        self._stream = stream

    def __enter__(self):
        os.set_inheritable(self._stream._fd, True)
        return self._stream

    def __exit__(self, exType, exVal, trace):
        os.close(self._stream._fd)

class _AioPipeStream:
    def __init__(self, fd):
        self._fd = fd

    def open(self, eventLoop):
        raise NotImplementedError

    def send(self):
        """
        Send this end of the pipe to a child process.

        This returns an instance of `AioPipeGuard`, which must be used as part of a `with`
        context. When the context is entered, the stream is prepared for inheritance by
        the child process and returned as the context variable. When the context is exited,
        the stream is closed in the parent process.
        """

        return AioPipeGuard(self)

class AioPipeReader(_AioPipeStream):
    """
    The read end of a pipe.
    """

    __pdoc__["AioPipeReader.__init__"] = None

    async def open(self, loop=None):
        """
        Open the receive end on the given event loop, returning an instance of
        [`asyncio.StreamReader`](https://docs.python.org/3/library/asyncio-stream.html#streamreader).

        If no event loop is given, the default one will be used.
        """

        if loop is None:
            loop = asyncio.get_event_loop()

        rx = StreamReader(loop=loop)
        _, _ = await loop.connect_read_pipe(
            lambda: StreamReaderProtocol(rx, loop=loop),
            os.fdopen(self._fd))

        return rx

class AioPipeWriter(_AioPipeStream):
    """
    The write end of a pipe.
    """

    __pdoc__["AioPipeWriter.__init__"] = None

    async def open(self, loop=None):
        """
        Open the transmit end on the given event loop, returning an instance of
        [`asyncio.StreamWriter`](https://docs.python.org/3/library/asyncio-stream.html#streamwriter).

        If no event loop is given, the default one will be used.
        """

        if loop is None:
            loop = asyncio.get_event_loop()

        txTransport, txProto = await loop.connect_write_pipe(
            lambda: StreamReaderProtocol(StreamReader(loop=loop), loop=loop),
            os.fdopen(self._fd, "w"))
        tx = StreamWriter(txTransport, txProto, None, loop)

        return tx
