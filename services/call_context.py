from typing import List, Optional, Dict, Any


class CallContext:
    """Store context for the current call."""
    def __init__(self):
        # Unique identifier for the media stream
        self.stream_sid: Optional[str] = None
        # Unique identifier for the call
        self.call_sid: Optional[str] = None
        # Flag to indicate if the call has ended
        self.call_ended: bool = False
        # List to store user interactions and context
        self.user_context: List = []
        # System message to guide the conversation
        self.system_message: str = ""
        # Initial message to start the conversation
        self.initial_message: str = ""
        # Timestamp for when the call started
        self.start_time: Optional[str] = None
        # Timestamp for when the call ended
        self.end_time: Optional[str] = None
        # Final status of the call (e.g., completed, failed)
        self.final_status: Optional[str] = None
        # Track active function state for argument collection
        self.active_functions: Dict[str, Dict[str, Any]] = {}
        # Store collected data during the call
        self.collected_data: Dict[str, Any] = {}
        # Store the user's phone number for future reference
        self.user_phone_number: Optional[str] = None
        # Store the user's email for sending information
        self.user_email: Optional[str] = None

