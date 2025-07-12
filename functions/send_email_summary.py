import os
import datetime
from services.email_service import email_service
from logger_config import get_logger
from functions.send_whatsapp_summary import generate_conversation_summary

logger = get_logger("SendEmailSummary")


async def send_email_summary(context, args):
    """
    Send a summary of the conversation to the user's email address.
    Similar to send_whatsapp_summary but sends via email instead.
    """
    try:
        to_email = args.get('to_email', '').strip()
        include_transcript = args.get('include_transcript', False)
        
        logger.info(f"Email summary request - Email: '{to_email}', Include transcript: {include_transcript}")
        
        # Validate email service is configured
        if not email_service.enabled:
            return "I'm sorry, but email service is not configured. Please contact your administrator or try WhatsApp instead."
        
        # Check if a summary was sent recently to prevent spam
        if not hasattr(context, 'collected_data'):
            context.collected_data = {}
        
        last_summary = context.collected_data.get('email_summary', {})
        
        if last_summary:
            last_timestamp = last_summary.get('timestamp')
            if last_timestamp:
                last_time = datetime.datetime.fromisoformat(last_timestamp)
                current_time = datetime.datetime.now()
                time_diff = (current_time - last_time).total_seconds()
                
                # If summary was sent in the last 2 minutes, don't send again
                if time_diff < 120:  # 2 minutes in seconds
                    logger.info(f"Summary already sent {time_diff:.1f} seconds ago. Skipping.")
                    return "I've already sent a summary to your email just now. Check your inbox."
        
        # Get the recipient email
        if not to_email:
            # First try to get from stored context
            if hasattr(context, 'user_email') and context.user_email:
                to_email = context.user_email
                logger.info(f"Using stored user email: {to_email}")
            else:
                return "I need an email address to send the summary to. Could you please provide your email address?"
        
        if not to_email:
            return "I need an email address to send the summary to."
        
        # Validate email format (basic validation)
        if '@' not in to_email or '.' not in to_email.split('@')[-1]:
            return "Please provide a valid email address."
        
        # Generate summary
        summary = await generate_conversation_summary(context)
        
        # Prepare transcript if requested
        transcript = None
        if include_transcript and context.user_context:
            transcript = context.user_context
        
        # Get phone number for email
        phone_number = getattr(context, 'user_phone_number', 'Unknown')
        call_sid = getattr(context, 'call_sid', 'Unknown')
        
        # Send email
        success = await email_service.send_call_summary(
            to_email=to_email,
            call_summary=summary,
            call_sid=call_sid,
            phone_number=phone_number,
            include_transcript=include_transcript,
            transcript=transcript
        )
        
        if success:
            # Store information about this summary
            context.collected_data['email_summary'] = {
                'timestamp': datetime.datetime.now().isoformat(),
                'email': to_email,
                'include_transcript': include_transcript
            }
            
            logger.info(f"Successfully sent email summary to {to_email}")
            
            if include_transcript:
                return f"I've sent a detailed summary with the full conversation transcript to your email at {to_email}. Please check your inbox."
            else:
                return f"I've sent a summary of our conversation to your email at {to_email}. Please check your inbox."
        else:
            logger.error(f"Failed to send email summary to {to_email}")
            return "I'm sorry, but I encountered an error while sending the email summary. Please try again or use WhatsApp instead."
        
    except Exception as e:
        logger.error(f"Error in send_email_summary: {str(e)}")
        return f"I'm sorry, but I encountered an error while processing your email summary request: {str(e)}"
