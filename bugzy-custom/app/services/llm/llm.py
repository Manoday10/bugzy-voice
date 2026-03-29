import requests
import json
import os
import base64
import io
import logging
from PIL import Image
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

AWS_API_KEY = os.getenv("AWS_BEARER_TOKEN_BEDROCK")

SUPPORTED_MODELS = {
    "llama-3b": "us.meta.llama3-2-3b-instruct-v1:0",
    "llama-11b": "us.meta.llama3-2-11b-instruct-v1:0", 
    "mistral-7b": "mistral.mistral-7b-instruct-v0:2",
    "mistral-large": "mistral.mistral-large-2402-v1:0",
    "mixtral-8x7b": "mistral.mixtral-8x7b-instruct-v0:1",
    "qwen-32b": "qwen.qwen3-32b-v1:0",
    "qwen-coder": "qwen.qwen3-coder-30b-a3b-v1:0"
}

def process_image(path, max_size=1120):
    img = Image.open(path).convert("RGB")
    if img.width > max_size or img.height > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    fmt = img.format if img.format else "JPEG"
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return b64, f"image/{fmt.lower()}"

def invoke_llama_api(
    query: str,
    model_type: str = "text",
    image_path: str = None,
    temperature: float = 0.8,
    top_p: float = 0.9,
    max_tokens: int = 1024,
    model_name: str = "llama-11b",
    use_data_url: bool = False
):

    if model_name not in SUPPORTED_MODELS:
        raise ValueError(f"Choose model from: {list(SUPPORTED_MODELS.keys())}")

    model = SUPPORTED_MODELS[model_name]

    url = "https://z9dzgw1de2.execute-api.us-east-1.amazonaws.com/prod/invoke"
    headers = {"Authorization": f"Bearer {AWS_API_KEY}", "Content-Type": "application/json"}

    # =====================================================================
    # TEXT MODELS - UPDATED FORMAT
    # =====================================================================
    if model_type == "text":

        # MISTRAL & QWEN → Chat Format (messages array)
        if any(model_name.startswith(prefix) for prefix in ["mistral", "qwen"]):
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": query}]
                    }
                ],
                "inferenceConfig": {
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                    "topP": top_p
                }
            }

        # LLaMA → Text Format (inputText)
        else:
            payload = {
                "model": model,
                "inputText": query,
                "textGenerationConfig": {
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                    "topP": top_p
                }
            }

    # =====================================================================
    # VISION MODELS (LLaMA Vision) - UPDATED FORMAT
    # =====================================================================
    elif model_type == "vision":
        if not image_path:
            raise ValueError("image_path is required for vision models")

        # Only llama-11b supports vision currently
        if model_name != "llama-11b":
            raise ValueError(f"Vision is only supported with llama-11b model, not {model_name}")

        b64, mime = process_image(image_path)

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "image": {
                                "format": mime.split("/")[-1],
                                "source": {"bytes": b64}
                            }
                        },
                        {"text": query}
                    ]
                }
            ],
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
                "topP": top_p
            }
        }

    else:
        raise ValueError("model_type must be 'text' or 'vision'")

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        response_data = r.json()
        
        # Check if the Lambda returned an error
        if "error" in response_data:
            return {"error": response_data["error"]}
            
        return response_data
        
    except requests.exceptions.RequestException as e:
        logger.warning("⚠️ API ERROR: %s", e)
        return {"error": "We are currently experiencing high traffic. Please try again in a few moments."}
    except json.JSONDecodeError as e:
        logger.warning("⚠️ JSON Decode ERROR: %s", e)
        return {"error": "We encountered a temporary issue. Please try again later."}
    except Exception as e:
        logger.error("⚠️ UNEXPECTED ERROR: %s", e)
        return {"error": "An unexpected error occurred. Please try again later."}


def extract_text_from_response(response):
    """Updated extractor for new response formats"""
    if "error" in response:
        return response['error']
    
    # Try different response formats from the updated Lambda
    if "outputText" in response:
        return str(response["outputText"]).strip()
    elif "response" in response:
        return str(response["response"]).strip()
    elif "output" in response and "message" in response["output"]:
        # For converse API format
        try:
            return str(response["output"]["message"]["content"][0]["text"]).strip()
        except (KeyError, IndexError):
            pass
    elif "body" in response:
        # If response is wrapped in API Gateway format
        try:
            body_data = json.loads(response["body"])
            return extract_text_from_response(body_data)
        except (json.JSONDecodeError, KeyError):
            pass
            
    # Fallback: return the whole response for debugging
    return str(response)


# =====================================================================
# UPDATED TESTS
# =====================================================================
if __name__ == "__main__":

    logger.info("=== TEXT MODEL TEST (MISTRAL) ===")
    res = invoke_llama_api(
        query="Write a haiku about stars.",
        model_type="text",
        model_name="mistral-7b",
        temperature=0.85,
        top_p=0.95,
        max_tokens=1024
    )
    logger.info("Response: %s", extract_text_from_response(res))
    logger.info("Full response: %s", json.dumps(res, indent=2))

    logger.info("\n" + "="*50 + "\n")

    logger.info("=== TEXT MODEL TEST (LLAMA-3B) ===")
    res = invoke_llama_api(
        query="Explain quantum computing in simple terms.",
        model_type="text", 
        model_name="llama-3b",
        temperature=0.7,
        max_tokens=512
    )
    logger.info("Response: %s", extract_text_from_response(res))
    logger.info("Full response: %s", json.dumps(res, indent=2))

    logger.info("\n" + "="*50 + "\n")

    logger.info("=== VISION MODEL TEST ===")
    image_path = "/Users/siddharthmishra35/Desktop/mongo-try/image.png"

    if os.path.exists(image_path):
        res2 = invoke_llama_api(
            query="Describe this image in detail.",
            model_type="vision",
            model_name="llama-11b",
            image_path=image_path,
            max_tokens=2048  # Vision responses tend to be longer
        )
        logger.info("Response: %s", extract_text_from_response(res2))
        logger.info("Full response: %s", json.dumps(res2, indent=2))
    else:
        logger.warning("⚠️ Image not found at %s", image_path)
        logger.info("Testing with a text fallback...")
        res2 = invoke_llama_api(
            query="Describe a sunset over mountains.",
            model_type="text",
            model_name="llama-11b"
        )
        logger.info("Response: %s", extract_text_from_response(res2))

    logger.info("\n" + "="*50 + "\n")

    logger.info("=== QWEN MODEL TEST ===")
    res3 = invoke_llama_api(
        query="Write Python code to calculate fibonacci sequence.",
        model_type="text",
        model_name="qwen-32b",
        temperature=0.3,  # Lower temp for code generation
        max_tokens=512
    )
    logger.info("Response: %s", extract_text_from_response(res3))
    logger.info("Full response: %s", json.dumps(res3, indent=2))