"""
Test script for Email functionality in AI Call system
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import dotenv
from services.email_service import email_service
from services.call_context import CallContext
from functions.send_email_summary import send_email_summary
from functions.send_email_info import send_email_info
from logger_config import get_logger

# Load environment variables
dotenv.load_dotenv()

logger = get_logger("EmailTest")


async def test_email_service():
    """Test the email service configuration and basic functionality"""
    try:
        logger.info("🧪 Testing email service...")
        
        if not email_service.enabled:
            logger.error("❌ Email service is not enabled. Please configure SENDER_EMAIL and SENDER_PASSWORD in your .env file")
            return False
        
        logger.info(f"✅ Email service is configured with sender: {email_service.sender_email}")
        
        # Test email address (you can change this to your email for testing)
        test_email = "dushyantbha012@gmail.com"
        
        # Test basic email sending
        logger.info("📧 Testing basic email sending...")
        
        success = await email_service.send_email(
            to_email=test_email,
            subject="AI Call System - Test Email",
            body="This is a test email from your AI Call system. If you receive this, the email configuration is working correctly!",
            is_html=False
        )
        
        if success:
            logger.info("✅ Basic email test successful")
        else:
            logger.error("❌ Basic email test failed")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Email service test failed: {e}")
        return False


async def test_email_functions():
    """Test the email functions with sample data"""
    try:
        logger.info("🧪 Testing email functions...")
        
        # Create a test call context
        context = CallContext()
        context.user_email = os.getenv("TEST_EMAIL", "test@example.com")
        context.call_sid = "test_call_email"
        context.user_phone_number = "+1234567890"
        
        # Add some sample conversation
        context.user_context = [
            {"role": "user", "content": "Hello, I need help with Python programming"},
            {"role": "assistant", "content": "I'd be happy to help you with Python programming. What specific aspect would you like to learn about?"},
            {"role": "user", "content": "I want to learn about data structures"},
            {"role": "assistant", "content": "Great! Python has several built-in data structures like lists, dictionaries, sets, and tuples. Each has its own strengths and use cases."}
        ]
        
        # Test email summary function
        logger.info("📊 Testing email summary function...")
        
        summary_args = {
            "to_email": context.user_email,
            "include_transcript": True
        }
        
        summary_result = await send_email_summary(context, summary_args)
        logger.info(f"Summary result: {summary_result}")
        
        # Test email info function
        logger.info("📋 Testing email info function...")
        
        info_args = {
            "query": "Python programming basics",
            "info_type": "programming",
            "to_email": context.user_email
        }
        
        info_result = await send_email_info(context, info_args)
        logger.info(f"Info result: {info_result}")
        
        logger.info("✅ Email functions test completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Email functions test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_email_integration():
    """Test the complete email integration"""
    try:
        logger.info("🧪 Testing complete email integration...")
        
        # Test without email configured
        logger.info("Testing function behavior without email in context...")
        
        empty_context = CallContext()
        empty_context.call_sid = "test_no_email"
        
        result = await send_email_summary(empty_context, {})
        logger.info(f"No email result: {result}")
        
        # Test with invalid email
        logger.info("Testing function behavior with invalid email...")
        
        invalid_context = CallContext()
        invalid_context.user_email = "invalid-email"
        
        result = await send_email_summary(invalid_context, {})
        logger.info(f"Invalid email result: {result}")
        
        logger.info("✅ Email integration test completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Email integration test failed: {e}")
        return False


def print_email_setup_instructions():
    """Print setup instructions for email configuration"""
    print("""
📧 Email Configuration Setup Instructions:

1. For Gmail users:
   - Go to your Google Account settings
   - Navigate to Security > App passwords
   - Generate a new app password for "Mail"
   - Use this app password (not your regular password) in SENDER_PASSWORD

2. Update your .env file with:
   SENDER_EMAIL=your_email@gmail.com
   SENDER_PASSWORD=your_16_character_app_password
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   GMAIL_SENDER_NAME="AI Assistant"

3. For testing, you can also set:
   TEST_EMAIL=your_test_email@example.com

4. Other email providers:
   - Outlook: smtp.live.com:587
   - Yahoo: smtp.mail.yahoo.com:587
   - Custom SMTP: Configure according to your provider

⚠️  Important: Never use your regular email password. Always use app passwords or OAuth tokens.
""")


async def main():
    """Main test function"""
    logger.info("🚀 Starting email functionality tests...")
    
    # Check if email is configured
    if not email_service.enabled:
        logger.warning("⚠️  Email service is not configured")
        print_email_setup_instructions()
        
        # Test the functions anyway to check error handling
        logger.info("Testing error handling with unconfigured email...")
        success = await test_email_integration()
        
        if success:
            logger.info("✅ Error handling tests passed!")
        else:
            logger.error("❌ Error handling tests failed!")
        
        sys.exit(0)
    
    # Run all tests
    tests = [
        ("Email Service", test_email_service),
        ("Email Functions", test_email_functions),
        ("Email Integration", test_email_integration)
    ]
    
    all_passed = True
    
    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} Tests ---")
        success = await test_func()
        
        if success:
            logger.info(f"✅ {test_name} tests passed!")
        else:
            logger.error(f"❌ {test_name} tests failed!")
            all_passed = False
    
    if all_passed:
        logger.info("\n🎉 All email tests passed!")
        sys.exit(0)
    else:
        logger.error("\n❌ Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
