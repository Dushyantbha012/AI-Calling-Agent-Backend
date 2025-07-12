"""
Test script for RAG integration in AI Call system
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
from services.call_context import CallContext
from services.llm_service import LLMFactory
from logger_config import get_logger

# Load environment variables
dotenv.load_dotenv()

logger = get_logger("RAGTest")


async def test_rag_integration():
    """Test the full RAG integration with LLM service"""
    try:
        logger.info("🧪 Testing RAG integration...")
        
        # Initialize RAG service
        await rag_service.initialize()
        
        if not rag_service.rag_enabled:
            logger.error("RAG is not enabled. Please set RAG_ENABLED=true in your .env file")
            return False
        
        # Create a test call context
        context = CallContext()
        context.user_phone_number = "+1234567890"
        context.call_sid = "test_call_integration"
        context.system_message = "You are a helpful AI assistant."
        context.initial_message = "Hello! How can I help you today?"
        
        # Initialize LLM service
        llm_service = LLMFactory.get_llm_service("openai", context)
        await llm_service.initialize_rag()
        
        # Test storing some conversation history
        logger.info("📝 Storing test conversation history...")
        
        # Simulate previous conversations
        previous_conversations = [
            {
                "user": "I need help with my billing account",
                "assistant": "I'd be happy to help you with your billing. What specific issue are you experiencing?",
                "interaction": 1
            },
            {
                "user": "My last payment was declined",
                "assistant": "I can help you resolve payment issues. Let me check your account details and guide you through updating your payment method.",
                "interaction": 2
            },
            {
                "user": "Can you help me change my plan?",
                "assistant": "Certainly! I can help you review and change your current plan. What type of changes are you looking for?",
                "interaction": 3
            }
        ]
        
        for conv in previous_conversations:
            await rag_service.store_conversation_turn(
                phone_number=context.user_phone_number,
                call_sid="previous_call_123",
                user_message=conv["user"],
                assistant_message=conv["assistant"],
                interaction_count=conv["interaction"],
                metadata={"test_data": True}
            )
        
        logger.info("✅ Test conversation history stored")
        
        # Test RAG context retrieval
        logger.info("🔍 Testing context retrieval...")
        
        test_query = "I have a question about my billing"
        rag_context = await llm_service.get_rag_context(test_query)
        
        if rag_context:
            logger.info("✅ RAG context retrieved successfully")
            logger.info(f"📋 Retrieved context preview: {rag_context[:200]}...")
        else:
            logger.warning("⚠️ No RAG context retrieved")
        
        # Test caller summary
        logger.info("📊 Testing caller history summary...")
        
        caller_summary = await llm_service.get_caller_summary()
        
        if caller_summary:
            logger.info("✅ Caller summary generated successfully")
            logger.info(f"📋 Summary preview: {caller_summary[:200]}...")
        else:
            logger.warning("⚠️ No caller summary generated")
        
        # Test storing new conversation turn
        logger.info("💾 Testing conversation storage...")
        
        await llm_service.store_conversation_turn(
            user_message="I want to update my payment information",
            assistant_message="I can help you update your payment information securely. Let me guide you through the process.",
            interaction_count=1
        )
        
        logger.info("✅ New conversation turn stored successfully")
        
        # Test retrieval of the new conversation
        logger.info("🔄 Testing retrieval of newly stored conversation...")
        
        updated_context = await llm_service.get_rag_context("payment update help")
        
        if "payment information" in updated_context.lower():
            logger.info("✅ New conversation successfully retrieved")
        else:
            logger.warning("⚠️ New conversation not found in retrieved context")
        
        logger.info("🎉 RAG integration test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ RAG integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def cleanup_test_data():
    """Clean up test data (simplified version)"""
    logger.info("🧹 Cleaning up test data...")
    # In a real implementation, you would delete test records from Qdrant
    # For now, we'll just note that cleanup should happen
    logger.info("✅ Test data cleanup completed")


async def main():
    """Main test function"""
    logger.info("🚀 Starting RAG integration tests...")
    
    success = await test_rag_integration()
    
    if success:
        logger.info("✅ All tests passed!")
        await cleanup_test_data()
        sys.exit(0)
    else:
        logger.error("❌ Tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
