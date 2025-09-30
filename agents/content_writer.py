import random
import re
import time
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

from services.ai_providers import GroqService, CohereService, HuggingFaceService, GeminiService, AIService
from database.database_service import db_service
from core.context_logger import ContextLogger

writer_context_logger = ContextLogger("writer")

class HumanizedWriter:
    def __init__(self):
        self.ai_services: List[AIService] = []
        self.context_logger = writer_context_logger
        self._initialize_ai_services()
        self.block_styles = {
            "introduccion": "periodístico y enganchador con una anécdota personal",
            "explicacion": "técnico pero conversacional y fácil de entender",
            "analisis": "opinativo y analítico con ejemplos concretos",
            "conclusion": "práctico y reflexivo con una llamada a la acción o pensamiento final"
        }
        self.prompts = {
            "introduccion": "Genera una introducción de aproximadamente 200 palabras. Comienza con una anécdota personal o una pregunta intrigante para captar la atención del lector. El tono debe ser {style}. El tema es: {topic}",
            "explicacion": "Desarrolla una explicación técnica del tema de aproximadamente 200 palabras, utilizando un lenguaje {style}. Asegúrate de que sea accesible para un público general. El tema es: {topic}",
            "analisis": "Proporciona una opinión y análisis del tema de aproximadamente 200 palabras, respaldado con ejemplos concretos. El tono debe ser {style}. El tema es: {topic}",
            "conclusion": "Escribe una conclusión de aproximadamente 200 palabras que resuma los puntos clave y ofrezca una perspectiva práctica o una llamada a la reflexión. El tono debe ser {style}. El tema es: {topic}"
        }
        self.min_article_length = 800
        self.block_word_count = 200
        self.max_regeneration_attempts = 3
        self.max_block_retries = 5 # Max retries for a single block, including prompt variations
        self.context_logger.logger.info("HumanizedWriter initialized.")

    @writer_context_logger.log_execution
    def _initialize_ai_services(self) -> None:
        """Initializes and shuffles available AI services."""
        services = [
            GroqService(),
            CohereService(),
            HuggingFaceService(),
            GeminiService()
        ]
        self.ai_services = [s for s in services if s.is_available]
        if not self.ai_services:
            self.context_logger.logger.error("No AI services are available. Please check your API keys and installations.")
            raise Exception("No AI services are available. Please check your API keys and installations.")
        random.shuffle(self.ai_services)
        self.context_logger.logger.info("Initialized AI services", count=len(self.ai_services))

    @writer_context_logger.log_execution
    def _get_next_ai_service(self) -> Optional[AIService]:
        """Rotates through available AI services."""
        if not self.ai_services:
            self.context_logger.logger.warning("No AI services available for rotation.")
            return None
        service = self.ai_services[0]
        self.ai_services.append(self.ai_services.pop(0)) # Rotate for next call
        return service

    @writer_context_logger.log_execution
    def _get_alternative_prompt(self, original_prompt: str, attempt: int) -> str:
        """Generates an alternative prompt for regeneration attempts."""
        if attempt == 1:
            return f"Reescribe el siguiente contenido con un estilo más conversacional y humano, evitando frases robóticas: {original_prompt}"
        elif attempt == 2:
            return f"Genera un bloque de contenido muy creativo y original sobre el tema, con un enfoque fresco y personal: {original_prompt}"
        else:
            return f"Intenta generar el contenido de nuevo, enfocándote en la fluidez y naturalidad del lenguaje: {original_prompt}"

    @writer_context_logger.log_execution
    def _generate_block(self, prompt_template: str, topic: str, block_type: str) -> Optional[str]:
        """
        Generates a content block using an AI service, with fallback, style rotation,
        and prompt variation for resilience.
        """
        style = self.block_styles.get(block_type, "conversacional")
        original_formatted_prompt = prompt_template.format(style=style, topic=topic)

        for attempt in range(self.max_block_retries):
            current_prompt = original_formatted_prompt
            if attempt > 0:
                current_prompt = self._get_alternative_prompt(original_formatted_prompt, attempt)
                self.context_logger.logger.info("Using alternative prompt for block", block_type=block_type, attempt=attempt + 1)

            service = self._get_next_ai_service()
            if not service:
                self.context_logger.logger.error("No AI service available to generate block.", block_type=block_type)
                continue

            self.context_logger.logger.info("Attempting to generate block", block_type=block_type, service=service.service_name, attempt=attempt + 1)

            generated_text = service.generate_text(
                prompt=current_prompt,
                max_tokens=int(self.block_word_count * 1.5), # Allow some buffer for token count
                temperature=0.7 + (attempt * 0.1) # Increase temperature for variety on retries
            )

            # Si es una lista, convertir a string
            if isinstance(generated_text, list):
                generated_text = " ".join(generated_text)

            # Si no es string o está vacío, continuar al siguiente intento
            if not generated_text or not isinstance(generated_text, str):
                self.context_logger.logger.warning("Service returned invalid type for block. Retrying...", block_type=block_type)
                continue

            if self._is_robotic(generated_text):
                self.context_logger.logger.warning("Generated content for block seems robotic. Regenerating with new prompt/service...", block_type=block_type)
                continue
            return generated_text

        self.context_logger.logger.error("Failed to generate block after multiple attempts", block_type=block_type, attempts=self.max_block_retries)

        # Salvamento system: if all attempts fail, generate a generic block
        self.context_logger.logger.warning("Activating salvamento system for block. Generating generic content.", block_type=block_type)
        salvamento_prompt = f"Genera un bloque de contenido genérico sobre '{topic}' para la sección de {block_type}. Asegúrate de que tenga al menos {self.block_word_count} palabras."
        for service in self.ai_services: # Try all services for salvamento
            generic_content = service.generate_text(prompt=salvamento_prompt, max_tokens=int(self.block_word_count * 1.5))
            if generic_content:
                self.context_logger.logger.info("Salvamento successful for block", block_type=block_type, service=service.service_name)
                return generic_content

        self.context_logger.logger.error("Salvamento system failed for block. No content could be generated.", block_type=block_type)
        return None

    @writer_context_logger.log_execution
    def _is_robotic(self, text: str) -> bool:
        """
        Simple heuristic to detect robotic-sounding content.
        This can be greatly improved with more advanced NLP techniques.
        """
        # Look for repetitive phrases, lack of contractions, overly formal language
        # Heuristics to detect robotic-sounding content.
        # This version is less sensitive and focuses on clearly robotic patterns.

        # 1. Look for clearly robotic phrases
        robotic_patterns = [
            r"En el ámbito de", r"Es importante destacar que", r"En la actualidad,",
            r"Cabe señalar que", r"La finalidad de este documento", r"Se ha demostrado que",
            r"Por consiguiente,", r"En resumen,", r"En conclusión,"
        ]
        for pattern in robotic_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        # 2. Exclude enthusiastic/conversational language from being flagged as robotic
        conversational_keywords = [
            r"Wow", r"increíble", r"fantástico", r"sorprendente", r"genial",
            r"imagina esto", r"piensa en", r"te encantará", r"descubre cómo"
        ]
        for keyword in conversational_keywords:
            if re.search(keyword, text, re.IGNORECASE):
                return False # If conversational language is present, it's likely not robotic

        # 3. Check for very short sentences or lack of sentence variety (more lenient heuristic)
        sentences = re.split(r'[.!?]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        sentences = [s for s in sentences if len(s.split()) > 3] # Filter out very short fragments

        if not sentences:
            return True # Consider empty or fragmented text robotic

        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
        # Flag if it's excessively short (e.g., < 5) or excessively long (e.g., > 40)
        if avg_sentence_length < 5 or avg_sentence_length > 40:
            return True

        return False

    @writer_context_logger.log_execution
    def _validate_article(self, article: str) -> Tuple[bool, str]:
        """
        Validates the article for length and quality (basic robotic detection).
        Returns (is_valid, message).
        """
        word_count = len(article.split())
        if word_count < self.min_article_length:
            return False, f"Article is too short: {word_count} words, expected {self.min_article_length}+."

        if self._is_robotic(article):
            return False, "Article content seems robotic."

        return True, "Article validated successfully."

    @writer_context_logger.log_execution
    def _assemble_article(self, blocks: List[str]) -> str:
        """
        Assembles blocks into a cohesive article with natural transitions.
        """
        # Simple assembly for now, can be enhanced with AI-driven transitions
        return "\n\n".join(blocks)

    @writer_context_logger.log_execution
    def _generate_slug(self, title: str) -> str:
        """
        Generates a URL-friendly slug from a title.
        """
        # Convert to lowercase and replace spaces with hyphens
        slug = title.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)  # Remove special characters
        slug = re.sub(r'[-\s]+', '-', slug)    # Replace spaces and multiple hyphens with single hyphen
        return slug

    @writer_context_logger.log_execution
    async def generate_humanized_article(self, topic: str, source_url: Optional[str] = None, source_type: str = "unknown") -> Optional[str]:
        """
        Generates a humanized article of 800+ words using a block-based approach.
        Returns the article content as a string.
        """
        self.context_logger.logger.info("Starting humanized article generation", topic=topic)
        generated_blocks = []
        block_types = ["introduccion", "explicacion", "analisis", "conclusion"]

        for block_type in block_types:
            block_content = self._generate_block(self.prompts[block_type], topic, block_type)
            if block_content:
                generated_blocks.append(block_content)
            else:
                self.context_logger.logger.error("Failed to generate content for block type. Aborting article generation.", block_type=block_type)
                return None

        assembled_article = self._assemble_article(generated_blocks)
        is_valid, message = self._validate_article(assembled_article)

        if not is_valid:
            self.context_logger.logger.warning("Assembled article failed validation. Attempting full regeneration.", message=message)
            # For simplicity, a full regeneration is attempted. More advanced would be to regenerate specific blocks.
            return await self.generate_humanized_article(topic, source_url, source_type) # Recursive call for full regeneration

        self.context_logger.logger.info("Humanized article generated and validated successfully.")

        # Guardar artículo en Supabase
        article_data = {
            "title": topic,
            "content": assembled_article,
            "excerpt": assembled_article[:150] + "...",
            "slug": self._generate_slug(topic),
            "status": "draft",
            "source_type": source_type,
            "source_url": source_url,
            "author": "Sistema Automatizado Tech",
            "word_count": len(assembled_article.split()),
            "reading_time": max(1, len(assembled_article.split()) // 200)
        }
        saved_article = await db_service.save_article(article_data)

        if saved_article:
            self.context_logger.logger.info("Article saved to Supabase", article_id=saved_article['id'])
        else:
            self.context_logger.logger.error("Failed to save article to Supabase")

        # Note: Metadata (title, author, etc.) is no longer returned directly by this method
        # as per user's request to make it return a string for testing purposes.
        # If metadata is needed by the orchestrator, it should be generated/handled separately
        # or this method's return type would need to be a dict again.
        return saved_article # Return the saved article object with its ID

# Removed example usage and venv check as orchestration will handle execution
