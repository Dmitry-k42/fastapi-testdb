import os
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import DeclarativeBase

from fastapi_testdb import create_testdb, TestDB
from .dummy_app import app, BaseOrm, UserDB, PATH_TO_REAL_DB, PATH_TO_TEST_DB, TEST_DSN, connect_db


def test_dummy():
    assert isinstance(app, FastAPI)
    assert issubclass(BaseOrm, DeclarativeBase)
    assert issubclass(UserDB, DeclarativeBase)
    assert not os.path.exists(PATH_TO_REAL_DB)


def test_type_create():
    tdb1 = create_testdb(app, connect_db, BaseOrm, TEST_DSN)
    assert issubclass(tdb1, TestDB)
    assert tdb1.app == app
    assert tdb1.db_dependency == connect_db
    assert tdb1.orm_base_type == [BaseOrm]
    assert tdb1.dsn == TEST_DSN
    assert tdb1.create_engine_fn is None

    tmp_create_engine_fn = lambda: 0
    tdb2 = create_testdb(app, connect_db, BaseOrm, create_engine_fn=tmp_create_engine_fn)
    assert tdb1 is not tdb2
    assert tdb2.dsn is None
    assert tdb2.create_engine_fn is tmp_create_engine_fn

    with pytest.raises(ValueError) as e:
        create_testdb(app, connect_db, BaseOrm, dsn=None, create_engine_fn=None)
    assert e.value.args == ('You should provide either `dsn` or `create_engine_fn` to connect to the DB',)
    with pytest.raises(ValueError) as e:
        create_testdb(app, connect_db, BaseOrm, dsn=TEST_DSN, create_engine_fn=tmp_create_engine_fn)
    assert e.value.args == ('Parameters `dns` and `create_engine_fn` are mutually exclusive',)


def test_queries():
    # Real db doesn't exists in the beginning
    assert not os.path.exists(PATH_TO_REAL_DB)
    testdb = create_testdb(app, connect_db, BaseOrm, dsn=TEST_DSN)
    try:
        # First test
        with testdb() as tdb:
            # Since here a brand new test db has been created
            users = [
                {
                    'id': 1,
                    'name': 'Anna',
                },
                {
                    'id': 2,
                    'name': 'Brenda',
                },
            ]
            tdb.prefill_orm(UserDB, users)
            with TestClient(app) as client:
                res1 = client.get('/users/1')
                assert res1.status_code == 200
                assert res1.json() == {'id': 1, 'name': 'Anna'}
                res2 = client.get('/users/2')
                assert res2.status_code == 200
                assert res2.json() == {'id': 2, 'name': 'Brenda'}
                res3 = client.get('/users/3')
                assert res3.status_code == 404
        # Make sure we haven't created a real db accidentially during the first test
        assert not os.path.exists(PATH_TO_REAL_DB)
        assert os.path.exists(PATH_TO_TEST_DB)
    finally:
        os.unlink(PATH_TO_TEST_DB)
    assert not os.path.exists(PATH_TO_TEST_DB)
    try:
        # Second test
        with testdb() as tdb:
            # Here a new db was created, let's check it doesn't contain data from the previous test
            users = [
                {
                    'id': 3,
                    'name': 'Johnny',
                },
            ]
            tdb.prefill_orm(UserDB, users)
            with TestClient(app) as client:
                res1 = client.get('/users/1')
                assert res1.status_code == 404
                res2 = client.get('/users/2')
                assert res2.status_code == 404
                res3 = client.get('/users/3')
                assert res3.status_code == 200
                assert res3.json() == {'id': 3, 'name': 'Johnny'}
        # Make sure we haven't created a real db accidentially during the first test
        assert not os.path.exists(PATH_TO_REAL_DB)
        assert os.path.exists(PATH_TO_TEST_DB)
    finally:
        os.unlink(PATH_TO_TEST_DB)


def test_deco():
    testdb = create_testdb(app, connect_db, BaseOrm, dsn=TEST_DSN)

    @testdb.initdb
    def my_test_func(tdb):
        with TestClient(app) as client:
            users = [
                {
                    'id': 3,
                    'name': 'Johnny',
                },
            ]
            tdb.prefill_orm(UserDB, users)
            res1 = client.get('/users/1')
            assert res1.status_code == 404
            res2 = client.get('/users/3')
            assert res2.status_code == 200
            assert res2.json() == {'id': 3, 'name': 'Johnny'}

    try:
        my_test_func()
    finally:
        if os.path.exists(PATH_TO_TEST_DB):
            os.unlink(PATH_TO_TEST_DB)
