import importlib
import json
import os
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from groq import AsyncGroq
import anthropic
from openai import AsyncOpenAI

from functions.function_manifest import tools
from logger_config import get_logger
from services.call_context import CallContext
from services.event_emmiter import EventEmitter
from services.rag_service import rag_service

logger = get_logger("LLMService")

class AbstractLLMService(EventEmitter, ABC):
    def __init__(self, context: CallContext):
        super().__init__()
        self.system_message = context.system_message
        self.initial_message = context.initial_message
        self.context = context
        self.user_context = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": self.initial_message}
        ]
        self.partial_response_index = 0
        self.available_functions = {}
        for tool in tools:
            function_name = tool['function']['name']
            module = importlib.import_module(f'functions.{function_name}')
            self.available_functions[function_name] = getattr(module, function_name)
        self.sentence_buffer = ""
        context.user_context = self.user_context

    async def initialize_rag(self):
        """Initialize RAG service"""
        await rag_service.initialize()

    async def get_rag_context(self, user_message: str) -> str:
        """Get relevant context from RAG for the current user message"""
        if not self.context.user_phone_number:
            return ""
        
        try:
            relevant_contexts = await rag_service.retrieve_relevant_context(
                phone_number=self.context.user_phone_number,
                current_query=user_message,
                exclude_call_sid=self.context.call_sid
            )
            
            if not relevant_contexts:
                return ""
            
            # Format relevant contexts into a string
            context_parts = ["Previous relevant conversations:"]
            
            for i, context in enumerate(relevant_contexts):
                context_parts.append(f"\n{i+1}. From {context['timestamp'][:10]}:")
                context_parts.append(f"   User: {context['user_message']}")
                context_parts.append(f"   Assistant: {context['assistant_message']}")
                context_parts.append(f"   (Similarity: {context['similarity_score']:.2f})")
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Failed to get RAG context: {e}")
            return ""

    async def store_conversation_turn(self, user_message: str, assistant_message: str, interaction_count: int):
        """Store the conversation turn in RAG"""
        if not self.context.user_phone_number or not self.context.call_sid:
            return
        
        try:
            await rag_service.store_conversation_turn(
                phone_number=self.context.user_phone_number,
                call_sid=self.context.call_sid,
                user_message=user_message,
                assistant_message=assistant_message,
                interaction_count=interaction_count,
                metadata={
                    "system_message": self.system_message,
                    "start_time": self.context.start_time
                }
            )
        except Exception as e:
            logger.error(f"Failed to store conversation turn: {e}")

    async def get_caller_summary(self) -> str:
        """Get a summary of the caller's previous interactions"""
        if not self.context.user_phone_number:
            return ""
        
        try:
            return await rag_service.get_caller_history_summary(self.context.user_phone_number)
        except Exception as e:
            logger.error(f"Failed to get caller summary: {e}")
            return ""

    def set_call_context(self, context: CallContext):
        self.context = context
        self.user_context = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": context.initial_message}
        ]
        context.user_context = self.user_context
        self.system_message = context.system_message
        self.initial_message = context.initial_message

    @abstractmethod
    async def completion(self, text: str, interaction_count: int, role: str = 'user', name: str = 'user'):
        pass

    def reset(self):
        self.partial_response_index = 0

    def validate_function_args(self, args):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            logger.info('Warning: Invalid function arguments returned by LLM:', args)
            return {}

    @staticmethod
    def convert_openai_tools_to_anthropic(openai_tools):
        anthropic_tools = []
        for tool in openai_tools:
            if tool['type'] == 'function':
                function = tool['function']
                anthropic_tool = {
                    "name": function['name'],
                    "description": function.get('description', ''),
                    "input_schema": {
                        "type": "object",
                        "properties": function.get('parameters', {}).get('properties', {}),
                        "required": function.get('parameters', {}).get('required', [])
                    }
                }
                
                # Remove 'description' from individual properties if present
                for prop in anthropic_tool['input_schema']['properties'].values():
                    prop.pop('description', None)
                
                # If there are no properties, set an empty dict
                if not anthropic_tool['input_schema']['properties']:
                    anthropic_tool['input_schema']['properties'] = {}
                
                anthropic_tools.append(anthropic_tool)
        
        return anthropic_tools

    def split_into_sentences(self, text):
        # Split the text into sentences, keeping the separators
        sentences = re.split(r'([.!?])', text)
        # Pair the sentences with their separators
        sentences = [''.join(sentences[i:i+2]) for i in range(0, len(sentences), 2)]
        return sentences

    async def emit_complete_sentences(self, text, interaction_count):
        self.sentence_buffer += text
        sentences = self.split_into_sentences(self.sentence_buffer)
        
        # Emit all complete sentences
        for sentence in sentences[:-1]:
            await self.emit('llmreply', {
                "partialResponseIndex": self.partial_response_index,
                "partialResponse": sentence.strip()
            }, interaction_count)
            self.partial_response_index += 1
        
        # Keep the last (potentially incomplete) sentence in the buffer
        self.sentence_buffer = sentences[-1] if sentences else ""

    async def emit_function_progress(self, message, status, interaction_count):
        """Emit function progress updates"""
        await self.emit('function_progress', {
            'message': message,
            'status': status
        }, interaction_count)

class OpenAIService(AbstractLLMService):
    def __init__(self, context: CallContext):
        super().__init__(context)
        self.openai = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def completion(self, text: str, interaction_count: int, role: str = 'user', name: str = 'user'):
        try:
            # Check for recursive function calls to prevent loops
            if role == 'function' and name in ['send_whatsapp_info', 'send_whatsapp_summary', 'send_email_info', 'send_email_summary']:
                # If we're getting a response from these functions, don't immediately 
                # send it back to OpenAI as it tends to trigger the same function again
                self.user_context.append({"role": role, "content": text, "name": name})
                
                # Add a synthetic assistant response to prevent the loop
                synthetic_response = "I've processed your request. Is there anything else you'd like to know?"
                self.user_context.append({"role": "assistant", "content": synthetic_response})
                
                # Send the synthetic response to TTS
                await self.emit('llmreply', {
                    "partialResponseIndex": self.partial_response_index,
                    "partialResponse": synthetic_response
                }, interaction_count)
                self.partial_response_index += 1
                
                return
            
            self.user_context.append({"role": role, "content": text, "name": name})
            
            # Get RAG context for user messages
            enhanced_system_message = self.system_message
            if role == 'user' and name == 'user':
                try:
                    # Get caller history summary
                    caller_summary = await self.get_caller_summary()
                    if caller_summary:
                        enhanced_system_message += f"\n\n{caller_summary}"
                    
                    # Get relevant context for current query
                    rag_context = await self.get_rag_context(text)
                    if rag_context:
                        enhanced_system_message += f"\n\n{rag_context}"
                        
                except Exception as e:
                    logger.error(f"Failed to get RAG context: {e}")
            
            messages = [{"role": "system", "content": enhanced_system_message}] + self.user_context
        
            stream = await self.openai.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                stream=True,
            )

            complete_response = ""
            function_name = ""
            function_args = ""

            async for chunk in stream:
                delta = chunk.choices[0].delta
                content = delta.content or ""
                tool_calls = delta.tool_calls

                if tool_calls:
                    for tool_call in tool_calls:
                        if tool_call.function and tool_call.function.name:
                            logger.info(f"Function call detected: {tool_call.function.name}")
                            function_name = tool_call.function.name
                            function_args += tool_call.function.arguments or ""
                else:
                    complete_response += content
                    await self.emit_complete_sentences(content, interaction_count)

                if chunk.choices[0].finish_reason == "tool_calls":
                    logger.info(f"Function call detected: {function_name}")
                    function_to_call = self.available_functions[function_name]
                    
                    # Improved function argument handling
                    try:
                        parsed_args = self.validate_function_args(function_args)
                        logger.info(f"Function arguments for {function_name}: {parsed_args}")
                        
                        # Extra validation for WhatsApp info function to prevent empty queries
                        if function_name == "send_whatsapp_info" and "query" not in parsed_args:
                            # Extract potential query from recent user context
                            recent_user_msg = ""
                            for msg in reversed(self.user_context[-5:]):
                                if msg['role'] == 'user':
                                    recent_user_msg = msg['content']
                                    break
                                    
                            # Try to extract a topic from the recent message
                            potential_query = ""
                            if "about" in recent_user_msg.lower():
                                potential_query = recent_user_msg.lower().split("about")[-1].strip()
                                if potential_query.startswith("the "):
                                    potential_query = potential_query[4:]
                            
                            if potential_query:
                                parsed_args["query"] = potential_query
                                logger.info(f"Added missing query parameter: {potential_query}")
                            else:
                                # Skip function call if we still can't determine the query
                                logger.warning("Skipping send_whatsapp_info call due to missing query parameter")
                                await self.emit('llmreply', {
                                    "partialResponseIndex": None,
                                    "partialResponse": "I'm not sure what information you'd like me to send. Could you please tell me specifically what you want to know about?"
                                }, interaction_count)
                                continue
                    except Exception as e:
                        logger.error(f"Error parsing function arguments: {str(e)}. Raw args: {function_args}")
                        parsed_args = {}
                    
                    tool_data = next((tool for tool in tools if tool['function']['name'] == function_name), None)
                    say = tool_data['function']['say']

                    await self.emit('llmreply', {
                        "partialResponseIndex": None,
                        "partialResponse": say
                    }, interaction_count)

                    # Emit initial function progress
                    await self.emit_function_progress(
                        f"Starting {function_name.replace('_', ' ')}...",
                        'started',
                        interaction_count
                    )

                    self.user_context.append({"role": "assistant", "content": say})
                    
                    function_response = await function_to_call(self.context, parsed_args)
                    
                    # Emit completion function progress
                    await self.emit_function_progress(
                        function_response,
                        'completed',
                        interaction_count
                    )
                                        
                    logger.info(f"Function {function_name} called with args: {parsed_args}")

                    if function_name != "end_call":
                        # For WhatsApp functions, we prevent the recursive call by handling differently
                        if function_name in ['send_whatsapp_info', 'send_whatsapp_summary']:
                            # Store response but don't trigger another completion
                            self.user_context.append({"role": "function", "name": function_name, "content": function_response})
                            
                            # Add a synthetic assistant response to prevent the loop
                            synthetic_response = "Is there anything else you'd like to know?"
                            self.user_context.append({"role": "assistant", "content": synthetic_response})
                            
                            # Send the synthetic response to TTS
                            await self.emit('llmreply', {
                                "partialResponseIndex": self.partial_response_index,
                                "partialResponse": synthetic_response
                            }, interaction_count)
                            self.partial_response_index += 1
                        else:
                            # Normal recursive call for other functions
                            await self.completion(function_response, interaction_count, 'function', function_name)

            # Emit any remaining content in the buffer
            if self.sentence_buffer.strip():
                await self.emit('llmreply', {
                    "partialResponseIndex": self.partial_response_index,
                    "partialResponse": self.sentence_buffer.strip()
                }, interaction_count)
                self.sentence_buffer = ""

            self.user_context.append({"role": "assistant", "content": complete_response})
            
            # Store conversation turn in RAG if this was a user message
            if role == 'user' and name == 'user' and complete_response.strip():
                try:
                    await self.store_conversation_turn(text, complete_response, interaction_count)
                except Exception as e:
                    logger.error(f"Failed to store conversation turn in RAG: {e}")

        except Exception as e:
            logger.error(f"Error in OpenAIService completion: {str(e)}")

class GroqService(AbstractLLMService):
    def __init__(self, context: CallContext):
        super().__init__(context)
        self.groq = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

    async def completion(self, text: str, interaction_count: int, role: str = 'user', name: str = 'user'):
        try:
            # Check for recursive function calls to prevent loops
            if role == 'function' and name in ['send_whatsapp_info', 'send_whatsapp_summary', 'send_email_info', 'send_email_summary']:
                # If we're getting a response from these functions, don't immediately 
                # send it back to Groq as it tends to trigger the same function again
                self.user_context.append({"role": role, "content": text, "name": name})
                
                # Add a synthetic assistant response to prevent the loop
                synthetic_response = "I've processed your request. Is there anything else you'd like to know?"
                self.user_context.append({"role": "assistant", "content": synthetic_response})
                
                # Send the synthetic response to TTS
                await self.emit('llmreply', {
                    "partialResponseIndex": self.partial_response_index,
                    "partialResponse": synthetic_response
                }, interaction_count)
                self.partial_response_index += 1
                
                return
            
            self.user_context.append({"role": role, "content": text, "name": name})
            
            # Get RAG context for user messages
            enhanced_system_message = self.system_message
            if role == 'user' and name == 'user':
                try:
                    # Get caller history summary
                    caller_summary = await self.get_caller_summary()
                    if caller_summary:
                        enhanced_system_message += f"\n\n{caller_summary}"
                    
                    # Get relevant context for current query
                    rag_context = await self.get_rag_context(text)
                    if rag_context:
                        enhanced_system_message += f"\n\n{rag_context}"
                        
                except Exception as e:
                    logger.error(f"Failed to get RAG context: {e}")
            
            messages = [{"role": "system", "content": enhanced_system_message}] + self.user_context
        
            stream = await self.groq.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True,
            )
        
            complete_response = ""
            function_name = ""
            function_args = ""
        
            async for chunk in stream:
                delta = chunk.choices[0].delta
                content = delta.content or ""
                tool_calls = delta.tool_calls
                if tool_calls:
                    for tool_call in tool_calls:
                        if tool_call.function and tool_call.function.name:
                            logger.info(f"Function call detected: {tool_call.function.name}")
                            function_name = tool_call.function.name
                            function_args += tool_call.function.arguments or ""
                else:
                    complete_response += content
                    await self.emit_complete_sentences(content, interaction_count)

                if chunk.choices[0].finish_reason == "tool_calls":
                    logger.info(f"Function call detected: {function_name}")
                    function_to_call = self.available_functions[function_name]
                    
                    # Improved function argument handling
                    try:
                        parsed_args = self.validate_function_args(function_args)
                        logger.info(f"Function arguments for {function_name}: {parsed_args}")
                        
                        # Enhanced validation for email and WhatsApp info functions
                        if function_name in ["send_email_info", "send_whatsapp_info"] and ("query" not in parsed_args or not parsed_args.get("query", "").strip()):
                            # Extract potential query from recent user context
                            recent_user_msg = ""
                            for msg in reversed(self.user_context[-5:]):
                                if msg['role'] == 'user':
                                    recent_user_msg = msg['content']
                                    break
                                    
                            # Try to extract a topic from the recent message using multiple patterns
                            potential_query = self.extract_query_from_message(recent_user_msg)
                            
                            if potential_query:
                                parsed_args["query"] = potential_query
                                logger.info(f"Added missing query parameter: {potential_query}")
                            else:
                                # Skip function call if we still can't determine the query
                                logger.warning(f"Skipping {function_name} call due to missing or empty query parameter")
                                await self.emit('llmreply', {
                                    "partialResponseIndex": None,
                                    "partialResponse": "I'm not sure what information you'd like me to send. Could you please tell me specifically what you want to know about?"
                                }, interaction_count)
                                continue
                                
                        # Handle email address extraction for email functions
                        if function_name in ["send_email_info", "send_email_summary"] and not parsed_args.get("to_email"):
                            if hasattr(self.context, 'user_email') and self.context.user_email:
                                parsed_args["to_email"] = self.context.user_email
                                logger.info(f"Added stored user email: {self.context.user_email}")
                                
                    except Exception as e:
                        logger.error(f"Error parsing function arguments: {str(e)}. Raw args: {function_args}")
                        parsed_args = {}

                    tool_data = next((tool for tool in tools if tool['function']['name'] == function_name), None)
                    say = tool_data['function']['say']

                    await self.emit('llmreply', {
                        "partialResponseIndex": None,
                        "partialResponse": say
                    }, interaction_count)

                    # Emit initial function progress
                    await self.emit_function_progress(
                        f"Starting {function_name.replace('_', ' ')}...",
                        'started',
                        interaction_count
                    )

                    self.user_context.append({"role": "assistant", "content": say})
                    
                    function_response = await function_to_call(self.context, parsed_args)
                    
                    # Emit completion function progress
                    await self.emit_function_progress(
                        function_response,
                        'completed',
                        interaction_count
                    )
                                        
                    logger.info(f"Function {function_name} called with args: {parsed_args}")

                    if function_name != "end_call":
                        # For WhatsApp and email functions, we prevent the recursive call by handling differently
                        if function_name in ['send_whatsapp_info', 'send_whatsapp_summary', 'send_email_info', 'send_email_summary']:
                            # Store response but don't trigger another completion
                            self.user_context.append({"role": "function", "name": function_name, "content": function_response})
                            
                            # Add a synthetic assistant response to prevent the loop
                            synthetic_response = "Is there anything else you'd like to know?"
                            self.user_context.append({"role": "assistant", "content": synthetic_response})
                            
                            # Send the synthetic response to TTS
                            await self.emit('llmreply', {
                                "partialResponseIndex": self.partial_response_index,
                                "partialResponse": synthetic_response
                            }, interaction_count)
                            self.partial_response_index += 1
                        else:
                            # Normal recursive call for other functions
                            await self.completion(function_response, interaction_count, 'function', function_name)

            if self.sentence_buffer.strip():
                await self.emit('llmreply', {
                    "partialResponseIndex": self.partial_response_index,
                    "partialResponse": self.sentence_buffer.strip()
                }, interaction_count)
                self.sentence_buffer = ""

            self.user_context.append({"role": "assistant", "content": complete_response})
            
            # Store conversation turn in RAG if this was a user message
            if role == 'user' and name == 'user' and complete_response.strip():
                try:
                    await self.store_conversation_turn(text, complete_response, interaction_count)
                except Exception as e:
                    logger.error(f"Failed to store conversation turn in RAG: {e}")

        except Exception as e:
            logger.error(f"Error in GroqService completion: {str(e)}")


class AnthropicService(AbstractLLMService):
    def __init__(self, context: CallContext):
        super().__init__(context)
        self.client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        # Add a dummy user message to ensure the first message is from the user
        self.user_context = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": self.initial_message}
        ]

    async def completion(self, text: str, interaction_count: int, role: str = 'user', name: str = 'user'):
        try:
            self.user_context.append({"role": role, "content": text})
            
            # Get RAG context for user messages
            enhanced_system_message = self.system_message
            if role == 'user' and name == 'user':
                try:
                    # Get caller history summary
                    caller_summary = await self.get_caller_summary()
                    if caller_summary:
                        enhanced_system_message += f"\n\n{caller_summary}"
                    
                    # Get relevant context for current query
                    rag_context = await self.get_rag_context(text)
                    if rag_context:
                        enhanced_system_message += f"\n\n{rag_context}"
                        
                except Exception as e:
                    logger.error(f"Failed to get RAG context: {e}")
            
            messages = [{"role": msg["role"], "content": msg["content"]} for msg in self.user_context]
            
            async with self.client.messages.stream(
                model="claude-3-opus-20240229",
                max_tokens=300,
                system=enhanced_system_message,
                messages=messages,
                tools=self.convert_openai_tools_to_anthropic(tools),
            ) as stream:
                complete_response = ""
                async for event in stream:
                    if event.type == "text":
                        content = event.text
                        complete_response += content
                        await self.emit_complete_sentences(content, interaction_count)
                    elif event.type == "tool_call":
                        function_name = event.tool_call.function.name
                        function_args = event.tool_call.function.arguments
                        logger.info(f"Function call detected: {function_name}")
                        function_to_call = self.available_functions[function_name]
                        function_args = self.validate_function_args(function_args)
                        
                        tool_data = next((tool for tool in tools if tool['function']['name'] == function_name), None)
                        say = tool_data['function']['say']

                        await self.emit('llmreply', {
                            "partialResponseIndex": None,
                            "partialResponse": say
                        }, interaction_count)

                        function_response = await function_to_call(function_args)
                                            
                        logger.info(f"Function {function_name} called with args: {function_args}")

                        if function_name != "end_call":
                            await self.completion(function_response, interaction_count, 'function', function_name)

                # Emit any remaining content in the buffer
                if self.sentence_buffer.strip():
                    await self.emit('llmreply', {
                        "partialResponseIndex": self.partial_response_index,
                        "partialResponse": self.sentence_buffer.strip()
                    }, interaction_count)
                    self.sentence_buffer = ""

                final_message = await stream.get_final_message()
                self.user_context.append({"role": "assistant", "content": final_message.content[0].text})
                
                # Store conversation turn in RAG if this was a user message
                if role == 'user' and name == 'user' and final_message.content[0].text.strip():
                    try:
                        await self.store_conversation_turn(text, final_message.content[0].text, interaction_count)
                    except Exception as e:
                        logger.error(f"Failed to store conversation turn in RAG: {e}")

        except Exception as e:
            logger.error(f"Error in AnthropicService completion: {str(e)}")

class LLMFactory:
    @staticmethod
    def get_llm_service(service_name: str, context: CallContext) -> AbstractLLMService:
        if service_name.lower() == "openai":
            return OpenAIService(context)
        elif service_name.lower() == "anthropic":
            return AnthropicService(context)
        elif service_name.lower() == "groq":
            return GroqService(context)
        else:
            raise ValueError(f"Unsupported LLM service: {service_name}")