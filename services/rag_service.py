import asyncio
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct, Filter, 
    FieldCondition, MatchValue, ScoredPoint
)
import json

from logger_config import get_logger

logger = get_logger("RAGService")


class RAGService:
    """
    RAG (Retrieval Augmented Generation) service using Qdrant vector database.
    Stores and retrieves conversation context based on phone numbers.
    """
    
    def __init__(self):
        self.client = None
        self.embedder = None
        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME", "phone_conversations")
        self.vector_size = int(os.getenv("QDRANT_VECTOR_SIZE", "384"))
        self.max_context_chunks = int(os.getenv("RAG_MAX_CONTEXT_CHUNKS", "5"))
        self.similarity_threshold = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.7"))
        self.chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "500"))
        self.chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "50"))
        self.rag_enabled = os.getenv("RAG_ENABLED", "true").lower() == "true"
        
    async def initialize(self):
        """Initialize the RAG service with Qdrant client and sentence transformer"""
        if not self.rag_enabled:
            logger.info("RAG service is disabled")
            return
            
        try:
            # Initialize Qdrant client
            qdrant_host = os.getenv("QDRANT_HOST", "localhost")
            qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
            qdrant_api_key = os.getenv("QDRANT_API_KEY")
            
            if qdrant_api_key:
                self.client = AsyncQdrantClient(
                    host=qdrant_host,
                    port=qdrant_port,
                    api_key=qdrant_api_key
                )
            else:
                self.client = AsyncQdrantClient(host=qdrant_host, port=qdrant_port)
            
            # Initialize sentence transformer for embeddings
            # Using a smaller, faster model for real-time performance
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            self.vector_size = self.embedder.get_sentence_embedding_dimension()
            
            # Ensure collection exists
            await self._ensure_collection_exists()
            
            logger.info(f"RAG service initialized with collection: {self.collection_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize RAG service: {e}")
            self.rag_enabled = False
    
    async def _ensure_collection_exists(self):
        """Ensure the Qdrant collection exists with proper configuration"""
        try:
            collections = await self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                await self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Created collection: {self.collection_name}")
            else:
                logger.info(f"Collection {self.collection_name} already exists")
                
        except Exception as e:
            logger.error(f"Failed to ensure collection exists: {e}")
            raise
    
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks with overlap for better context retrieval"""
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            
            # Try to break at a sentence boundary
            if end < len(text):
                last_period = chunk.rfind('.')
                last_exclamation = chunk.rfind('!')
                last_question = chunk.rfind('?')
                
                sentence_end = max(last_period, last_exclamation, last_question)
                if sentence_end > start + self.chunk_size // 2:
                    chunk = text[start:start + sentence_end + 1]
                    end = start + sentence_end + 1
            
            chunks.append(chunk.strip())
            start = end - self.chunk_overlap
            
            if start >= len(text):
                break
                
        return chunks
    
    async def store_conversation_turn(
        self, 
        phone_number: str, 
        call_sid: str,
        user_message: str, 
        assistant_message: str,
        interaction_count: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store a conversation turn in the vector database"""
        if not self.rag_enabled or not self.client:
            return
            
        try:
            # Create conversation text
            conversation_text = f"User: {user_message}\nAssistant: {assistant_message}"
            
            # Generate chunks
            chunks = self._chunk_text(conversation_text)
            
            # Generate embeddings and store each chunk
            points = []
            for i, chunk in enumerate(chunks):
                embedding = self.embedder.encode(chunk).tolist()
                
                point_metadata = {
                    "phone_number": phone_number,
                    "call_sid": call_sid,
                    "interaction_count": interaction_count,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "timestamp": datetime.utcnow().isoformat(),
                    "user_message": user_message,
                    "assistant_message": assistant_message,
                    "conversation_text": chunk
                }
                
                if metadata:
                    point_metadata.update(metadata)
                
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload=point_metadata
                )
                points.append(point)
            
            # Store in Qdrant
            await self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info(f"Stored {len(chunks)} chunks for phone {phone_number}, interaction {interaction_count}")
            
        except Exception as e:
            logger.error(f"Failed to store conversation turn: {e}")
    
    async def retrieve_relevant_context(
        self, 
        phone_number: str, 
        current_query: str,
        exclude_call_sid: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant conversation context for the given phone number and query"""
        if not self.rag_enabled or not self.client:
            return []
            
        try:
            # Generate embedding for the current query
            query_embedding = self.embedder.encode(current_query).tolist()
            
            # Create filter for the specific phone number
            filter_conditions = [
                FieldCondition(
                    key="phone_number",
                    match=MatchValue(value=phone_number)
                )
            ]
            
            # Exclude current call if specified
            if exclude_call_sid:
                filter_conditions.append(
                    FieldCondition(
                        key="call_sid",
                        match=MatchValue(value=exclude_call_sid),
                        range=None
                    )
                )
            
            search_filter = Filter(must=filter_conditions)
            
            # Search for similar conversations
            search_results = await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=search_filter,
                limit=self.max_context_chunks,
                score_threshold=self.similarity_threshold
            )
            
            # Process and return results
            relevant_contexts = []
            for result in search_results:
                context = {
                    "conversation_text": result.payload.get("conversation_text", ""),
                    "user_message": result.payload.get("user_message", ""),
                    "assistant_message": result.payload.get("assistant_message", ""),
                    "timestamp": result.payload.get("timestamp", ""),
                    "similarity_score": result.score,
                    "call_sid": result.payload.get("call_sid", ""),
                    "interaction_count": result.payload.get("interaction_count", 0)
                }
                relevant_contexts.append(context)
            
            logger.info(f"Retrieved {len(relevant_contexts)} relevant contexts for phone {phone_number}")
            return relevant_contexts
            
        except Exception as e:
            logger.error(f"Failed to retrieve relevant context: {e}")
            return []
    
    async def get_caller_history_summary(self, phone_number: str) -> str:
        """Get a summary of the caller's interaction history"""
        if not self.rag_enabled or not self.client:
            return ""
            
        try:
            # Get recent conversations for this phone number
            filter_condition = Filter(
                must=[
                    FieldCondition(
                        key="phone_number",
                        match=MatchValue(value=phone_number)
                    )
                ]
            )
            
            # Get recent points (limit to last 10 interactions)
            recent_points = await self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=filter_condition,
                limit=10,
                with_payload=True
            )
            
            if not recent_points[0]:  # No previous conversations
                return ""
            
            # Group by call_sid and summarize
            calls_summary = {}
            for point in recent_points[0]:
                call_sid = point.payload.get("call_sid", "")
                timestamp = point.payload.get("timestamp", "")
                user_msg = point.payload.get("user_message", "")
                assistant_msg = point.payload.get("assistant_message", "")
                
                if call_sid not in calls_summary:
                    calls_summary[call_sid] = {
                        "timestamp": timestamp,
                        "interactions": []
                    }
                
                calls_summary[call_sid]["interactions"].append({
                    "user": user_msg,
                    "assistant": assistant_msg
                })
            
            # Create summary text
            if not calls_summary:
                return ""
            
            summary_parts = [f"Previous interactions with caller {phone_number}:"]
            
            for call_sid, call_data in list(calls_summary.items())[:3]:  # Last 3 calls
                summary_parts.append(f"\nCall from {call_data['timestamp'][:10]}:")
                for interaction in call_data["interactions"][:2]:  # First 2 interactions per call
                    summary_parts.append(f"- User asked: {interaction['user'][:100]}...")
                    summary_parts.append(f"- Assistant responded: {interaction['assistant'][:100]}...")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Failed to get caller history summary: {e}")
            return ""
    
    async def store_call_metadata(
        self, 
        phone_number: str, 
        call_sid: str, 
        metadata: Dict[str, Any]
    ):
        """Store additional metadata about a call"""
        if not self.rag_enabled or not self.client:
            return
            
        try:
            # Create a metadata point
            embedding = self.embedder.encode(f"Call metadata for {phone_number}").tolist()
            
            point_metadata = {
                "phone_number": phone_number,
                "call_sid": call_sid,
                "type": "call_metadata",
                "timestamp": datetime.utcnow().isoformat(),
                **metadata
            }
            
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload=point_metadata
            )
            
            await self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.info(f"Stored call metadata for {phone_number}")
            
        except Exception as e:
            logger.error(f"Failed to store call metadata: {e}")
    
    async def cleanup_old_conversations(self, days_to_keep: int = 30):
        """Clean up conversations older than specified days"""
        if not self.rag_enabled or not self.client:
            return
            
        try:
            cutoff_date = datetime.utcnow().timestamp() - (days_to_keep * 24 * 60 * 60)
            
            # This would require implementing a cleanup mechanism
            # For now, we'll log the intent
            logger.info(f"Cleanup requested for conversations older than {days_to_keep} days")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old conversations: {e}")


# Global RAG service instance
rag_service = RAGService()
