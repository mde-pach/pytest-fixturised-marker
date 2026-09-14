# pytest-fixturised-marker

Mark a fixture, and every test that uses it inherits the mark.

pytest refuses marks on fixtures — since 9.0 it is a hard error. This plugin lifts that restriction
and propagates the marks to the tests at collection time, so `-m`, `skip`, `skipif` and `xfail` all
behave as if you had written the mark on each test yourself.

## Install

```console
pip install pytest-fixturised-marker
```

No configuration: the plugin registers itself.

## Usage

```python
@pytest.mark.slow
@pytest.fixture
def database() -> Database:
    return connect_to_the_real_thing()
```

```console
pytest -m "not slow"
```

Every test that reaches `database` is now marked `slow` — whether it requests it directly, through
another fixture, through `@pytest.mark.usefixtures`, or through `request.getfixturevalue`, whose
argument is read off the source even when it is a constant, an attribute or a loop variable rather
than a literal. Either decorator order works.

Any mark applies, with its arguments:

```python
@pytest.mark.skipif(shutil.which("docker") is None, reason="docker is required")
@pytest.fixture
def container() -> Iterator[Container]:
    with start_container() as running:
        yield running
```

When a fixture is overridden, the mark follows the definition that actually runs: an override that
replaces the fixture drops it, an override that requests the fixture it overrides keeps it.

### usefixtures

`usefixtures` keeps its own meaning instead of being copied onto the test: the named fixtures
become dependencies of the marked fixture, set up before it.

```python
@pytest.mark.usefixtures("clean_database")
@pytest.fixture
def api_client() -> Client:
    return Client()
```

### parametrize

`parametrize` is applied to every test that reaches the fixture. The fixture may consume the
parameter itself.

```python
@pytest.mark.parametrize("backend", ["memory", "disk"])
@pytest.fixture
def store(backend: str) -> Store:
    return Store(backend)
```

Each test using `store` now runs twice.

## Supported versions

Python 3.9 to 3.14, pytest 7.0 to 9.1, every combination exercised in CI.

## Development

```console
uv sync
make test
make lint
make matrix
```
