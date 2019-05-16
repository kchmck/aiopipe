# aiopipe -- Multiprocess communication pipe for asyncio

[![Documentation](https://img.shields.io/badge/docs-blue.svg)](http://kchmck.github.io/pdoc/aiopipe/)
[![Build status](https://img.shields.io/circleci/project/github/kchmck/aiopipe/master.svg)](https://circleci.com/gh/kchmck/aiopipe)

This package wraps the [`os.pipe`](https://docs.python.org/3/library/os.html#os.pipe)
simplex communication pipe so it can be used as part of the non-blocking
[`asyncio`](https://docs.python.org/3/library/asyncio.html) event loop.

## Example

The following example opens a pipe with the write end in the child process and the read
end in the parent process:

```python
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

## Installation

This package requires Python >= 3.5.0 and can be installed with `pip`:
```
pip install aiopipe
```
