# aiopipe -- Multiprocess communication pipe for asyncio

[Documentation](http://kchmck.github.io/pdoc/aiopipe)

This package wraps the [`os.pipe`](https://docs.python.org/3/library/os.html#os.pipe)
simplex communication pipe so it can be used as part of the non-blocking
[`asyncio`](https://docs.python.org/3/library/asyncio.html) event loop.

## Example

The following example opens a pipe with the write end in the child process and the read
end in the parent process:

```python
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

    assert msg == b"hi from child process\n"

    proc.join()

def childProc(tx):
    eventLoop = asyncio.new_event_loop()
    stream = eventLoop.run_until_complete(tx.open(eventLoop))

    with closing(stream):
        stream.write(b"hi from child process\n")

eventLoop = asyncio.get_event_loop()
eventLoop.run_until_complete(mainTask(eventLoop))
```

## Installation

This package requires Python >= 3.5.0 and can be installed with `pip`:
```
pip install aiopipe
```
