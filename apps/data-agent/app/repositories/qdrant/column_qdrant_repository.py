from aiohttp import payload
from openai.types import embedding
from qdrant_client import AsyncQdrantClient, models

from app.conf.app_config import app_config
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant

class ColumnQdrantRepository:
    collection_name:str = "data-agent-column"
    def __init__(self,client:AsyncQdrantClient):
        self.client = client
    async def ensure_collection(self):
        if not await self.client.collection_exists(collection_name=self.collection_name):
            await self._create_collection()

    async def reset_collection(self):
        """删除并重建集合。

        「重建知识」的语义是整体重建，不是增量追加。点位 id 用的是随机 uuid，
        直接 upsert 会让每次重建都产生一批重复点，越积越多；而且旧的 payload
        （里面带着字段取值样例）不会随数据变化更新，会把大模型带偏。
        """
        if await self.client.collection_exists(collection_name=self.collection_name):
            await self.client.delete_collection(collection_name=self.collection_name)
        await self._create_collection()

    async def _create_collection(self):
        await self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=app_config.qdrant.embedding_size,
                distance=models.Distance.COSINE,
            ),
        )
    async def upsert_column_embeddings(self,ids:list[str], embeddings:list[list[float]], payloads:list[ColumnInfoQdrant],batch_size:int=10):
        zipped = list(zip(ids, embeddings, payloads))
        for i in range(0, len(zipped), batch_size):
            batch_zipped = zipped[i:i+batch_size]
            points =[
                models.PointStruct(
                    id=id,
                    payload=payload,
                    vector=embedding,
                )
                for id, embedding, payload in batch_zipped
            ]
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )

    async def search(self, embedding: list[float], score_threshold: float = 0.6, limit: int = 5) -> list[
        ColumnInfoQdrant]:

        # 使用qdrant客户端对象查询指定向量的匹配结果
        results = await self.client.query_points(
            collection_name=self.collection_name,
            query=embedding,
            score_threshold=score_threshold,
            limit=limit
        )

        # 解析获取pointStruct的payload负载结果
        return [point.payload for point in results.points]














