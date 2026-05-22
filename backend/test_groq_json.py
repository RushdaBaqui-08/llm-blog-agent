import os
from pydantic import BaseModel, Field
from typing import Literal, List
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# Schemas
# -----------------------------
class RouterDecision(BaseModel):
    needs_research: bool
    mode: Literal["closed_book", "hybrid", "open_book"]
    reason: str
    queries: List[str] = Field(default_factory=list)
    max_results_per_query: int = Field(5)

class Task(BaseModel):
    id: int
    title: str
    goal: str = Field(..., description="One sentence describing what the reader should do/understand.")
    bullets: List[str] = Field(..., min_length=1, max_length=10)
    target_words: int = Field(..., description="Target words (120–550).")
    tags: List[str] = Field(default_factory=list)
    requires_research: bool = False
    requires_citations: bool = False
    requires_code: bool = False

class Plan(BaseModel):
    blog_title: str
    audience: str
    tone: str
    blog_kind: str = Field("explainer", description="Must be one of: explainer, tutorial, news_roundup, comparison, system_design")
    constraints: List[str] = Field(default_factory=list)
    tasks: List[Task]

# -----------------------------
# Wrapper
# -----------------------------
class GroqStructuredOutputWrapper:
    def __init__(self, llm_instance, schema, **kwargs):
        self.decider = llm_instance.with_structured_output(schema, method="json_mode", **kwargs)
        self.parser = PydanticOutputParser(pydantic_object=schema)
        self.format_instructions = self.parser.get_format_instructions()

    def invoke(self, input_messages, *args, **kwargs):
        instructions = (
            "\n\nCRITICAL: You MUST respond with a valid JSON object matching the JSON schema below.\n"
            "The output must conform strictly to the specified JSON schema structure. Do not invent extra keys.\n"
            f"{self.format_instructions}\n"
        )
        
        new_messages = []
        if isinstance(input_messages, list):
            system_msg_found = False
            for msg in input_messages:
                if isinstance(msg, SystemMessage):
                    new_messages.append(SystemMessage(content=msg.content + instructions))
                    system_msg_found = True
                else:
                    new_messages.append(msg)
            if not system_msg_found:
                new_messages.insert(0, SystemMessage(content="You are a helpful assistant.\n" + instructions))
        elif isinstance(input_messages, str):
            new_messages = [
                SystemMessage(content="You are a helpful assistant.\n" + instructions),
                HumanMessage(content=input_messages)
            ]
        else:
            new_messages = input_messages
            
        return self.decider.invoke(new_messages, *args, **kwargs)

def main():
    model = ChatGroq(model="llama-3.1-8b-instant")
    
    print("--- Testing RouterDecision ---")
    router_wrapper = GroqStructuredOutputWrapper(model, RouterDecision)
    res_router = router_wrapper.invoke([
        SystemMessage(content="You are a routing module for a technical blog planner."),
        HumanMessage(content="Topic: Effects of AI on Agriculture Farming\nAs-of: 2026-05-21")
    ])
    print("Router Decision type:", type(res_router))
    print("Router Decision result:", res_router)
    
    print("\n--- Testing Plan (Nested) ---")
    plan_wrapper = GroqStructuredOutputWrapper(model, Plan)
    res_plan = plan_wrapper.invoke([
        SystemMessage(content="You are a senior technical writer. Outline a blog post."),
        HumanMessage(content="Topic: Effects of AI on Agriculture Farming\nAs-of: 2026-05-21\nMode: open_book")
    ])
    print("Plan type:", type(res_plan))
    print("Plan result:", res_plan)

if __name__ == "__main__":
    main()
