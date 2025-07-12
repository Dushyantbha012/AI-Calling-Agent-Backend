tools = [
    {
        "type": "function",
        "function": {
            "name": "transfer_call",
            "description": "Transfer call to a human representative only if the user explicitly requests to speak with a person or if you cannot solve their problem.",
            "parameters": {
                "type": "object",
                "properties": {}
            },
            "say": "I'll transfer you to a human representative who can help you further. Please hold the line for a moment."
        }
    },    
    
    {
        "type": "function",
        "function": {
            "name": "end_call",
            "description": "End the current call. Use this when the conversation has reached a natural conclusion, the user's query has been fully addressed, or the user asks to end the call.",
            "parameters": {
                "type": "object",
                "properties": {}
            },
            "say": "Thank you for calling. Have a great day! Goodbye."
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "add_calendar_event",
            "description": "Add an event to the user's Google Calendar. Use this when a user wants to schedule an appointment, meeting, or any other event. Collect all necessary details like date, time, title, and duration in a natural conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title or name of the event"
                    },
                    "date": {
                        "type": "string",
                        "description": "The date of the event in YYYY-MM-DD format"
                    },
                    "start_time": {
                        "type": "string",
                        "description": "The starting time of the event in HH:MM format 24-hour"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "The ending time of the event in HH:MM format 24-hour"
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of the event"
                    }
                },
                "required": ["title", "date", "start_time", "end_time"]
            },
            "say": "I'll schedule that event for you. Just a moment while I add it to your calendar."
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp_summary",
            "description": "Send a summary of the conversation to the user's WhatsApp. ONLY use this when the user EXPLICITLY requests a summary to be sent to WhatsApp. DO NOT use this function automatically at the end of calls or repeatedly during the same call unless specifically requested again by the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_number": {
                        "type": "string",
                        "description": "The phone number to send the WhatsApp message to (with country code, e.g., +1234567890)"
                    },
                    "include_transcript": {
                        "type": "boolean",
                        "description": "Whether to include the full conversation transcript in the summary"
                    },
                    "force_send": {
                        "type": "boolean",
                        "description": "Force send even if a summary was sent recently (use only when user explicitly asks again for a summary)"
                    }
                },
                "required": []
            },
            "say": "I'll send a summary of our conversation to your WhatsApp. You should receive it shortly."
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp_info",
            "description": "Send specific information to the user's WhatsApp. Use this function ONLY when a user EXPLICITLY asks for information to be sent to their WhatsApp AND you know exactly what topic they want information about. Never call this function with an empty query parameter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SPECIFIC information topic the user wants sent (e.g., 'Hyderabad', 'python programming', 'healthy recipes'). This must be extracted from user's request and CANNOT be empty."
                    },
                    "info_type": {
                        "type": "string",
                        "description": "General category of information"
                    },
                    "to_number": {
                        "type": "string",
                        "description": "The phone number to send the WhatsApp message to (with country code, e.g., +1234567890)"
                    },
                    "custom_text": {
                        "type": "string",
                        "description": "Custom text to send instead of generating content"
                    }
                },
                "required": ["query"]
            },
            "say": "I'll send that information to your WhatsApp right away. You should receive it shortly."
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "send_email_summary",
            "description": "Send a summary of the conversation to the user's email address. Use this when the user explicitly asks for an email summary of the call or wants the conversation details sent via email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_email": {
                        "type": "string",
                        "description": "The email address to send the summary to"
                    },
                    "include_transcript": {
                        "type": "boolean",
                        "description": "Whether to include the full conversation transcript in the email",
                        "default": False
                    }
                },
                "required": []
            },
            "say": "I'll send a summary of our conversation to your email. You should receive it shortly."
        }
    },
    
    {
        "type": "function",
        "function": {
            "name": "send_email_info",
            "description": "Send specific information to the user's email address. Use this function ONLY when a user EXPLICITLY asks for information to be sent to their email AND you know exactly what topic they want information about. Never call this function with an empty query parameter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SPECIFIC information topic the user wants sent (e.g., 'Hyderabad', 'python programming', 'healthy recipes'). This must be extracted from user's request and CANNOT be empty."
                    },
                    "info_type": {
                        "type": "string",
                        "description": "General category of information"
                    },
                    "to_email": {
                        "type": "string",
                        "description": "The email address to send the information to"
                    },
                    "custom_text": {
                        "type": "string",
                        "description": "Custom text to send instead of generating content"
                    }
                },
                "required": ["query"]
            },
            "say": "I'll send that information to your email right away. You should receive it shortly."
        }
    }
]

