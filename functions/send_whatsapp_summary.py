import os
import json
import datetime
from twilio.rest import Client
import openai
from logger_config import get_logger

logger = get_logger("WhatsAppSummary")

async def generate_conversation_summary(context):
    """
    Generate a summary of the conversation using OpenAI.
    
    Args:
        context: The call context containing conversation history
    
    Returns:
        str: A summary of the conversation
    """
    try:
        # Extract conversation history
        conversation = []
        for msg in context.user_context:
            if msg['role'] in ['user', 'assistant']:
                conversation.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
        
        # Prepare prompt for summary generation
        system_prompt = """You are an AI that creates concise summaries of phone conversations.
        Summarize the conversation in 3-5 bullet points, highlighting:
        1. The main purpose of the call
        2. Key information discussed
        3. Actions taken or promised
        4. Any follow-up needed
        
        Format the summary professionally and concisely."""
        
        # Get OpenAI client
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Request summary from OpenAI
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                *conversation
            ],
            max_tokens=500
        )
        
        summary = response.choices[0].message.content
        logger.info(f"Generated conversation summary: {summary}")
        
        # Check if any calendar events were created and add them to the summary
        calendar_event = context.collected_data.get('calendar_event')
        if calendar_event:
            event_date = datetime.datetime.strptime(calendar_event['date'], "%Y-%m-%d").strftime("%A, %B %d, %Y")
            event_summary = (
                f"\n\n📅 *Scheduled Event*:\n"
                f"• Event: {calendar_event['title']}\n"
                f"• Date: {event_date}\n"
                f"• Time: {calendar_event['start_time']} to {calendar_event['end_time']}"
            )
            summary += event_summary
        
        # Add footer
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary += f"\n\n_Summary generated on {timestamp}_"
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating conversation summary: {str(e)}")
        return "An error occurred while generating the call summary."

async def send_whatsapp_summary(context, args):
    """
    Send a summary of the conversation to a WhatsApp number.
    Only sends if explicitly requested or if no summary was sent in the last 2 minutes.
    
    Args:
        context: The call context
        args: Dictionary containing parameters
            - to_number: WhatsApp number to send the summary to (optional, defaults to caller's number)
            - include_transcript: Boolean to include full transcript (optional, defaults to False)
            - force_send: Boolean to force sending even if recent summary exists (optional, defaults to False)
    
    Returns:
        str: A message confirming the summary was sent or describing an error
    """
    try:
        # Check if summary was already sent recently
        last_summary = context.collected_data.get('whatsapp_summary', {})
        force_send = args.get('force_send', False)
        
        if last_summary and not force_send:
            # Check if summary was sent in the last 2 minutes
            last_timestamp = last_summary.get('timestamp')
            if last_timestamp:
                last_time = datetime.datetime.fromisoformat(last_timestamp)
                current_time = datetime.datetime.now()
                time_diff = (current_time - last_time).total_seconds()
                
                # If summary was sent in the last 2 minutes, don't send again
                if time_diff < 120:  # 2 minutes in seconds
                    logger.info(f"Summary already sent {time_diff:.1f} seconds ago. Skipping.")
                    return "I've already sent a summary to your WhatsApp just now. Check your messages."
        
        # Initialize Twilio client
        account_sid = os.environ['TWILIO_ACCOUNT_SID']
        auth_token = os.environ['TWILIO_AUTH_TOKEN']
        from_number = os.environ['TWILIO_WHATSAPP_NUMBER']  # Should be in format "whatsapp:+1234567890"
        
        client = Client(account_sid, auth_token)
        
        # Get the recipient number
        to_number = args.get('to_number')
        
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
                    return "I couldn't send a WhatsApp summary because I couldn't determine your phone number."
        
        if not to_number:
            return "I need a phone number to send the WhatsApp summary to."
        
        # Format to_number for WhatsApp API if not already formatted
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"
        
        # Generate summary
        summary = await generate_conversation_summary(context)
        
        # Add full transcript if requested
        include_transcript = args.get('include_transcript', False)
        message_body = summary
        
        if include_transcript:
            transcript = "\n\n*Full Conversation Transcript:*\n"
            for msg in context.user_context:
                if msg['role'] == 'user':
                    transcript += f"\n👤 You: {msg['content']}\n"
                elif msg['role'] == 'assistant':
                    transcript += f"\n🤖 AI: {msg['content']}\n"
            
            # Check if transcript would make the message too long
            if len(message_body + transcript) > 1600:  # WhatsApp has a character limit
                message_body += "\n\n_Full transcript was too long to include._"
            else:
                message_body += transcript
        
        # Send WhatsApp message
        message = client.messages.create(
            body=message_body,
            from_=from_number,
            to=to_number
        )
        
        logger.info(f"WhatsApp summary sent with SID: {message.sid}")
        
        # Store in context that a summary was sent
        context.collected_data['whatsapp_summary'] = {
            'sent_to': to_number,
            'timestamp': datetime.datetime.now().isoformat(),
            'message_sid': message.sid
        }
        
        return f"I've sent a summary of our conversation to your WhatsApp. You should receive it shortly."
        
    except Exception as e:
        logger.error(f"Error sending WhatsApp summary: {str(e)}")
        return f"I encountered an error while sending the WhatsApp summary: {str(e)}"
