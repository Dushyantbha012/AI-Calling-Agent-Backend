import os
import datetime
from services.email_service import email_service
from logger_config import get_logger
from functions.send_whatsapp_info import get_info_content

logger = get_logger("SendEmailInfo")


async def send_email_info(context, args):
    """
    Send specific information to the user's email address.
    Similar to send_whatsapp_info but sends via email instead.
    """
    try:
        query = args.get('query', '').strip()
        info_type = args.get('info_type', 'general').strip()
        to_email = args.get('to_email', '').strip()
        custom_text = args.get('custom_text', '').strip()
        
        logger.info(f"Email info request - Query: '{query}', Type: '{info_type}', Email: '{to_email}'")
        
        # Validate email service is configured
        if not email_service.enabled:
            return "I'm sorry, but email service is not configured. Please contact your administrator or try WhatsApp instead."
        
        # Extract query from context if not provided
        if not query and not custom_text:
            # Try to extract from recent conversation
            recent_messages = context.user_context[-3:] if context.user_context else []
            for msg in reversed(recent_messages):
                if msg.get('role') == 'user':
                    content = msg.get('content', '').lower()
                    # Look for patterns like "send me info about X" or "tell me about X"
                    if 'about' in content:
                        potential_query = content.split('about')[-1].strip()
                        if potential_query and len(potential_query) > 2:
                            query = potential_query
                            break
                    elif 'information' in content or 'info' in content:
                        # Extract the main subject
                        words = content.split()
                        # Find words after "information" or "info"
                        for i, word in enumerate(words):
                            if word in ['information', 'info', 'details'] and i < len(words) - 1:
                                query = ' '.join(words[i+1:i+4])  # Take next 3 words
                                break
        
        if not query and not custom_text and not info_type:
            logger.warning("No query could be extracted from context")
            return "I need more specific information about what you'd like me to send to your email. For example, 'Send me information about Python programming via email.'"
        
        # Determine a unique identifier for this information request
        request_id = f"{info_type}_{query}"[:50]  # Limit length for safety
        
        # Check if similar information was sent recently (within 2 minutes)
        if not hasattr(context, 'collected_data'):
            context.collected_data = {}
        
        last_info = context.collected_data.get('email_info', {}).get(request_id, {})
        
        if last_info:
            last_timestamp = last_info.get('timestamp')
            if last_timestamp:
                last_time = datetime.datetime.fromisoformat(last_timestamp)
                current_time = datetime.datetime.now()
                time_diff = (current_time - last_time).total_seconds()
                
                # If this info was sent in the last 2 minutes, don't send again
                if time_diff < 120:  # 2 minutes in seconds
                    logger.info(f"Similar information already sent {time_diff:.1f} seconds ago. Skipping.")
                    return f"I've already sent that information to your email just now. Please check your inbox."
        
        # Get the recipient email
        if not to_email:
            # First try to get from stored context
            if hasattr(context, 'user_email') and context.user_email:
                to_email = context.user_email
                logger.info(f"Using stored user email: {to_email}")
            else:
                return "I need an email address to send the information to. Could you please provide your email address?"
        
        if not to_email:
            return "I need an email address to send the information to."
        
        # Validate email format (basic validation)
        if '@' not in to_email or '.' not in to_email.split('@')[-1]:
            return "Please provide a valid email address."
        
        # Get the content based on the info type and query
        message_body = await get_info_content(info_type, query, context, custom_text)
        
        # Determine the topic for email subject
        topic = query if query else info_type if info_type != 'general' else 'Requested Information'
        
        # Send email
        success = await email_service.send_information(
            to_email=to_email,
            topic=topic,
            information=message_body
        )
        
        if success:
            # Store information about this request
            if 'email_info' not in context.collected_data:
                context.collected_data['email_info'] = {}
            
            context.collected_data['email_info'][request_id] = {
                'timestamp': datetime.datetime.now().isoformat(),
                'query': query,
                'info_type': info_type,
                'email': to_email
            }
            
            logger.info(f"Successfully sent email info to {to_email}")
            return f"I've sent the information about {topic} to your email at {to_email}. Please check your inbox."
        else:
            logger.error(f"Failed to send email to {to_email}")
            return "I'm sorry, but I encountered an error while sending the email. Please try again or use WhatsApp instead."
        
    except Exception as e:
        logger.error(f"Error in send_email_info: {str(e)}")
        return f"I'm sorry, but I encountered an error while processing your email request: {str(e)}"
