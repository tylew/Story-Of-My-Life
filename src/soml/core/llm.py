"""
LLM Integration - OpenAI and Anthropic API calls.

Provides a unified interface for calling LLMs with:
- Configurable provider (OpenAI or Anthropic)
- Structured output (JSON mode)
- Error handling and retries
- Embedding generation
"""

import json
from typing import Any, Literal

from soml.core.config import settings, get_logger

logger = get_logger("core.llm")


async def call_llm(
    prompt: str,
    system_prompt: str | None = None,
    response_format: Literal["text", "json"] = "text",
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str | dict:
    """
    Call the LLM with the given prompt.
    
    Args:
        prompt: The user prompt
        system_prompt: Optional system prompt (instructions)
        response_format: 'text' or 'json'
        provider: 'openai' or 'anthropic' (defaults to settings)
        model: Model name (defaults to settings)
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response
        
    Returns:
        Response text or parsed JSON dict
    """
    provider = provider or settings.default_llm
    
    if provider == "openai":
        return await _call_openai(
            prompt=prompt,
            system_prompt=system_prompt,
            response_format=response_format,
            model=model or settings.openai_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif provider == "anthropic":
        return await _call_anthropic(
            prompt=prompt,
            system_prompt=system_prompt,
            response_format=response_format,
            model=model or settings.anthropic_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


async def _call_openai(
    prompt: str,
    system_prompt: str | None,
    response_format: Literal["text", "json"],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str | dict:
    """Call OpenAI API."""
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    
    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}
    
    response = await client.chat.completions.create(**kwargs)
    
    content = response.choices[0].message.content or ""
    
    if response_format == "json":
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON response: {content[:100]}...")
            return {"raw": content}
    
    return content


async def _call_anthropic(
    prompt: str,
    system_prompt: str | None,
    response_format: Literal["text", "json"],
    model: str,
    temperature: float,
    max_tokens: int,
) -> str | dict:
    """Call Anthropic API."""
    from anthropic import AsyncAnthropic
    
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    
    # Anthropic uses system as a separate parameter
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    
    if system_prompt:
        if response_format == "json":
            kwargs["system"] = system_prompt + "\n\nRespond with valid JSON only."
        else:
            kwargs["system"] = system_prompt
    
    response = await client.messages.create(**kwargs)
    
    content = response.content[0].text if response.content else ""
    
    if response_format == "json":
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON response: {content[:100]}...")
            return {"raw": content}
    
    return content


async def generate_embedding(
    text: str,
    model: str | None = None,
) -> list[float]:
    """
    Generate an embedding vector for the given text.
    
    Uses OpenAI's embedding API.
    """
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    model = model or settings.openai_embedding_model
    
    response = await client.embeddings.create(
        model=model,
        input=text,
    )
    
    return response.data[0].embedding


async def generate_embeddings_batch(
    texts: list[str],
    model: str | None = None,
) -> list[list[float]]:
    """
    Generate embeddings for multiple texts in batch.
    
    More efficient than calling generate_embedding multiple times.
    """
    from openai import AsyncOpenAI
    
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    model = model or settings.openai_embedding_model
    
    # Process in batches
    batch_size = settings.embedding_batch_size
    all_embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = await client.embeddings.create(
            model=model,
            input=batch,
        )
        all_embeddings.extend([d.embedding for d in response.data])
    
    return all_embeddings


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Estimate token count for text.
    
    Simple approximation: ~4 characters per token for English.
    For precise counting, use tiktoken.
    """
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except ImportError:
        # Fallback approximation
        return len(text) // 4

