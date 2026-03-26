import os
import logging
import json
from typing import List, Optional
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BedrockEmbeddingClient:
    """AWS Bedrock client for Titan v2 embeddings."""
    
    def __init__(self):
        self.aws_access_key = os.getenv("accesskey")
        self.aws_secret_key = os.getenv("secretaccesskey")
        self.aws_region = os.getenv("awsregion")
        self.model_id = os.getenv("bedrockmodel")
        
        if not all([self.aws_access_key, self.aws_secret_key]):
            raise ValueError("[BEDROCK_ERR] AWS credentials not set")
        
        try:
            self.client = boto3.client(
                service_name='bedrock-runtime',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.aws_region
            )
            logger.info(f"[BEDROCK_OK] Connected to {self.model_id}")
        except Exception as e:
            logger.error(f"[BEDROCK_ERR] Initialization failed: {e}")
            raise
    
    def normalize_text(self, text: str) -> str:
        """
        Normalize text for consistent embeddings.
        - NFKC normalization
        - Lowercase
        - Strip extra whitespace
        """
        import unicodedata
        text = unicodedata.normalize('NFKC', text)
        text = text.lower().strip()
        text = ' '.join(text.split())  # Collapse multiple spaces
        return text
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate a 1024-dim embedding for a single text.
        
        Args:
            text: Input text to embed
        
        Returns:
            List of 1024 floats, or None on failure
        """
        try:
            normalized = self.normalize_text(text)
            
            body = json.dumps({
                "inputText": normalized,
                "dimensions": 1024,
                "normalize": True
            })
            
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=body,
                contentType='application/json',
                accept='application/json'
            )
            
            response_body = json.loads(response["body"].read().decode())
            embedding = response_body.get('embedding')
            
            if not embedding or len(embedding) != 1024:
                logger.error(f"[EMBEDDING_ERR] Invalid embedding dimension: {len(embedding) if embedding else 0}")
                return None
            
            logger.info(f"[EMBEDDING_OK] Generated 1024-dim vector")
            return embedding
            
        except (BotoCoreError, ClientError) as e:
            logger.error(f"[EMBEDDING_ERR] AWS error: {e}")
            return None
        except Exception as e:
            logger.error(f"[EMBEDDING_ERR] Unexpected error: {e}")
            return None
    
    def generate_batch_embeddings(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of input texts
        
        Returns:
            List of embeddings (same order as input)
        """
        embeddings = []
        for idx, text in enumerate(texts):
            logger.info(f"[BATCH] Processing {idx+1}/{len(texts)}")
            embedding = self.generate_embedding(text)
            embeddings.append(embedding)
        return embeddings
