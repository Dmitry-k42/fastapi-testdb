# fastapi-testdb

[FastAPI](https://https://fastapi.tiangolo.com/) is a cool framework for building
fast and reliable API. It provides various tools to create an app you want. Also
it has convenient way to cover the code with tests. Read the articles for more
details [Testing](https://fastapi.tiangolo.com/tutorial/testing/) and
[Testing a Database](https://fastapi.tiangolo.com/advanced/testing-database/).
It covers the most aspects of testing, but sadly one important thing was left
behind scenes. You have to recreate the database every time before run each test
to make tests *reproducible*, otherwise be ready to get unpredictible results
after every test run.

This package helps you to make database tests reproducible.

## Installation

```shell
pip install fastapi-testdb
```

## Usage

Let's say you have a FastAPI instance `app` with dependency `connect_db` to get a connection
to your database. Your SQLAlchemy ORM base class is `BaseOrm`. Common usage of TestDB for having
repeatable tests:

1) First create a class by call `create_testdb`:

    ```python
    from fastapi_testdb import create_testdb

    testdb = create_testdb(app, connect_db, BaseOrm, dsn='sqlite:////tmp/your-testdb.sqlite')
    ```

    `testdb` is your new class type targeted to connect to the test database. In this case it is
    an SQLite DB, but you can use other databases - PostgreSQL, MySQL and everything that
    supported by SQLAlchemy.
    
    You have to pass `connect_db` because this dependecy must be replaced on a test run for not
    to harm you real database.

    `BaseOrm` will be used to get metadata when the SQL tables create.

3) Now you can use the new class for creating reproducible DB state:

    ```python
    def test_yourtestfunc():
        with testdb() as tdb:
            # In this `with` statement a new DB was created and all the tables from
            # `BaseOrm.metadata` were initiated. Now you have a completely empty tables in the DB.
            # Do your test here:
            ...
    ```

### Usage as a decorator
It is also possible to use this as a decorator:

```python
@testdb.initdb
def test_yourtestfunc(tdb):
    # A new DB is ready for testing. Do your test below
    ...
```

### Insert test data

A new DB has created empty. If you have to fill tables with some data, you can use
`prefill_orm` method. For example, let you have an ORM class for users:

```python
class UserDB(BaseOrm):
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(index=True, unique=True)
```

To have some content on testing, call the method `prefill_orm`:

```python
@testdb.initdb
def test_yourtestfunc(tdb):
    users_fixture = [
        {"id": 1, "name": "Bob"},
        {"id": 2, "name": "Henry"},
    ]
    tdb.prefill_orm(UserDB, users_fixture)

    # Now you have your users in the table:
    with TestClient(app) as client:
        client = app.get('/user/1')
        assert client.status_code == 200
```

## Contribution

You are welcome to make contribution and proposals for improvement!
