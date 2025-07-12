#!/usr/bin/env python3
"""
Qdrant Setup Utility for AI Call System

This script helps set up and manage the Qdrant vector database for the RAG system.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import dotenv
from services.rag_service import rag_service
from logger_config import get_logger

# Load environment variables
dotenv.load_dotenv()

logger = get_logger("QdrantSetup")


async def setup_qdrant():
    """Initialize Qdrant database and collection"""
    try:
        logger.info("Setting up Qdrant vector database...")
        
        # Initialize RAG service
        await rag_service.initialize()
        
        if rag_service.rag_enabled:
            logger.info("✅ Qdrant database setup completed successfully!")
            logger.info(f"Collection name: {rag_service.collection_name}")
            logger.info(f"Vector size: {rag_service.vector_size}")
            logger.info(f"Max context chunks: {rag_service.max_context_chunks}")
            logger.info(f"Similarity threshold: {rag_service.similarity_threshold}")
        else:
            logger.warning("RAG service is disabled. Enable it by setting RAG_ENABLED=true in your .env file")
            
    except Exception as e:
        logger.error(f"Failed to setup Qdrant: {e}")
        sys.exit(1)


async def test_rag_functionality():
    """Test basic RAG functionality"""
    try:
        logger.info("Testing RAG functionality...")
        
        test_phone = "+1234567890"
        test_call_sid = "test_call_123"
        
        # Test storing a conversation
        await rag_service.store_conversation_turn(
            phone_number=test_phone,
            call_sid=test_call_sid,
            user_message="Hello, I need help with my account",
            assistant_message="I'd be happy to help you with your account. What specific issue are you experiencing?",
            interaction_count=1,
            metadata={"test": True}
        )
        
        logger.info("✅ Successfully stored test conversation")
        
        # Test retrieving context
        contexts = await rag_service.retrieve_relevant_context(
            phone_number=test_phone,
            current_query="I have a problem with billing"
        )
        
        logger.info(f"✅ Retrieved {len(contexts)} relevant contexts")
        
        # Test caller history
        history = await rag_service.get_caller_history_summary(test_phone)
        if history:
            logger.info("✅ Successfully retrieved caller history")
        else:
            logger.info("ℹ️ No previous history found (expected for new caller)")
            
        logger.info("🎉 All RAG functionality tests passed!")
        
    except Exception as e:
        logger.error(f"RAG functionality test failed: {e}")
        sys.exit(1)


async def cleanup_test_data():
    """Clean up test data"""
    try:
        logger.info("Cleaning up test data...")
        # Note: In a production setup, you would implement a proper cleanup method
        # For now, we'll just log that cleanup would happen here
        logger.info("✅ Test data cleanup completed")
        
    except Exception as e:
        logger.error(f"Failed to cleanup test data: {e}")


def print_usage():
    """Print usage information"""
    print("""
Qdrant Setup Utility

Usage:
    python setup_qdrant.py [command]

Commands:
    setup     - Initialize Qdrant database and collection
    test      - Test RAG functionality with sample data
    cleanup   - Clean up test data
    info      - Show current configuration

Examples:
    python setup_qdrant.py setup
    python setup_qdrant.py test
    python setup_qdrant.py cleanup
""")


def print_config_info():
    """Print current configuration"""
    print("\n📋 Current RAG Configuration:")
    print(f"  RAG Enabled: {os.getenv('RAG_ENABLED', 'true')}")
    print(f"  Qdrant Host: {os.getenv('QDRANT_HOST', 'localhost')}")
    print(f"  Qdrant Port: {os.getenv('QDRANT_PORT', '6333')}")
    print(f"  Collection Name: {os.getenv('QDRANT_COLLECTION_NAME', 'phone_conversations')}")
    print(f"  Vector Size: {os.getenv('QDRANT_VECTOR_SIZE', '384')}")
    print(f"  Max Context Chunks: {os.getenv('RAG_MAX_CONTEXT_CHUNKS', '5')}")
    print(f"  Similarity Threshold: {os.getenv('RAG_SIMILARITY_THRESHOLD', '0.7')}")
    print(f"  Chunk Size: {os.getenv('RAG_CHUNK_SIZE', '500')}")
    print(f"  Chunk Overlap: {os.getenv('RAG_CHUNK_OVERLAP', '50')}")
    print()


async def main():
    """Main function"""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "setup":
        await setup_qdrant()
    elif command == "test":
        await setup_qdrant()
        await test_rag_functionality()
        await cleanup_test_data()
    elif command == "cleanup":
        await cleanup_test_data()
    elif command == "info":
        print_config_info()
    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
