import logging
import base64
import json
import threading
import asyncio
import time
from typing import Any, Dict, Iterator, AsyncIterator, Optional, Sequence, Tuple, List
from types import TracebackType
from abc import ABC, abstractmethod

from azure.cosmos import CosmosClient, PartitionKey, exceptions
from azure.cosmos.aio import CosmosClient as AsyncCosmosClient
from azure.cosmos.exceptions import CosmosBatchOperationError

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    ChannelVersions,
    get_checkpoint_id,
    SerializerProtocol,
)

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from contextlib import AbstractContextManager, AbstractAsyncContextManager

from langchain_core.runnables import RunnableConfig
from typing_extensions import Self

# Set up logging
logger = logging.getLogger(__name__)

# Define constants for consistent key usage
CONFIGURABLE = "configurable"
THREAD_ID = "thread_id"
CHECKPOINT_ID = "checkpoint_id"
PARENT_CHECKPOINT_ID = "parent_checkpoint_id"
METADATA = "metadata"
CHECKPOINT = "checkpoint"
CHECKPOINT_ENCODED = "checkpoint_encoded"
METADATA_ENCODED = "metadata_encoded"

class BaseCosmosDBSaver(ABC, BaseCheckpointSaver):
    """Abstract base class for CosmosDB Savers with shared logic."""

    serde: SerializerProtocol
    
    DEFAULT_INDEXING_POLICY = {
        "indexingMode": "consistent",
        "automatic": True,
        "includedPaths": [
            {
                "path": f"/{THREAD_ID}/?",
                "indexes": [
                    {
                        "kind": "Range",
                        "dataType": "String",
                        "precision": -1
                    },
                    {
                        "kind": "Range",
                        "dataType": "Number",
                        "precision": -1
                    }
                ]
            },
            {
                "path": f"/{CHECKPOINT_ID}/?",
                "indexes": [
                    {
                        "kind": "Range",
                        "dataType": "String",
                        "precision": -1
                    }
                ]
            },
            # Composite indexes for common query patterns
            {
                "path": "/*",
                "compositeIndexes": [
                    [
                        {"path": f"/{THREAD_ID}", "order": "ascending"},
                        {"path": f"/{CHECKPOINT_ID}", "order": "ascending"}
                    ]
                ]
            }
        ],
        "excludedPaths": [
            {"path": "/_etag/?"},
            # Exclude other unnecessary paths
        ]
    }

    def __init__(
        self,
        *,
        database_name: str,
        container_name: str,
        serde: Optional[SerializerProtocol] = None,
    ) -> None:
        super().__init__(serde=serde or JsonPlusSerializer())
        self.database_name = database_name
        self.container_name = container_name
        self.database = None
        self.container = None

    def setup(self) -> None:
        """
        Set up the CosmosDB container with necessary configurations.

        This method can be overridden to include any initialization logic,
        such as creating stored procedures or defining indexing policies.
        """
        # Implement any necessary initialization here
        pass
    
    def setup_indexing_policy(self) -> Dict[str, Any]:
        """Returns the default indexing policy. Can be overridden by subclasses."""
        return self.DEFAULT_INDEXING_POLICY
    
    @abstractmethod
    def upsert_item(self, doc: Dict[str, Any]) -> None:
        """Abstract method to upsert an item into the database."""
        pass
    
    @abstractmethod
    def upsert_items(self, docs: List[Dict[str, Any]]) -> None:
        """Abstract method to upsert multiple items into the database."""
        pass

    @abstractmethod
    def query_items(
        self,
        query: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Abstract method to query items from the database."""
        pass

    def _serialize_field(self, data: Any) -> Tuple[Any, bool]:
        """Helper method to serialize and conditionally encode data."""
        serialized = self.serde.dumps(data)
        encoded = False
        try:
            json.dumps(serialized)
            data_out = serialized
        except (TypeError, ValueError):
            if isinstance(serialized, str):
                serialized = serialized.encode('utf-8')
            data_out = base64.b64encode(serialized).decode('utf-8')
            encoded = True
        return data_out, encoded

    def _deserialize_field(self, doc: Dict[str, Any], field_name: str, encoded_flag_name: str) -> Any:
        """Helper method to deserialize a field from the document."""
        data = doc[field_name]
        encoded = doc.get(encoded_flag_name, False)
        if encoded:
            serialized = base64.b64decode(data.encode('utf-8'))
        else:
            serialized = data
            if isinstance(serialized, str):
                serialized = serialized.encode('utf-8')
        return self.serde.loads(serialized)

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """
        Retrieve a checkpoint tuple from the database.

        Args:
            config (RunnableConfig): The runnable configuration containing 'thread_id' and optional 'checkpoint_id'.

        Returns:
            Optional[CheckpointTuple]: A CheckpointTuple if found, else None.

        Raises:
            ValueError: If 'thread_id' is not provided in the config.

        Example:
            >>> config = {"configurable": {"thread_id": "thread1"}}
            >>> checkpoint_tuple = saver.get_tuple(config)
        """
        thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
        if not thread_id:
            raise ValueError(f"'{THREAD_ID}' is required in config['{CONFIGURABLE}']")
        checkpoint_id = get_checkpoint_id(config)
        parameters = [{"name": "@thread_id", "value": thread_id}]
        if checkpoint_id:
            query = (
                "SELECT * FROM c WHERE c.thread_id = @thread_id AND IS_DEFINED(c.checkpoint) "
                "AND c.checkpoint_id = @checkpoint_id"
            )
            parameters.append({"name": "@checkpoint_id", "value": checkpoint_id})
        else:
            query = (
                "SELECT * FROM c WHERE c.thread_id = @thread_id AND IS_DEFINED(c.checkpoint) "
                "ORDER BY c.checkpoint_id DESC OFFSET 0 LIMIT 1"
            )

        items = self.query_items(query=query, parameters=parameters)
        results = list(items)
        if results:
            doc = results[0]
            checkpoint = self._deserialize_field(doc, CHECKPOINT, CHECKPOINT_ENCODED)
            metadata = self._deserialize_field(doc, METADATA, METADATA_ENCODED)
            parent_checkpoint_id = doc.get(PARENT_CHECKPOINT_ID)
            parent_config = (
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                        CHECKPOINT_ID: parent_checkpoint_id,
                    }
                }
                if parent_checkpoint_id
                else None
            )
            return CheckpointTuple(
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                        CHECKPOINT_ID: doc[CHECKPOINT_ID],
                    }
                },
                checkpoint,
                metadata,
                parent_config,
            )
        else:
            return None

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """
        List checkpoints from the database.

        Args:
            config (Optional[RunnableConfig]): Optional runnable configuration.
            filter (Optional[Dict[str, Any]]): Optional filter for metadata.
            before (Optional[RunnableConfig]): Optional configuration to list checkpoints before a certain point.
            limit (Optional[int]): Optional limit on the number of checkpoints to return.

        Returns:
            Iterator[CheckpointTuple]: An iterator of CheckpointTuples.
        """
        parameters = []
        conditions = []
        if config is not None:
            thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
            if not thread_id:
                raise ValueError(f"'{THREAD_ID}' is required in config['{CONFIGURABLE}']")
            conditions.append("c.thread_id = @thread_id")
            parameters.append({"name": "@thread_id", "value": thread_id})

        if filter:
            for key, value in filter.items():
                conditions.append(f"c.metadata.{key} = @{key}")
                parameters.append({"name": f"@{key}", "value": value})

        if before is not None:
            before_checkpoint_id = before.get(CONFIGURABLE, {}).get(CHECKPOINT_ID)
            if before_checkpoint_id:
                conditions.append("c.checkpoint_id < @before_checkpoint_id")
                parameters.append({"name": "@before_checkpoint_id", "value": before_checkpoint_id})

        conditions.append("IS_DEFINED(c.checkpoint)")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        order_clause = "ORDER BY c.checkpoint_id DESC"
        limit_clause = f"OFFSET 0 LIMIT {limit}" if limit else ""

        query = f"SELECT * FROM c WHERE {where_clause} {order_clause} {limit_clause}"

        items = self.query_items(query=query, parameters=parameters)
        for doc in items:
            checkpoint = self._deserialize_field(doc, CHECKPOINT, CHECKPOINT_ENCODED)
            metadata = self._deserialize_field(doc, METADATA, METADATA_ENCODED)
            parent_checkpoint_id = doc.get(PARENT_CHECKPOINT_ID)
            parent_config = (
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                        CHECKPOINT_ID: parent_checkpoint_id,
                    }
                }
                if parent_checkpoint_id
                else None
            )
            yield CheckpointTuple(
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                        CHECKPOINT_ID: doc[CHECKPOINT_ID],
                    }
                },
                checkpoint,
                metadata,
                parent_config,
            )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """
        Save a checkpoint to the database.

        Args:
            config (RunnableConfig): The runnable configuration.
            checkpoint (Checkpoint): The checkpoint data to save.
            metadata (CheckpointMetadata): Metadata associated with the checkpoint.
            new_versions (ChannelVersions): New channel versions.

        Returns:
            RunnableConfig: Updated runnable configuration.

        Raises:
            ValueError: If required fields are missing in the config or checkpoint.
        """
        thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
        if not thread_id:
            raise ValueError(f"'{THREAD_ID}' is required in config['{CONFIGURABLE}']")
        checkpoint_id = checkpoint.get("id")
        if not checkpoint_id:
            raise ValueError("Checkpoint must have an 'id' field")

        # Use checkpoint_id as the document ID to ensure uniqueness
        doc_id = checkpoint_id

        # Serialize checkpoint and metadata
        checkpoint_data, checkpoint_encoded = self._serialize_field(checkpoint)
        metadata_data, metadata_encoded = self._serialize_field(metadata)

        doc = {
            "id": doc_id,
            THREAD_ID: thread_id,
            CHECKPOINT_ID: checkpoint_id,
            CHECKPOINT: checkpoint_data,
            METADATA: metadata_data,
            CHECKPOINT_ENCODED: checkpoint_encoded,
            METADATA_ENCODED: metadata_encoded,
        }
        parent_checkpoint_id = config.get(CONFIGURABLE, {}).get(CHECKPOINT_ID)
        if parent_checkpoint_id:
            doc[PARENT_CHECKPOINT_ID] = parent_checkpoint_id

        self.upsert_item(doc)

        return {
            CONFIGURABLE: {
                THREAD_ID: thread_id,
                CHECKPOINT_ID: checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """
        Store intermediate writes linked to a checkpoint.

        Args:
            config (RunnableConfig): The runnable configuration.
            writes (Sequence[Tuple[str, Any]]): A sequence of channel and value tuples.
            task_id (str): The task identifier.

        Raises:
            ValueError: If required fields are missing in the config.
        """
        thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
        checkpoint_id = config.get(CONFIGURABLE, {}).get(CHECKPOINT_ID)
        if not thread_id or not checkpoint_id:
            raise ValueError(f"Both '{THREAD_ID}' and '{CHECKPOINT_ID}' are required in config['{CONFIGURABLE}']")

        # Use batch operations for efficiency
        docs = []
        for idx, (channel, value) in enumerate(writes):
            doc_id = f"{checkpoint_id}_{task_id}_{idx}"

            # Use the helper method to serialize the value
            value_data, value_encoded = self._serialize_field(value)

            doc = {
                "id": doc_id,
                THREAD_ID: thread_id,
                CHECKPOINT_ID: checkpoint_id,
                "task_id": task_id,
                "idx": idx,
                "channel": channel,
                "type": type(value).__name__,
                "value": value_data,
                "value_encoded": value_encoded,
            }
            docs.append(doc)

        self.upsert_items(docs)



class CosmosDBSaver(BaseCosmosDBSaver, AbstractContextManager):
    """
    A checkpoint saver that stores checkpoints in an Azure Cosmos DB database.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        key: str,
        database_name: str,
        container_name: str,
        serde: Optional[SerializerProtocol] = None,
    ) -> None:
        super().__init__(
            database_name=database_name,
            container_name=container_name,
            serde=serde
        )
        self.client = CosmosClient(endpoint, credential=key)
        self.lock = threading.Lock()
        self._initialized = False  # Track if setup was run
        
        
    def __enter__(self) -> Self:
        self.setup()
        return self
    
    
    def setup(self):
        """
        Initializes the database and container if not already done.
        You must call this method if you're not using the `with` statement.
        """
        if not self._initialized:
            try:
                self.database = self.client.create_database_if_not_exists(self.database_name)
                logger.debug(f"Database '{self.database_name}' is ready.")
            except exceptions.CosmosHttpResponseError as e:
                logger.error(f"Error creating database '{self.database_name}': {e}")
                raise
            try:
                self.container = self.database.create_container_if_not_exists(
                    id=self.container_name,
                    partition_key=PartitionKey(path=f"/{THREAD_ID}"),
                    indexing_policy=self.setup_indexing_policy()
                )
                logger.debug(f"Container '{self.container_name}' is ready.")
            except exceptions.CosmosHttpResponseError as e:
                logger.error(f"Error creating container '{self.container_name}': {e}")
                raise

            self._initialized = True
            # If there's any additional setup logic, add it here
            self.setup_additional()
            

    def setup_additional(self):
        # Implement any additional setup logic if necessary
        pass    
            

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        self.close()
    
    def close(self):
        """
        Cleans up resources. Call this if you're not using 'with' statement.
        """
        # Client does not need explicit close in synchronous mode, but if you had resources,
        # this is where you'd close them. Placeholder for future resource cleanup.
        pass

    def upsert_item(self, doc: Dict[str, Any]) -> None:
        """Upsert an item into the database with retry logic."""
        if not self._initialized:
            raise RuntimeError("CosmosDBSaver not initialized. Call setup() first.")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self.lock:
                    self.container.upsert_item(doc)
                break
            except exceptions.CosmosHttpResponseError as e:
                if attempt < max_retries - 1 and e.status_code in (429, 503):
                    wait_time = 2 ** attempt
                    logger.warning(f"Retrying upsert_item in {wait_time} seconds due to error: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error upserting item after {max_retries} attempts: {e}")
                    raise

                    
    def upsert_items(self, docs: List[Dict[str, Any]]) -> None:
        """Upsert multiple items individually."""
        if not self._initialized:
            raise RuntimeError("CosmosDBSaver not initialized. Call setup() first.")

        max_retries = 3
        for doc in docs:
            for attempt in range(max_retries):
                try:
                    with self.lock:
                        self.container.upsert_item(doc)
                    break  # Exit the retry loop on success
                except exceptions.CosmosHttpResponseError as e:
                    if attempt < max_retries - 1 and e.status_code in (429, 503):
                        wait_time = 2 ** attempt
                        logger.warning(f"Retrying upsert_item in {wait_time} seconds due to error: {e}")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Error upserting item after {max_retries} attempts: {e}")
                        raise
                    
                    
    def query_items(
        self,
        query: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Query items from the database with retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self.lock:
                    items = self.container.query_items(
                        query=query,
                        parameters=parameters,
                        enable_cross_partition_query=True
                    )
                return items
            except exceptions.CosmosHttpResponseError as e:
                if attempt < max_retries - 1 and e.status_code in (429, 503):
                    wait_time = 2 ** attempt
                    logger.warning(f"Retrying query_items in {wait_time} seconds due to error: {e}")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error querying items after {max_retries} attempts: {e}")
                    raise

class AsyncCosmosDBSaver(BaseCosmosDBSaver, AbstractAsyncContextManager):
    """
    An asynchronous checkpoint saver that stores checkpoints in an Azure Cosmos DB database.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        key: str,
        database_name: str,
        container_name: str,
        serde: Optional[SerializerProtocol] = None,
    ) -> None:
        super().__init__(
            database_name=database_name,
            container_name=container_name,
            serde=serde
        )
        self.client = AsyncCosmosClient(endpoint, credential=key)
        self.lock = asyncio.Lock()
        self._initialized = False  # Track if setup was run
        
    async def __aenter__(self) -> Self:
        await self.setup()
        return self
    
    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> Optional[bool]:
        await self.close()
        
        
    async def setup(self):
        """
        Initializes the database and container if not already done.
        Call this if not using 'async with'.
        """
        if not self._initialized:
            try:
                self.database = await self.client.create_database_if_not_exists(self.database_name)
                logger.debug(f"Database '{self.database_name}' is ready.")
            except exceptions.CosmosHttpResponseError as e:
                logger.error(f"Error creating database '{self.database_name}': {e}")
                raise
            try:
                self.container = await self.database.create_container_if_not_exists(
                    id=self.container_name,
                    partition_key=PartitionKey(path=f"/{THREAD_ID}"),
                    indexing_policy=self.setup_indexing_policy()
                )
                logger.debug(f"Container '{self.container_name}' is ready.")
            except exceptions.CosmosHttpResponseError as e:
                logger.error(f"Error creating container '{self.container_name}': {e}")
                raise

            self._initialized = True
            # If there's any additional setup logic, add it here
            self.setup_additional()

    def setup_additional(self):
        # Implement any additional setup logic if necessary
        pass

    async def close(self):
        """
        Cleans up resources. Call this if you're not using 'async with'.
        """
        # Close the asynchronous client
        await self.client.close()


    async def upsert_item(self, doc: Dict[str, Any]) -> None:
        """Upsert an item into the database asynchronously with retry logic."""
        if not self._initialized:
            raise RuntimeError("AsyncCosmosDBSaver not initialized. Call setup() first.")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with self.lock:
                    await self.container.upsert_item(doc)
                break
            except exceptions.CosmosHttpResponseError as e:
                if attempt < max_retries - 1 and e.status_code in (429, 503):
                    wait_time = 2 ** attempt
                    logger.warning(f"Retrying upsert_item in {wait_time} seconds due to error: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Error upserting item after {max_retries} attempts: {e}")
                    raise

    async def upsert_items(self, docs: List[Dict[str, Any]]) -> None:
            """Asynchronously upsert multiple items individually."""
            if not self._initialized:
                raise RuntimeError("AsyncCosmosDBSaver not initialized. Call setup() first.")

            max_retries = 3
            for doc in docs:
                for attempt in range(max_retries):
                    try:
                        async with self.lock:
                            await self.container.upsert_item(doc)
                        break  # Exit the retry loop on success
                    except exceptions.CosmosHttpResponseError as e:
                        if attempt < max_retries - 1 and e.status_code in (429, 503):
                            wait_time = 2 ** attempt
                            logger.warning(f"Retrying upsert_item in {wait_time} seconds due to error: {e}")
                            await asyncio.sleep(wait_time)
                        else:
                            logger.error(f"Error upserting item after {max_retries} attempts: {e}")
                            raise

    def query_items(
        self,
        query: str,
        parameters: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Query items from the database asynchronously with retry logic."""
        if not self._initialized:
            raise RuntimeError("AsyncCosmosDBSaver not initialized. Call setup() first.")

        async def fetch_items():
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    async with self.lock:
                        items = self.container.query_items(
                            query=query,
                            parameters=parameters,
                        )
                    async for item in items:
                        yield item
                    break
                except exceptions.CosmosHttpResponseError as e:
                    if attempt < max_retries - 1 and e.status_code in (429, 503):
                        wait_time = 2 ** attempt
                        logger.warning(f"Retrying query_items in {wait_time} seconds due to error: {e}")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"Error querying items after {max_retries} attempts: {e}")
                        raise
        return fetch_items()

    # Implement the asynchronous versions of the checkpoint methods
    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Asynchronously retrieve a checkpoint tuple from the database."""
        if not self._initialized:
            raise RuntimeError("AsyncCosmosDBSaver not initialized. Call setup() first.")
        
        thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
        if not thread_id:
            raise ValueError(f"'{THREAD_ID}' is required in config['{CONFIGURABLE}']")
        checkpoint_id = get_checkpoint_id(config)
        parameters = [{"name": "@thread_id", "value": thread_id}]
        if checkpoint_id:
            query = (
                "SELECT * FROM c WHERE c.thread_id = @thread_id AND IS_DEFINED(c.checkpoint) "
                "AND c.checkpoint_id = @checkpoint_id"
            )
            parameters.append({"name": "@checkpoint_id", "value": checkpoint_id})
        else:
            query = (
                "SELECT * FROM c WHERE c.thread_id = @thread_id AND IS_DEFINED(c.checkpoint) "
                "ORDER BY c.checkpoint_id DESC OFFSET 0 LIMIT 1"
            )

        items_iterable = self.query_items(query=query, parameters=parameters)

        results = []
        async for item in items_iterable:
            results.append(item)

        if results:
            doc = results[0]
            checkpoint = self._deserialize_field(doc, CHECKPOINT, CHECKPOINT_ENCODED)
            metadata = self._deserialize_field(doc, METADATA, METADATA_ENCODED)
            parent_checkpoint_id = doc.get(PARENT_CHECKPOINT_ID)
            parent_config = (
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                        CHECKPOINT_ID: parent_checkpoint_id,
                    }
                }
                if parent_checkpoint_id
                else None
            )
            return CheckpointTuple(
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                        CHECKPOINT_ID: doc[CHECKPOINT_ID],
                    }
                },
                checkpoint,
                metadata,
                parent_config,
            )
        else:
            return None


    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Asynchronously list checkpoints from the database."""
        if not self._initialized:
            raise RuntimeError("AsyncCosmosDBSaver not initialized. Call setup() first.")
        
        parameters = []
        conditions = []
        if config is not None:
            thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
            if not thread_id:
                raise ValueError(f"'{THREAD_ID}' is required in config['{CONFIGURABLE}']")
            conditions.append("c.thread_id = @thread_id")
            parameters.append({"name": "@thread_id", "value": thread_id})

        if filter:
            for key, value in filter.items():
                conditions.append(f"c.metadata.{key} = @{key}")
                parameters.append({"name": f"@{key}", "value": value})

        if before is not None:
            before_checkpoint_id = before.get(CONFIGURABLE, {}).get(CHECKPOINT_ID)
            if before_checkpoint_id:
                conditions.append("c.checkpoint_id < @before_checkpoint_id")
                parameters.append({"name": "@before_checkpoint_id", "value": before_checkpoint_id})

        conditions.append("IS_DEFINED(c.checkpoint)")

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        order_clause = "ORDER BY c.checkpoint_id DESC"
        limit_clause = f"OFFSET 0 LIMIT {limit}" if limit else ""

        query = f"SELECT * FROM c WHERE {where_clause} {order_clause} {limit_clause}"

        items_iterable = self.query_items(query=query, parameters=parameters)

        async for doc in items_iterable:
            checkpoint = self._deserialize_field(doc, CHECKPOINT, CHECKPOINT_ENCODED)
            metadata = self._deserialize_field(doc, METADATA, METADATA_ENCODED)
            parent_checkpoint_id = doc.get(PARENT_CHECKPOINT_ID)
            parent_config = (
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                        CHECKPOINT_ID: parent_checkpoint_id,
                    }
                }
                if parent_checkpoint_id
                else None
            )
            yield CheckpointTuple(
                {
                    CONFIGURABLE: {
                        THREAD_ID: doc[THREAD_ID],
                        CHECKPOINT_ID: doc[CHECKPOINT_ID],
                    }
                },
                checkpoint,
                metadata,
                parent_config,
            )

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Asynchronously save a checkpoint to the database."""
        if not self._initialized:
            raise RuntimeError("AsyncCosmosDBSaver not initialized. Call setup() first.")
        
        thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
        if not thread_id:
            raise ValueError(f"'{THREAD_ID}' is required in config['{CONFIGURABLE}']")
        checkpoint_id = checkpoint.get("id")
        if not checkpoint_id:
            raise ValueError("Checkpoint must have an 'id' field")

        doc_id = checkpoint_id

        # Serialize checkpoint and metadata
        checkpoint_data, checkpoint_encoded = self._serialize_field(checkpoint)
        metadata_data, metadata_encoded = self._serialize_field(metadata)

        doc = {
            "id": doc_id,
            THREAD_ID: thread_id,
            CHECKPOINT_ID: checkpoint_id,
            CHECKPOINT: checkpoint_data,
            METADATA: metadata_data,
            CHECKPOINT_ENCODED: checkpoint_encoded,
            METADATA_ENCODED: metadata_encoded,
        }
        parent_checkpoint_id = config.get(CONFIGURABLE, {}).get(CHECKPOINT_ID)
        if parent_checkpoint_id:
            doc[PARENT_CHECKPOINT_ID] = parent_checkpoint_id

        await self.upsert_item(doc)

        return {
            CONFIGURABLE: {
                THREAD_ID: thread_id,
                CHECKPOINT_ID: checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Asynchronously store intermediate writes linked to a checkpoint."""
        if not self._initialized:
            raise RuntimeError("AsyncCosmosDBSaver not initialized. Call setup() first.")
        
        thread_id = config.get(CONFIGURABLE, {}).get(THREAD_ID)
        checkpoint_id = config.get(CONFIGURABLE, {}).get(CHECKPOINT_ID)
        if not thread_id or not checkpoint_id:
            raise ValueError(f"Both '{THREAD_ID}' and '{CHECKPOINT_ID}' are required in config['{CONFIGURABLE}']")

        # Use batch operations for efficiency
        docs = []
        for idx, (channel, value) in enumerate(writes):
            doc_id = f"{checkpoint_id}_{task_id}_{idx}"

            # Use the helper method to serialize the value
            value_data, value_encoded = self._serialize_field(value)

            doc = {
                "id": doc_id,
                THREAD_ID: thread_id,
                CHECKPOINT_ID: checkpoint_id,
                "task_id": task_id,
                "idx": idx,
                "channel": channel,
                "type": type(value).__name__,
                "value": value_data,
                "value_encoded": value_encoded,
            }
            docs.append(doc)

        await self.upsert_items(docs)

