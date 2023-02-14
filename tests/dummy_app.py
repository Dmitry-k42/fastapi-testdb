from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase, Mapped, mapped_column
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, status

# For simplicity we are going to use SQLite.
# Path to the production database. It should not be created during the tests. We'll keep an eye on it.
PATH_TO_REAL_DB = '/tmp/fastapi_testdb_real_db.sqlite'
REAL_DSN = f'sqlite:///{PATH_TO_REAL_DB}'

# That's our database to be used in the tests
PATH_TO_TEST_DB = '/tmp/fastapi_testdb_test_db.sqlite'
TEST_DSN = f'sqlite:///{PATH_TO_TEST_DB}'


class BaseOrm(DeclarativeBase):
    pass


class UserDB(BaseOrm):
    __tablename__: str = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(index=True, unique=True)


class UserOut(BaseModel):
    id: int
    name: str

    class Config:
        orm_mode = True


def connect_db():
    # We must not to get here while testing
    return create_engine(REAL_DSN)


app = FastAPI()


@app.get('/users/{user_id}')
def get_user(
        user_id: int,
        engine: Engine = Depends(connect_db),
):
    session_type = sessionmaker(engine)
    with session_type() as session:
        session: Session
        user = session.get(UserDB, user_id)
        if not user:
            raise HTTPException(status.HTTP_404_NOT_FOUND)
        return UserOut.from_orm(user)
