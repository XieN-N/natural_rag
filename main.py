import os
import json
import time
import uuid
import asyncio
from pydantic import BaseModel
import marvin

# Import sync and async completion classes
from openai.resources.chat.completions import Completions, AsyncCompletions

os.environ["OPENAI_API_KEY"] = os.environ['VSEGPT_KEY']
os.environ["OPENAI_BASE_URL"] = os.environ['VSEGPT_BASE_URL']
marvin.settings.__dict__['agent_model'] = 'openai:openai/gpt-5-nano'

# --- START: Robust Stream Logger Setup ---
os.makedirs("logs", exist_ok=True)

class LoggedStreamContext:
    """
    A wrapper class that behaves like an OpenAI AsyncStream.
    It supports 'async with', 'async for', and logs the accumulated data upon completion.
    """
    def __init__(self, original_stream, input_messages):
        self.stream = original_stream
        self.input_messages = input_messages
        self.accumulated_content = []
        self.accumulated_tool_calls = {} # {index: {id, name, args}}

    # Context Manager Protocol (Fixes your TypeError)
    async def __aenter__(self):
        # Allow the original stream to initialize if needed
        if hasattr(self.stream, '__aenter__'):
            await self.stream.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Ensure original stream cleans up
        if hasattr(self.stream, '__aexit__'):
            await self.stream.__aexit__(exc_type, exc_val, exc_tb)

    # Iterator Protocol (Allows 'async for chunk in ...')
    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            # Get next chunk from OpenAI
            chunk = await self.stream.__anext__()
            
            # --- Capture Data Logic ---
            if len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                
                # Acccumulate Text
                if delta.content:
                    self.accumulated_content.append(delta.content)
                
                # Accumulate Tool Calls (JSON fragments)
                if delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        idx = tool_call.index
                        if idx not in self.accumulated_tool_calls:
                            self.accumulated_tool_calls[idx] = {"id": "", "name": "", "arguments": ""}
                            
                        if tool_call.id:
                            self.accumulated_tool_calls[idx]["id"] = tool_call.id
                        if tool_call.function and tool_call.function.name:
                            self.accumulated_tool_calls[idx]["name"] = tool_call.function.name
                        if tool_call.function and tool_call.function.arguments:
                            self.accumulated_tool_calls[idx]["arguments"] += tool_call.function.arguments
            # --------------------------

            return chunk

        except StopAsyncIteration:
            # Stream is done. Write the log file.
            self._save_log()
            raise

    def _save_log(self):
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        unique_id = uuid.uuid4().hex[:6]
        filename = f"logs/log_{timestamp}_{unique_id}.json"

        # Reconstruct full text
        full_content = "".join(self.accumulated_content)
        # Reconstruct tool calls list
        final_tool_calls = [v for k, v in self.accumulated_tool_calls.items()]

        log_data = {
            "timestamp": timestamp,
            "input_messages": self.input_messages,
            "raw_output_reconstructed": {
                "content": full_content if full_content else None,
                "tool_calls": final_tool_calls if final_tool_calls else None
            }
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        print(f"Logged stream to {filename}")


# Patching the Async Client
_orig_async_create = AsyncCompletions.create

async def logged_async_create(self, *args, **kwargs):
    # Execute Original Call
    response = await _orig_async_create(self, *args, **kwargs)
    
    # If streaming, return our Class Wrapper instead of the raw generator
    if kwargs.get("stream", False):
        return LoggedStreamContext(response, kwargs.get("messages", []))
    else:
        # (Optional) Handle non-streaming logs here if needed
        return response

AsyncCompletions.create = logged_async_create
# --- END: Robust Stream Logger Setup ---


class Relation(BaseModel):
    from_entity: str
    to_entity: str
    type: str

class DocumentInput(BaseModel):
    document: str
    relation_types: list[str]

class RelationOutput(BaseModel):
    relations: list[Relation]

test_input = DocumentInput(
    document="Apple Inc. was founded by Steve Jobs in Cupertino. The company acquired Beats Electronics in 2014.",
    relation_types=["FOUNDED_BY", "LOCATED_IN", "ACQUIRED"],
)

@marvin.fn
def extract_relations(input: DocumentInput) -> RelationOutput:
    """Extracts relations from the document."""
    ...

result = extract_relations(test_input)
print(result)
