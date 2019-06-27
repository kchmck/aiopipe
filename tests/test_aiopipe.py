from multiprocessing import Process
import asyncio
import os
import pytest

from aiopipe import aiopipe, aioduplex

def test_simplex():
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

def test_duplex():
    async def maintask():
        pa, pb = aioduplex()

        fds = [pb._rx._fd, pb._tx._fd]
        with pb.detach() as pipe:
            proc = Process(target=childproc, args=(pipe,))
            proc.start()

        for fd in fds:
            with pytest.raises(OSError):
                os.stat(fd)

        fds = [pa._rx._fd, pa._tx._fd]
        async with pa.open() as pipe:
            await pipe.write(b"abc")
            msg = await pipe.read(6)

        proc.join()
        assert proc.exitcode == 0

        # Allow execution of cleanup tasks.
        await asyncio.sleep(0)

        for fd in fds:
            with pytest.raises(OSError):
                os.stat(fd)

        assert msg == b"abcdef"

    async def childtask(pipe):
        fds = [pipe._rx._fd, pipe._tx._fd]
        async with pipe.open() as pipe:
            msg = await pipe.read(3)
            await pipe.write(msg + b"def")

        # Allow execution of cleanup tasks.
        await asyncio.sleep(0)

        for fd in fds:
            with pytest.raises(OSError):
                os.stat(fd)

    def childproc(pipe):
        asyncio.run(childtask(pipe))

    asyncio.run(maintask())
