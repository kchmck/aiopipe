from setuptools import setup

setup(
    name="aiopipe",
    version="0.1.2",
    description="Multiprocess communication pipe for asyncio",
    author="Mick Koch",
    author_email="mick@kochm.co",
    license="MIT",
    url="https://github.com/kchmck/aiopipe",
    packages=["aiopipe"],
    extras_require={
        "dev": [
            "pylint==1.6.5",
            "pytest==3.0.6",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: MIT License",
    ],
    keywords="async asyncio pipe os.pipe",
)
