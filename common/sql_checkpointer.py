from langchain.pydantic_v1 import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, LargeBinary, Table, MetaData, PrimaryKeyConstraint, select
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import URL
from sqlalchemy import Engine
from typing import Iterator, Optional, Any
from types import TracebackType
import pickle
from contextlib import AbstractContextManager, contextmanager
from langchain_core.runnables import RunnableConfig
from typing_extensions import Self

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointAt,
    CheckpointTuple,
    Serializable,
)


metadata = MetaData()

# Adjusting the column type from String (which defaults to VARCHAR(max)) to a specific length
checkpoints_table = Table(
    'checkpoints', metadata,
    Column('thread_id', String(255), primary_key=True),  # String(255) specifies the max length
    Column('thread_ts', String(255), primary_key=True),
    Column('parent_ts', String(255)),  # Optional: Specify length here if it's a commonly used field
    Column('checkpoint', LargeBinary),  # VARBINARY(max) is fine for non-indexed columns
    PrimaryKeyConstraint('thread_id', 'thread_ts')
)

class BaseCheckpointSaver(BaseModel):
    
    engine: Optional[Engine] = None
    Session: Optional[scoped_session] = None
    is_setup: bool = Field(default=False)
    session: Any = Field(default=None) 

    class Config:
        arbitrary_types_allowed = True

class SQLAlchemyCheckpointSaver(BaseCheckpointSaver, AbstractContextManager):
    
    def __init__(self, engine: Engine, *, serde: Optional[Serializable] = None, at: Optional[CheckpointAt] = None):
        # Call super with all expected fields by Pydantic
        super().__init__(serde=serde or pickle, at=at or CheckpointAt.END_OF_STEP, is_setup=False)
        self.engine = engine
        self.Session = scoped_session(sessionmaker(bind=self.engine))


    @classmethod
    def from_db_config(cls, db_config):
        db_url = URL.create(
            drivername=db_config['drivername'],
            username=db_config['username'],
            password=db_config['password'],
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['database'],
            query=db_config['query']
        )
        engine = create_engine(db_url)
        return cls(engine)
    
    def __enter__(self):
        self.session = self.Session()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type:
                self.session.rollback()
            else:
                self.session.commit()
        finally:
            self.Session.remove()
            self.session.close()

        
    def setup(self):
        if not self.is_setup:
            # Create all tables if they don't exist
            metadata.create_all(self.engine)
            self.is_setup = True

    def get(self, config: RunnableConfig) -> Optional[Checkpoint]:
        if value := self.get_tuple(config):
            return value['checkpoint']

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        print("SQLAlchemyCheckpointSaver.get_tuple properly called")
        with self.Session() as session:
            thread_id = config["configurable"].get("thread_id")
            thread_ts = config["configurable"].get("thread_ts")

            query = select(checkpoints_table)
            if thread_ts:
                query = query.where(
                    (checkpoints_table.c.thread_id == thread_id) &
                    (checkpoints_table.c.thread_ts == thread_ts)
                )
            else:
                query = query.where(
                    checkpoints_table.c.thread_id == thread_id
                ).order_by(checkpoints_table.c.thread_ts.desc()).limit(1)

            result = session.execute(query).fetchone()
            if result:
                # Handling both potential types of result objects
                if isinstance(result, tuple):
                    # Convert tuple to dictionary using column keys if result is a tuple
                    result = dict(zip(result.keys(), result))
                elif hasattr(result, '_mapping'):
                    # Convert SQLAlchemy RowProxy to dictionary directly if available
                    result = dict(result._mapping)

                return {
                    'config': config,
                    'checkpoint': pickle.loads(result['checkpoint']),
                    'additional_info': {
                        "thread_id": result['thread_id'],
                        "thread_ts": result['parent_ts'] if result['parent_ts'] else None
                    }
                }
            return None



    def list(self, config: RunnableConfig):
        with self.Session() as session:
            query = select(checkpoints_table).where(
                checkpoints_table.c.thread_id == config["configurable"]["thread_id"]
            ).order_by(checkpoints_table.c.thread_ts.desc())
            results = session.execute(query).fetchall()

            return [
                {
                    "configurable": {
                        "thread_id": result['thread_id'],
                        "thread_ts": result['thread_ts']
                    },
                    "checkpoint": pickle.loads(result['checkpoint']),
                    "additional_info": {
                        "thread_id": result['thread_id'],
                        "thread_ts": result['parent_ts'] or None
                    }
                }
                for result in results
            ]


    def put(self, config: RunnableConfig, checkpoint: Checkpoint):
        print("Attempting to connect with engine:", self.engine.url)  # Check the engine URL
        with self.Session() as session:
            print("Session started for put operation.")
            try:
                session.execute(
                    checkpoints_table.insert().values(
                        thread_id=config["configurable"]["thread_id"],
                        thread_ts=checkpoint["ts"],
                        parent_ts=config["configurable"].get("thread_ts"),
                        checkpoint=pickle.dumps(checkpoint)
                    )
                )
                session.commit()
                print("Data inserted and committed successfully.")
            except Exception as e:
                print("Error during database operation:", e)
                session.rollback()
                raise
            finally:
                print("Session closed after put operation.")
        return {
            "configurable": {
                "thread_id": config["configurable"]["thread_id"],
                "thread_ts": checkpoint["ts"]
            }
        }

    async def aget(self, config: RunnableConfig) -> Optional[Checkpoint]:
        return await asyncio.get_running_loop().run_in_executor(None, self.get, config)

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return await asyncio.get_running_loop().run_in_executor(None, self.get_tuple, config)

    async def alist(self, config: RunnableConfig) -> Iterator[CheckpointTuple]:
        return await asyncio.get_running_loop().run_in_executor(None, self.list, config)

    async def aput(self, config: RunnableConfig, checkpoint: Checkpoint) -> RunnableConfig:
        return await asyncio.get_running_loop().run_in_executor(None, self.put, config, checkpoint)

