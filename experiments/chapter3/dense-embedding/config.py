"""稠密向量服务（实验 3-4）配置。

集中管理服务端参数（端口）、嵌入模型（默认 BAAI/bge-m3）与两种 ANN
索引后端（HNSW 图索引 / ANNOY 树索引）的超参数，均可用环境变量覆盖。
"""

import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

class IndexType(Enum):
    """Supported index types."""
    ANNOY = "annoy"
    HNSW = "hnsw"

@dataclass
class ServiceConfig:
    """Service configuration."""
    # Server settings
    host: str = "0.0.0.0"
    port: int = 4240  # Default port for dense embedding service
    
    # Model settings
    model_name: str = "BAAI/bge-m3"
    use_fp16: bool = True
    max_seq_length: int = 8192  # Increased to match HARD_LIMIT in chunking
    
    # Index settings
    index_type: IndexType = IndexType.HNSW
    max_documents: int = 100000
    
    # HNSW specific settings
    hnsw_ef_construction: int = 200
    hnsw_M: int = 16
    hnsw_ef_search: int = 50
    hnsw_space: str = "cosine"
    
    # Annoy specific settings
    annoy_n_trees: int = 50
    annoy_metric: str = "angular"
    
    # Logging settings
    log_level: str = "INFO"
    debug: bool = False
    show_embeddings: bool = False
    
    @classmethod
    def from_env(cls):
        """Create config from environment variables."""
        config = cls()
        
        # Override with environment variables if present
        if os.getenv("DENSE_PORT"):
            config.port = int(os.getenv("DENSE_PORT"))
        if os.getenv("DENSE_HOST"):
            config.host = os.getenv("DENSE_HOST")
        if os.getenv("DENSE_MODEL"):
            config.model_name = os.getenv("DENSE_MODEL")
        if os.getenv("DEBUG"):
            config.debug = os.getenv("DEBUG").lower() == "true"
            
        return config