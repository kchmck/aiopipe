from setuptools import setup

setup(
    name="aiopipe",
    version="0.2.0",
    description="Multiprocess communication pipe for asyncio",
    author="Mick Koch",
    author_email="mick@kochm.co",
    license="MIT",
    url="https://github.com/kchmck/aiopipe",
    packages=["aiopipe"],
    python_requires=">=3.5",
    extras_require={
        "dev": [
            "tox~=3.9",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "License :: OSI Approved :: MIT License",
    ],
    keywords="async asyncio pipe os.pipe",
)
