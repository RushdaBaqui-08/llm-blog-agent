import os
from pydantic import BaseModel, Field, field_validator
from typing import Literal, List
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from dotenv import load_dotenv

load_dotenv()

class ImageSpec(BaseModel):
    placeholder: str = Field(..., description="e.g. [[IMAGE_1]]")
    filename: str = Field(..., description="Save under images/, e.g. qkv_flow.png")
    alt: str
    caption: str
    prompt: str = Field(..., description="Prompt to send to the image model.")
    size: Literal["1024x1024", "1024x1536", "1536x1024"] = "1024x1024"
    quality: Literal["low", "medium", "high"] = "medium"

    @field_validator('placeholder', mode='before')
    @classmethod
    def clean_placeholder(cls, v):
        if isinstance(v, list):
            while isinstance(v, list) and len(v) > 0:
                v = v[0]
        if not isinstance(v, str):
            v = str(v)
        v = v.strip("[] ")
        return f"[[{v}]]"

class GlobalImagePlan(BaseModel):
    md_with_placeholders: str
    images: List[ImageSpec] = Field(default_factory=list)

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
    plan_wrapper = GroqStructuredOutputWrapper(model, GlobalImagePlan)
    
    print("Testing GlobalImagePlan...")
    res = plan_wrapper.invoke([
        SystemMessage(content="You are an editor. Insert image placeholders into the markdown body."),
        HumanMessage(content="Blog kind: explainer\nTopic: Effects of AI on Agriculture Farming\n\n# Effects of AI on Agriculture\nAI is revolutionizing farming. Drones and sensors monitor crop health in real-time.")
    ])
    print("Type:", type(res))
    print("Result:", res)

if __name__ == "__main__":
    main()
