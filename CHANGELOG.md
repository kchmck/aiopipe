## v0.2.2 - 2019-10-16

## Fixes

- Fixed `AttributeError: 'NoneType' object has no attribute 'create_future'` error in
  `StreamWriter` that appeared with Python 3.8

## v0.2.1 – 2019-10-03

### New features

- Added the [`aioduplex()`](https://kchmck.github.io/aiopipe/aiopipe/#aiopipe.aioduplex)
  function for creating async duplex pipes

### Breaking changes

- `send()` method for inheriting pipe renamed to `detach()`
- `open()` now returns a context -- `close()` method removed
- Python 3.7+ is now required for the `get_running_loop()` and `asynccontextmanager()`
  functions

## v0.2.0 - 2019-10-03

- Skipped due to mistake that caused readme to not display on PyPi

## v0.1.3 – 2018-10-19

- Bug fixes

## v0.1.2 – 2018-08-01

- Bug fixes

## v0.1.1 – 2017-07-27

- Initial release
