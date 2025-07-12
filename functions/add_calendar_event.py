import os
import datetime
import asyncio
from googleapiclient.discovery import build
from logger_config import get_logger
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import openai
import json

logger = get_logger("AddCalendarEvent")

async def extract_calendar_event_args(context):
    """
    Extract calendar event arguments from the conversation context using LLM.
    
    Args:
        context: The call context containing conversation history
    
    Returns:
        tuple: (args_dict, error_message) - args_dict contains the extracted arguments if successful,
               otherwise None. error_message contains any error information if extraction failed.
    """
    try:
        # Extract conversation history by joining all recent user messages
        user_messages = []
        for msg in context.user_context[-10:]:  # Look at last 10 messages
            if msg['role'] == 'user':
                user_messages.append(msg['content'])
        
        # Join recent user messages to create a combined context
        combined_user_input = " ".join(user_messages)
        
        # Get current date for context
        current_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d")
        
        PROMPT = f"""You are an AI assistant that helps users schedule calendar events. 
        Based on the conversation context, extract the EXACT event details mentioned by the user.
        Today's date is {current_date}. Use this to resolve relative dates like:
        - "tomorrow" = next day
        - "day after tomorrow" = day after next
        - "next week" = 7 days from today
        - "next month" = same day next month
        
        DO NOT use any example or template data. ONLY use information explicitly stated by the user.
        DO NOT MAKE UP ANY INFORMATION. If any required field is missing, leave it blank.
        
        The user has provided the following information across potentially multiple messages:
        "{combined_user_input}"
        
        Create a JSON object with the following event details:
        - title (string): The exact event title mentioned by the user
        - date (string): Event date in YYYY-MM-DD format exactly as specified by the user
          (convert mentions like "May 22nd 2025" to "2025-05-22")
        - start_time (string): Start time in HH:MM format (24-hour)
          (convert mentions like "9 AM" to "09:00")
        - end_time (string): End time in HH:MM format (24-hour)
          (convert mentions like "10 AM" to "10:00")
        - description (string, optional): Event description if mentioned by the user

        Return only the JSON object with no additional text.
        """
        
        # Create a client for the OpenAI API
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Call chat completions API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": PROMPT}
            ],
            response_format={"type": "json_object"}
        )
        
        # Extract the content from the response
        content = response.choices[0].message.content
        
        # Parse the JSON
        try:
            args = json.loads(content)
            logger.info(f"Parsed calendar event args: {args}")
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from OpenAI response: {e}")
            logger.error(f"Raw content: {content}")
            return None, "I couldn't process the calendar event information correctly."
        
        # Get and validate required fields
        title = args.get('title')
        date = args.get('date')
        start_time = args.get('start_time')
        end_time = args.get('end_time')
        
        # Check for missing fields
        missing = []
        if not title: missing.append("title")
        if not date: missing.append("date")
        if not start_time: missing.append("start time")
        if not end_time: missing.append("end time")
        
        if missing:
            logger.error(f"Missing required calendar fields: {', '.join(missing)}")
            return None, f"I need all the event details to schedule it. Please provide the following: {', '.join(missing)}."
        
        # Validate date format
        try:
            datetime.datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            logger.error(f"Invalid date format: {date}")
            return None, f"The date format seems incorrect. Please provide the date in YYYY-MM-DD format or say the month, day and year clearly."
        
        # All validations passed
        return args, None
        
    except Exception as e:
        logger.error(f"Error extracting calendar event args: {str(e)}")
        return None, f"I encountered an error while processing your calendar event details: {str(e)}"


async def create_calendar_event(args):
    """
    Add an event to Google Calendar using the extracted arguments.
    
    Args:
        args: Dictionary containing validated event details
    
    Returns:
        str: A confirmation message or error message
    """
    try:
        # Extract parameters
        title = args.get('title')
        date = args.get('date')
        start_time = args.get('start_time')
        end_time = args.get('end_time')
        description = args.get('description', '')
        
        # Log the calendar event creation
        logger.info(f"Creating calendar event: {title} on {date} from {start_time} to {end_time}")
        
        # Load credentials
        current_dir = os.path.dirname(os.path.abspath(__file__))
        token_path = os.path.join(current_dir, 'token.json')
        
        if not os.path.exists(token_path):
            return "I couldn't access your calendar. The authentication credentials are missing."
        
        creds = Credentials.from_authorized_user_file(
            token_path,
            ['https://www.googleapis.com/auth/calendar']
        )
        
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                return "I couldn't access your calendar due to authentication issues."
        
        # Format start and end times
        start_datetime = f"{date}T{start_time}:00"
        end_datetime = f"{date}T{end_time}:00"
        
        # Create event
        event = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': start_datetime,
                'timeZone': 'Asia/Kolkata',  # Indian timezone
            },
            'end': {
                'dateTime': end_datetime,
                'timeZone': 'Asia/Kolkata',  # Indian timezone
            },
        }
        
        # Build the service
        service = build('calendar', 'v3', credentials=creds)
        
        # Create the event
        event_result = service.events().insert(calendarId='primary', body=event).execute()
        
        # Format the confirmation message
        event_date = datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%A, %B %d, %Y")
        confirmation = (
            f"I've scheduled '{title}' for {event_date} from {start_time} to {end_time}. "
            f"The event has been added to your Google Calendar."
        )
        
        logger.info(f"Successfully added calendar event: {event_result.get('htmlLink')}")
        return confirmation
        
    except Exception as e:
        logger.error(f"Error creating calendar event: {str(e)}")
        return f"I'm having trouble adding this event to your calendar: {str(e)}"


async def add_calendar_event(context, args=None):
    """
    Main function that extracts arguments and creates a calendar event if all required information is available.
    
    Args:
        context: The call context
        args: Not used as arguments are extracted from context
    
    Returns:
        A confirmation message about the event creation or an error message
    """
    try:
        # Check if this function was recently called and failed
        if 'add_calendar_event' in context.active_functions:
            last_status = context.active_functions.get('add_calendar_event', {}).get('status')
            last_attempt = context.active_functions.get('add_calendar_event', {}).get('last_attempt', 0)
            current_time = datetime.datetime.now().timestamp()
            
            # If function was called in the last 10 seconds and failed, don't retry automatically
            if last_status == 'failed' and (current_time - last_attempt < 10):
                return "I'm still having trouble scheduling your event. Let me know if you'd like to try again with complete details."
        
        # Mark function as processing
        context.active_functions['add_calendar_event'] = {
            'status': 'processing',
            'last_attempt': datetime.datetime.now().timestamp()
        }
        
        # First extract the arguments from the conversation context
        extracted_args, error_message = await extract_calendar_event_args(context)
        
        if error_message:
            # Arguments extraction failed, mark function as failed
            context.active_functions['add_calendar_event'] = {
                'status': 'failed',
                'last_attempt': datetime.datetime.now().timestamp()
            }
            return error_message
        
        # All required arguments are available, proceed with calendar event creation
        await asyncio.sleep(1)  # Simulating some processing time
        result = await create_calendar_event(extracted_args)
        
        if "error" in result.lower() or "trouble" in result.lower() or "couldn't" in result.lower():
            # Calendar event creation failed
            context.active_functions['add_calendar_event'] = {
                'status': 'failed',
                'last_attempt': datetime.datetime.now().timestamp()
            }
        else:
            # Success
            context.active_functions['add_calendar_event'] = {
                'status': 'success',
                'last_attempt': datetime.datetime.now().timestamp()
            }
            # Store the collected data
            context.collected_data['calendar_event'] = extracted_args
            
        return result
        
    except Exception as e:
        logger.error(f"Error in add_calendar_event: {str(e)}")
        # Mark function as failed
        context.active_functions['add_calendar_event'] = {
            'status': 'failed',
            'last_attempt': datetime.datetime.now().timestamp()
        }
        return f"I encountered an unexpected error while scheduling your event: {str(e)}"
