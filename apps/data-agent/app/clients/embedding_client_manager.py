from typing import  Optional
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from app.conf.app_config import EmbeddingConfig, app_config

class EmbeddedClientManager:
    def __init__(self,config:EmbeddingConfig):
        self.config = config
        self.client:Optional[HuggingFaceEndpointEmbeddings] = None
    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"
    def init(self):
        self.client = HuggingFaceEndpointEmbeddings(model=self._get_url())

embedding_client_manager=EmbeddedClientManager(app_config.embedding)

if __name__=="__main__":
    client = EmbeddedClientManager(app_config.embedding)
    client.init()
    query = client.client.embed_query("hello world")
    print(len(query))
    print(query)