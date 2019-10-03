# aiopipe -- Multiprocess communication pipes for asyncio

[![Documentation](https://img.shields.io/badge/documentation-blue.svg)](https://kchmck.github.io/aiopipe/aiopipe/)
[![Build status](https://img.shields.io/circleci/project/github/kchmck/aiopipe/master.svg)](https://circleci.com/gh/kchmck/aiopipe)

This package wraps the [`os.pipe`](https://docs.python.org/3/library/os.html#os.pipe)
simplex communication pipe so it can be used as part of the non-blocking
[`asyncio`](https://docs.python.org/3/library/asyncio.html) event loop. A duplex pipe
is also provided, which allows reading and writing on both ends.

## Simplex example

The following example opens a pipe with the write end in the child process and the read
end in the parent process.

```python
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
...         tx.write(b"hi from the child process\n")
>>>
>>> asyncio.run(main())
b'hi from the child process\n'
>>>
```

## Duplex example

The following example shows a parent and child process sharing a duplex pipe to exchange
messages.

```python
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
...         tx.write(req + b" world\n")
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
b'HELLO WORLD\n'
>>>
```

## Installation

This package requires Python 3.7+ and can be installed with `pip`:
```
pip install aiopipe
```
