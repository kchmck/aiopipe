from multiprocessing import Process
import asyncio
import os
import pytest

from aiopipe import aiopipe

def test_mod():
    async def maintask():
        rx, tx = aiopipe()

        fd = tx._fd
        with tx.detach() as tx:
            proc = Process(target=childproc, args=(tx,))
            proc.start()

        # Ensure fd is closed.
        with pytest.raises(OSError):
            os.stat(fd)

        fd = rx._fd
        async with rx.open() as rx:
            msg = await rx.readline()

        proc.join()
        assert proc.exitcode == 0

        # Allow execution of cleanup tasks.
        await asyncio.sleep(0)

        # Ensure fd is closed.
        with pytest.raises(OSError):
            os.stat(fd)

        assert msg == b"hi from child process\n"

    async def childtask(tx):
        fd = tx._fd
        async with tx.open() as tx:
            tx.write(b"hi from child process\n")

        # Allow execution of cleanup tasks.
        await asyncio.sleep(0)

        # Ensure fd is closed.
        with pytest.raises(OSError):
            os.stat(fd)

    def childproc(tx):
        asyncio.run(childtask(tx))

    asyncio.run(maintask())
