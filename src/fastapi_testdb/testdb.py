"""TestDB module contains class `TestDB` to be used for make your DB tests repeatable."""

from typing import Optional, Callable, Union, Type, Iterable, Dict, Any

from fastapi import FastAPI
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

OrmBase = Type[DeclarativeBase]


class TestDB:
    """TestDB class

    Let's say you have a FastAPI instance `app` with dependency `connect_db` to get a connection
    to your database. Your SQLAlchemy ORM base class is `BaseOrm`. Common usage of TestDB for having
    repeatable tests:

    1) First create a class by call `create_testdb`:

    ```
    from fastapi_testdb import create_testdb

    testdb = create_testdb(app, connect_db, BaseOrm, dsn='sqlite:////tmp/your-testdb.sqlite')
    ```

    `testdb` is your new class type targeted to connect to the test database. In this case it is
    an SQLite DB, but you can use other databases - PostgreSQL, MySQL and everything that
    supported by SQLAlchemy.

    2) Now you can use the new class for creating reproducible DB state:

    ```
    def test_yourtestfunc():
        with testdb() as tdb:
            # In this `with` statement a new DB was created and all the tables from
            # `BaseOrm.metadata` were initiated. Now you have a completely empty tables in the DB.
            # Do your test here:
            ...
    ```

    It is also possible to use this as a decorator:
    ```
    @testdb.initdb
    def test_yourtestfunc(tdb):
        # A new DB is ready for testing. Do your test below
        ...
    ```

    A new DB has created empty. If you have to fill tables with some data, you can use
    `prefill_orm` method. For example, let you have an ORM class for users:

    ```
    class UserDB(BaseOrm):
        id: Mapped[int] = mapped_column(primary_key=True, index=True)
        name: Mapped[str] = mapped_column(index=True, unique=True)
    ```

    To have some content on testing, call the method `prefill_orm`:

    ```
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
    """
    app: FastAPI
    db_dependency: Callable
    orm_base_type: Union[OrmBase, Iterable[OrmBase]]
    dsn: Optional[str] = None
    create_engine_fn: Optional[Callable] = None

    def __init__(self) -> None:
        try:
            self._prev_override = self.app.dependency_overrides[self.db_dependency]
        except KeyError:
            self._prev_override = None
        self.engine = None

    def session(self) -> Session:
        """Create a new ORM session in the test database."""
        session_type = sessionmaker(self.engine)
        return session_type()

    def prefill_orm(self, type_: Type[DeclarativeBase], items: Iterable[Dict[str, Any]]) -> None:
        """Fill the ORM table with provided data.

        :param type_: your ORM class that represents the rows in the table you want to fill up.
        :param items: the data to be inserted represented as a list of dictionaries.
            Each dictionary has columns as keys and column values as dict values.
        """
        with self.session() as conn:
            for item in items:
                i = type_(**item)
                conn.add(i)
            conn.commit()

    @classmethod
    def initdb(cls, test_function: Callable) -> Callable:
        """Decorate a test function, create a new empty database according to your ORM models."""
        def inner_deco():
            with cls() as tdb:
                return test_function(tdb=tdb)
        return inner_deco

    def __enter__(self) -> "TestDB":
        # We want to store db_dependency as a function, but after instantiation
        # Python converts our class-level callable attribute to a bound method.
        # This is a key Python feature. Sadly it is not actually we want and
        # to keep real function we do access to it through a magic __class__
        self.app.dependency_overrides[self.__class__.db_dependency] = self._create_engine
        self.engine = self._create_engine()
        with self.engine.begin():
            for orm_base_type in self.orm_base_type:
                orm_base_type.metadata.drop_all(self.engine)
            for orm_base_type in self.orm_base_type:
                orm_base_type.metadata.create_all(self.engine)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.engine = None
        if self._prev_override is not None:
            self.app.dependency_overrides[self.__class__.db_dependency] = self._prev_override
            self._prev_override = None
        else:
            del self.app.dependency_overrides[self.__class__.db_dependency]

    def _create_engine(self) -> Engine:
        if self.engine is not None:
            return self.engine
        if self.create_engine_fn is not None:
            self.engine = self.create_engine_fn()
        self.engine = create_engine(self.dsn)
        return self.engine


_n_created_types = 0  # pylint: disable=invalid-name


def create_testdb(
        app: FastAPI,
        db_dependency: Callable,
        orm_base_type: Union[OrmBase, Iterable[OrmBase]],
        dsn: Optional[str] = None,
        create_engine_fn: Optional[Callable] = None,
) -> Type[TestDB]:
    """Create a new `TestDB` class that to be used in the tests. The method defines
    crucial parameters of your app. They must be used during creating reproducible databases.

    :param app: Your FastAPI instance.
    :param db_dependency: A dependency function where you create a database connection.
        It should be overriden to preserve your real database from erasing while tests.
        That's why we require it to be defined here.
    :param orm_base_type: Your base ORM class from which you derive all your rest ORM clases.
        You can set a list of classes if you need.
    :param dsn: Optional. DSN to the test database. Must be None if `create_engine_fn`
        is specified.
    :param create_engine_fn: Optional. When you need to create custom SQLAlchemy engine you
        can use this parameter to set your function which do all neccessary work. In this case
        parameter `dsn` must be None.
    :return:
    """
    if dsn is None and create_engine_fn is None:
        raise ValueError('You should provide either `dsn` or `create_engine_fn` '
                         'to connect to the DB')
    if dsn is not None and create_engine_fn is not None:
        raise ValueError('Parameters `dns` and `create_engine_fn` are mutually exclusive')
    global _n_created_types  # pylint: disable=global-statement, disable=invalid-name
    _n_created_types += 1
    testdb_type = type(f'{TestDB.__class__.__class__}_{_n_created_types}', (TestDB,), {})
    testdb_type.app = app
    testdb_type.db_dependency = db_dependency
    if isinstance(orm_base_type, Iterable):
        testdb_type.orm_base_type = list(orm_base_type)
    else:
        testdb_type.orm_base_type = [orm_base_type]
    testdb_type.dsn = dsn
    testdb_type.create_engine_fn = create_engine_fn
    # noinspection PyTypeChecker
    return testdb_type
