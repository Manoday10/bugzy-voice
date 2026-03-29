from dotenv import load_dotenv
import os
import boto3
import json
import logging
from typing import List, Union, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

load_dotenv()

class BedrockLLM:
    """
    AWS Bedrock LLM wrapper compatible with LangChain's ChatOpenAI interface.
    """

    def __init__(self, model: str = "qwen.qwen3-32b-v1:0",
                 temperature: float = 0.7, max_tokens: int = 12000, top_p: float = 0.9, **kwargs):
        self.logger = logging.getLogger(__name__)

        # Always use Qwen3 model regardless of input
        self.model = "qwen.qwen3-32b-v1:0"
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

        # Load real AWS credentials
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_session_token = os.getenv("AWS_SESSION_TOKEN")  # optional, only if using STS
        aws_region = "ap-south-1"   # QWEN is ONLY available in us-east-1

        # Create Bedrock Runtime client
        if aws_session_token:
            self.bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=aws_region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                aws_session_token=aws_session_token
            )
        else:
            self.bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=aws_region,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )

    def _convert_messages_to_bedrock_format(self, messages):
        if isinstance(messages, str):
            return [{"role": "user", "content": messages}]

        bedrock_msgs = []
        for msg in messages:
            if isinstance(msg, dict):
                bedrock_msgs.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            elif isinstance(msg, HumanMessage):
                bedrock_msgs.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                bedrock_msgs.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                bedrock_msgs.append({"role": "system", "content": msg.content})
            else:
                bedrock_msgs.append({"role": "user", "content": str(msg)})
        return bedrock_msgs

    def invoke(self, messages, **kwargs):
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        top_p = kwargs.get("top_p", self.top_p)

        bedrock_messages = self._convert_messages_to_bedrock_format(messages)

        body = json.dumps({
            "messages": bedrock_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p
        })

        try:
            response = self.bedrock_client.invoke_model(
                modelId=self.model,
                body=body,
                contentType="application/json",
                accept="application/json"
            )

            response_body = json.loads(response["body"].read())
            content = response_body["choices"][0]["message"]["content"]

            class BedrockResponse:
                def __init__(self, content):
                    self.content = content

            return BedrockResponse(content)

        except Exception as e:
            self.logger.error("❌ Bedrock API Error: %s", e)
            raise


ChatBedRockLLM = BedrockLLM