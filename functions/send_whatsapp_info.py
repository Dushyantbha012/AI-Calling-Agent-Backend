import os
import json
import datetime
import openai
from twilio.rest import Client
from logger_config import get_logger

logger = get_logger("WhatsAppInfo")

# Sample templates that can be used as fallback or examples
INFO_TEMPLATES = {
    "contact": """*Contact Information:*
• Customer Service: +1-800-555-1234
• Email: support@example.com
• Website: www.example.com
• Hours: Monday-Friday, 9am-5pm EST""",
    
    "pricing": """*Our Pricing Plans:*
• Basic: $9.99/month
  - 10 GB storage
  - Email support

• Premium: $19.99/month
  - 50 GB storage
  - Priority email & phone support
  - Advanced analytics

• Enterprise: $49.99/month
  - 200 GB storage
  - 24/7 dedicated support
  - Full feature access""",

    "faqs": """*Frequently Asked Questions:*

*Q: How do I reset my password?*
A: Visit the login page and click "Forgot Password" to receive reset instructions via email.

*Q: What payment methods do you accept?*
A: We accept all major credit cards, PayPal, and bank transfers for enterprise accounts.

*Q: How can I cancel my subscription?*
A: Log into your account, go to Settings > Subscription, and click "Cancel Subscription".""",

    "hours": """*Business Hours:*
• Monday-Friday: 9:00 AM - 6:00 PM
• Saturday: 10:00 AM - 4:00 PM
• Sunday: Closed

*Customer Support Hours:*
• Monday-Friday: 8:00 AM - 8:00 PM
• Saturday-Sunday: 10:00 AM - 4:00 PM

All times are in Eastern Time (ET).""",

    "shipping": """*Shipping Information:*
• Standard Shipping: 5-7 business days
• Express Shipping: 2-3 business days
• Overnight Shipping: Next business day

*International Shipping:*
• Available to most countries
• Delivery times vary by location (7-21 days)
• Additional customs fees may apply

For order tracking, visit our website and enter your order number."""
}

async def generate_custom_content(query, context):
    """Generate custom content based on user query using LLM"""
    try:
        # Extract conversation history for context
        conversation = []
        for msg in context.user_context[-10:]:  # Look at last 10 messages for context
            if msg['role'] in ['user', 'assistant']:
                conversation.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
        
        # Prepare prompt for content generation
        system_prompt = """You are an AI that creates concise, informative responses to user queries.
        Based on the conversation and the specific information request, create a well-formatted response
        that directly addresses what the user wants to know. Format your response with:
        - Clear headings using *bold text*
        - Bullet points for lists (•)
        - Brief, factual information
        - Professional tone
        
        If you don't have specific information on the topic, provide general, helpful information
        that would be reasonable to know about the topic."""
        
        # Get OpenAI client
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Add the specific query as the final message
        query_context = [
            {"role": "system", "content": system_prompt},
            *conversation,
            {"role": "user", "content": f"Please provide information about: {query}"}
        ]
        
        # Request content from OpenAI
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=query_context,
            max_tokens=800
        )
        
        content = response.choices[0].message.content
        logger.info(f"Generated custom content for query: '{query}'")
        
        return content
    
    except Exception as e:
        logger.error(f"Error generating custom content: {str(e)}")
        return f"I don't have specific information about '{query}'. Please contact customer service for assistance."

async def get_info_content(info_type, query, context, custom_text=None):
    """Get content for sending to WhatsApp"""
    # If custom text is directly provided, use that
    if custom_text:
        return custom_text
    
    # If it's a standard template and no query specified, use template
    if info_type.lower() in INFO_TEMPLATES and not query:
        return INFO_TEMPLATES.get(info_type.lower())
    
    # Otherwise generate custom content based on the query or info type
    content_query = query if query else info_type
    return await generate_custom_content(content_query, context)

async def send_whatsapp_info(context, args):
    """
    Send information to a WhatsApp number based on what the user requests.
    This can be any type of information the user asks for.
    
    Args:
        context: The call context
        args: Dictionary containing parameters
            - info_type: General category or specific query (optional)
            - query: The specific information request from the user (optional)
            - to_number: WhatsApp number to send the message to (optional, defaults to caller's number)
            - custom_text: Custom text to send instead of generating content (optional)
    
    Returns:
        str: A message confirming the information was sent or describing an error
    """
    try:
        # Extract arguments
        info_type = args.get('info_type', '').lower()
        query = args.get('query', '')
        to_number = args.get('to_number')
        custom_text = args.get('custom_text')
        
        # Validate query - CRITICAL CHECK
        if not query and not custom_text and not info_type:
            logger.error("Empty query detected - no content to send")
            return "I need to know what information you'd like me to send to your WhatsApp. Could you please specify what you'd like to know about?"
        
        # If query is mentioned in context but not provided, try to extract it
        if not query and not custom_text:
            # Check last few user messages for potential topics
            recent_messages = []
            for msg in reversed(context.user_context[-5:]):
                if msg['role'] == 'user':
                    recent_messages.append(msg['content'])
            
            for message in recent_messages:
                if "about" in message.lower():
                    # Try to extract topic after "about"
                    potential_query = message.lower().split("about")[-1].strip()
                    if potential_query and len(potential_query) > 2:
                        if potential_query.startswith("the "):
                            potential_query = potential_query[4:]
                        query = potential_query
                        logger.info(f"Extracted query from context: '{query}'")
                        break
        
        # Still no query? Use a default
        if not query and not custom_text and not info_type:
            logger.warning("No query could be extracted from context")
            return "I need more specific information about what you'd like me to send to your WhatsApp. For example, 'Send me information about Hyderabad.'"
        
        # Determine a unique identifier for this information request
        request_id = f"{info_type}_{query}"[:50]  # Limit length for safety
        
        # Check if similar information was sent recently (within 2 minutes)
        last_info = context.collected_data.get('whatsapp_info', {}).get(request_id, {})
        
        if last_info:
            last_timestamp = last_info.get('timestamp')
            if last_timestamp:
                last_time = datetime.datetime.fromisoformat(last_timestamp)
                current_time = datetime.datetime.now()
                time_diff = (current_time - last_time).total_seconds()
                
                # If this info was sent in the last 2 minutes, don't send again
                if time_diff < 120:  # 2 minutes in seconds
                    logger.info(f"Similar information already sent {time_diff:.1f} seconds ago. Skipping.")
                    return f"I've already sent that information to your WhatsApp just now. Please check your messages."
        
        # Initialize Twilio client
        account_sid = os.environ['TWILIO_ACCOUNT_SID']
        auth_token = os.environ['TWILIO_AUTH_TOKEN']
        from_number = os.environ['TWILIO_WHATSAPP_NUMBER']  # Should be in format "whatsapp:+1234567890"
        
        client = Client(account_sid, auth_token)
        
        # If no number provided, try to extract from the call context
        # If no number provided, try to extract from the call context
        if not to_number:
            # First try to get from stored context
            if hasattr(context, 'user_phone_number') and context.user_phone_number:
                to_number = context.user_phone_number
                logger.info(f"Using stored user phone number: {to_number}")
            elif context.call_sid:
                # Fallback to Twilio API
                try:
                    call_details = client.calls(context.call_sid).fetch()
                    # Use the correct attribute name for accessing the 'from' field
                    from_number = getattr(call_details, '_from', None)
                    to_number_api = getattr(call_details, 'to', None)
                    
                    # Determine which number is the user's number
                    twilio_number = os.environ.get("TWILIO_PHONE_NUMBER") or os.environ.get("APP_NUMBER")
                    
                    if from_number and from_number != twilio_number:
                        to_number = from_number
                    elif to_number_api and to_number_api != twilio_number:
                        to_number = to_number_api
                    
                    if to_number:
                        logger.info(f"Extracted to_number from call: {to_number}")
                except Exception as e:
                    logger.error(f"Error fetching call details: {str(e)}")
                    return "I couldn't send the information because I couldn't determine your phone number."
        
        if not to_number:
            return "I need a phone number to send the WhatsApp message to."
        
        # Format to_number for WhatsApp API if not already formatted
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"
        
        # Get the content based on the info type and query
        message_body = await get_info_content(info_type, query, context, custom_text)
        
        # Add header with topic if not using custom text
        if not custom_text:
            topic = query if query else info_type
            message_body = f"*Information: {topic.capitalize()}*\n\n{message_body}"
        
        # Add footer
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message_body += f"\n\n_Information sent on {timestamp}_"
        
        # Send WhatsApp message
        message = client.messages.create(
            body=message_body,
            from_=from_number,
            to=to_number
        )
        
        logger.info(f"WhatsApp information for '{request_id}' sent with SID: {message.sid}")
        
        # Store in context that this information was sent
        if 'whatsapp_info' not in context.collected_data:
            context.collected_data['whatsapp_info'] = {}
            
        context.collected_data['whatsapp_info'][request_id] = {
            'sent_to': to_number,
            'timestamp': datetime.datetime.now().isoformat(),
            'message_sid': message.sid,
            'topic': query if query else info_type
        }
        
        description = f"information about {query if query else info_type}"
        return f"I've sent {description} to your WhatsApp. You should receive it shortly."
        
    except Exception as e:
        logger.error(f"Error sending WhatsApp information: {str(e)}")
        return f"I encountered an error while sending the information to WhatsApp: {str(e)}"
