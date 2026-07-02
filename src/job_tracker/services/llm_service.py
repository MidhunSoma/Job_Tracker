import json
from typing import Any, Dict, Optional, Tuple
from langchain_core.language_models import BaseChatModel
from ..config.settings import settings
from ..schemas.extraction import AIJobEmailExtraction
from ..prompts.extract_prompt import extract_prompt_v1
from ..prompts.status_prompt import status_prompt_v1
from ..utils.logging import logger


class LLMService:
    """Service wrapping LangChain LLM endpoints for structured extraction and normalization."""

    def __init__(self) -> None:
        self.provider = settings.llm.provider.lower().strip(" =")
        self.model_name = settings.llm.model
        self.temperature = 0.0  # Set temperature to 0 for highly consistent parsing

    def _get_llm(self) -> BaseChatModel:
        """Initializes and returns the configured LangChain chat model dynamically.

        Supports OpenAI, Gemini, and Anthropic.
        """
        api_key_map = {
            "openai": settings.llm.openai_api_key,
            "gemini": settings.llm.gemini_api_key,
            "anthropic": settings.llm.anthropic_api_key,
        }
        
        api_key = api_key_map.get(self.provider)

        if self.provider == "openai":
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=self.model_name,
                api_key=api_key,
                temperature=self.temperature
            )
        elif self.provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                model=self.model_name,
                google_api_key=api_key,
                temperature=self.temperature
            )
        elif self.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=self.model_name,
                api_key=api_key,
                temperature=self.temperature
            )
        else:
            raise ValueError(
                f"Unsupported LLM provider '{self.provider}'. "
                f"Please choose from: openai, gemini, anthropic."
            )

    def extract_job_details(
        self,
        subject: str,
        sender: str,
        date_str: str,
        body: str
    ) -> Tuple[Optional[AIJobEmailExtraction], Dict[str, Any]]:
        """Invokes the LLM to classify and extract job application details.

        Returns:
            A tuple of (parsed Pydantic extraction model, telemetry metadata dict).
        """
        logger.info(
            f"Invoking LLM ({self.provider}/{self.model_name}) to extract job details.",
            extra={"action": "LLM_EXTRACT", "subject": subject, "sender": sender}
        )
        
        try:
            # 1. Print structured output schema
            schema_json = json.dumps(AIJobEmailExtraction.model_json_schema(), indent=2)
            logger.info(f"--- STRUCTURED OUTPUT SCHEMA ---\n{schema_json}\n--------------------------------")

            # 2. Print exact prompt sent to Gemini
            formatted_prompt = extract_prompt_v1.format(
                subject=subject,
                sender=sender,
                date=date_str,
                body=body[:8000]
            )
            logger.info(f"--- PROMPT SENT TO LLM ---\n{formatted_prompt}\n--------------------------")

            # 3. Validate Gemini model name if provider is gemini
            if self.provider == "gemini":
                valid_gemini_models = [
                    "gemini-1.5-flash", "gemini-1.5-pro", 
                    "gemini-2.0-flash-exp", "gemini-2.0-flash", "gemini-2.0-pro-exp",
                    "gemini-1.0-pro"
                ]
                if self.model_name not in valid_gemini_models:
                    logger.warning(
                        f"LLM__MODEL '{self.model_name}' is not in the list of standard Gemini models "
                        f"({valid_gemini_models}). This might cause API errors or lack of structured output support."
                    )

            llm = self._get_llm()
            
            parsed = None
            raw_message = None
            
            # Try structured output using standard method
            try:
                logger.info("Attempting extraction using with_structured_output()...")
                structured_llm = llm.with_structured_output(AIJobEmailExtraction, include_raw=True)
                chain = extract_prompt_v1 | structured_llm
                
                response = chain.invoke({
                    "subject": subject,
                    "sender": sender,
                    "date": date_str,
                    "body": body[:8000]
                })
                parsed = response.get("parsed")
                raw_message = response.get("raw")
                
                if raw_message:
                    raw_content = getattr(raw_message, "content", "")
                    tool_calls = raw_message.additional_kwargs.get("tool_calls", [])
                    logger.info(
                        f"--- RAW LLM RESPONSE (with_structured_output) ---\n"
                        f"Content: {raw_content}\n"
                        f"Tool Calls: {tool_calls}\n"
                        f"-------------------------------------------------"
                    )
            except Exception as structured_err:
                logger.error(
                    f"with_structured_output() failed or is incompatible with {self.model_name}: {str(structured_err)}", 
                    exc_info=True
                )
                logger.info("Switching to manual JSON generation and parsing fallback...")
                
                # Switch to raw model invocation and manual parsing
                raw_chain = extract_prompt_v1 | llm
                raw_message = raw_chain.invoke({
                    "subject": subject,
                    "sender": sender,
                    "date": date_str,
                    "body": body[:8000]
                })
                
                raw_content = getattr(raw_message, "content", "")
                logger.info(f"--- RAW LLM RESPONSE (fallback) ---\n{raw_content}\n----------------------------------")
                
                import re
                content_clean = raw_content.strip()
                if content_clean.startswith("```"):
                    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content_clean)
                    if match:
                        content_clean = match.group(1)
                
                try:
                    parsed_dict = json.loads(content_clean)
                    parsed = AIJobEmailExtraction(**parsed_dict)
                    logger.info("Successfully parsed raw response manually into AIJobEmailExtraction.")
                except Exception as parse_err:
                    logger.error(f"Manual JSON parsing failed: {parse_err}", exc_info=True)
                    raise parse_err

            # Telemetry metadata
            token_usage = {}
            raw_json = "{}"
            
            if raw_message:
                token_usage = raw_message.response_metadata.get("token_usage", {})
                if hasattr(raw_message, "content") and raw_message.content:
                    raw_json = raw_message.content
                elif "tool_calls" in raw_message.additional_kwargs:
                    tool_calls = raw_message.additional_kwargs["tool_calls"]
                    if tool_calls and len(tool_calls) > 0:
                        raw_json = json.dumps(tool_calls[0].get("function", {}).get("arguments", "{}"))
                else:
                    raw_json = json.dumps(raw_message.additional_kwargs)
            
            telemetry = {
                "raw_llm_json": raw_json,
                "prompt_version": "extract_prompt_v1",
                "model": self.model_name,
                "temperature": self.temperature,
                "token_usage": json.dumps(token_usage),
            }
            
            return parsed, telemetry
            
        except Exception as e:
            logger.exception("LLM extraction call failed.", extra={"action": "LLM_EXTRACT_FAILURE"})
            return None, {
                "raw_llm_json": "{}",
                "prompt_version": "extract_prompt_v1",
                "model": self.model_name,
                "temperature": self.temperature,
                "token_usage": "{}",
                "error": str(e)
            }

    def normalize_status(self, raw_status: str) -> Tuple[str, float]:
        """Maps an arbitrary email stage description to our precise set of 20 normalized statuses

        using a structured LLM call.

        Returns:
            A tuple of (normalized status string, status mapping confidence).
        """
        logger.info(f"Normalizing status: '{raw_status}'", extra={"action": "LLM_NORMALIZE_STATUS"})
        
        # Pydantic schema for status normalization
        from pydantic import BaseModel, Field
        class StatusMapping(BaseModel):
            normalized_status: str = Field(..., description="The exact allowed status mapped")
            confidence: float = Field(..., description="Mapping confidence score from 0.0 to 1.0")
            reason: str = Field(..., description="Reasoning statement")

        try:
            llm = self._get_llm()
            structured_llm = llm.with_structured_output(StatusMapping)
            chain = status_prompt_v1 | structured_llm
            
            mapping = chain.invoke({"raw_status": raw_status})
            
            if mapping:
                logger.info(
                    f"Normalized status mapped: '{raw_status}' -> '{mapping.normalized_status}' (conf={mapping.confidence})",
                    extra={
                        "action": "STATUS_NORMALIZE_SUCCESS",
                        "raw": raw_status,
                        "normalized": mapping.normalized_status,
                        "confidence": mapping.confidence
                    }
                )
                return mapping.normalized_status, mapping.confidence
            
        except Exception:
            logger.exception("Status mapping LLM call failed. Defaulting to 'Applied'.")
            
        return "Applied", 0.5
