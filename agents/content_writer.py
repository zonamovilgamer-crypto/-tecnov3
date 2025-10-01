import random
import re
import time
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime

from services.ai_providers import groq, cohere, huggingface, gemini
from database.database_service import db_service
from core.logging_config import log_execution, get_logger

logger = get_logger('writer')

class HumanizedWriter:
    """
    An agent responsible for generating humanized articles using various AI providers.
    It selects the best AI based on content type and handles article storage.
    """
    def __init__(self):
        self.ai_services: List[Any] = []
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
        logger.info("HumanizedWriter initialized.")

    @log_execution(logger_name='writer')
    def _initialize_ai_services(self) -> None:
        """Initializes and shuffles available AI services."""
        services = [groq, cohere, huggingface, gemini]
        self.ai_services = services  # Assume all available as pre-initialized
        if not self.ai_services:
            logger.error("No AI services are available. Please check your API keys and installations.")
            raise Exception("No AI services are available. Please check your API keys and installations.")
        random.shuffle(self.ai_services)
        logger.info(f"Initialized AI services: {len(self.ai_services)}")

    @log_execution(logger_name='writer')
    def _get_next_ai_service(self) -> Optional[Any]:
        """Rotates through available AI services."""
        if not self.ai_services:
            logger.warning("No AI services available for rotation.")
            return None
        service = self.ai_services[0]
        self.ai_services.append(self.ai_services.pop(0)) # Rotate for next call
        logger.debug(f"Rotated AI service. Next up: {service.service_name if service else 'None'}")
        return service

    @log_execution(logger_name='writer')
    def _get_alternative_prompt(self, original_prompt: str, attempt: int) -> str:
        """Generates an alternative prompt for regeneration attempts."""
        if attempt == 1:
            alt_prompt = f"Reescribe el siguiente contenido con un estilo más conversacional y humano, evitando frases robóticas: {original_prompt}"
        elif attempt == 2:
            alt_prompt = f"Genera un bloque de contenido muy creativo y original sobre el tema, con un enfoque fresco y personal: {original_prompt}"
        else:
            alt_prompt = f"Intenta generar el contenido de nuevo, enfocándote en la fluidez y naturalidad del lenguaje: {original_prompt}"
        logger.debug(f"Generated alternative prompt for attempt {attempt + 1}.")
        return alt_prompt

    @log_execution(logger_name='writer')
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
                logger.info(f"🔄 ContentWriter: Usando prompt alternativo para el bloque '{block_type}', intento {attempt + 1}.")

            service = self._get_next_ai_service()
            if not service:
                logger.error(f"❌ ContentWriter: No hay servicio de IA disponible para generar el bloque: '{block_type}'.")
                continue

            logger.info(f"✍️ ContentWriter: Intentando generar bloque '{block_type}' con el servicio '{service.service_name}', intento {attempt + 1}.")

            generated_text = service.generate_text(
                prompt=current_prompt,
                max_tokens=int(self.block_word_count * 1.5),
                temperature=0.7 + (attempt * 0.1)
            )

            # Si es una lista, convertir a string
            if isinstance(generated_text, list):
                generated_text = " ".join(generated_text)

            # Si no es string o está vacío, continuar al siguiente intento
            if not generated_text or not isinstance(generated_text, str):
                logger.warning(f"⚠️ ContentWriter: El servicio retornó un tipo inválido o contenido vacío para el bloque '{block_type}'. Reintentando...")
                continue

            if self._is_robotic(generated_text):
                logger.warning(f"🤖 ContentWriter: El contenido generado para el bloque '{block_type}' parece robótico. Regenerando con nuevo prompt/servicio...")
                continue
            logger.info(f"✅ ContentWriter: Bloque '{block_type}' generado exitosamente.")
            return generated_text

        logger.error(f"❌ ContentWriter: Falló la generación del bloque '{block_type}' después de {self.max_block_retries} intentos.")

        # Salvamento system: if all attempts fail, generate a generic block
        logger.warning(f"🚨 ContentWriter: Activando sistema de salvamento para el bloque '{block_type}'. Generando contenido genérico.")
        salvamento_prompt = f"Genera un bloque de contenido genérico sobre '{topic}' para la sección de {block_type}. Asegúrate de que tenga al menos {self.block_word_count} palabras."
        for service in self.ai_services:
            generic_content = service.generate_text(prompt=salvamento_prompt, max_tokens=int(self.block_word_count * 1.5))
            if generic_content:
                logger.info(f"✅ ContentWriter: Salvamento exitoso para el bloque '{block_type}' con el servicio '{service.service_name}'.")
                return generic_content

        logger.error(f"❌ ContentWriter: El sistema de salvamento falló para el bloque '{block_type}'. No se pudo generar contenido.")
        return None

    @log_execution(logger_name='writer')
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

    @log_execution(logger_name='writer')
    def _validate_article(self, article: str) -> Tuple[bool, str]:
        """
        Validates the article for length and quality (basic robotic detection).
        Returns (is_valid, message).
        """
        word_count = len(article.split())
        if word_count < self.min_article_length:
            return False, f"Article is too short: {word_count} words, expected {self.min_article_length}+."

        if self._is_robotic(article):
            logger.warning("🤖 ContentWriter: Artículo detectado como robótico durante la validación.")
            return False, "Article content seems robotic."

        logger.info("✅ ContentWriter: Artículo validado exitosamente.")
        return True, "Article validated successfully."

    @log_execution(logger_name='writer')
    def _assemble_article(self, blocks: List[str]) -> str:
        """
        Assembles blocks into a cohesive article with natural transitions.
        """
        logger.info("ContentWriter: Ensamblando bloques en un artículo.")
        return "\n\n".join(blocks)

    @log_execution(logger_name='writer')
    def _generate_slug(self, title: str) -> str:
        """
        Generates a URL-friendly slug from a title.
        """
        slug = title.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        logger.debug(f"ContentWriter: Slug generado para '{title}': '{slug}'.")
        return slug

    @log_execution(logger_name='writer')
    async def generate_humanized_article(self, topic: str, source_url: Optional[str] = None, source_type: str = "unknown") -> Optional[str]:
        """
        Generates a humanized article of 800+ words using a block-based approach.
        Returns the article content as a string.
        """
        logger.info(f"✍️ ContentWriter: Iniciando generación de artículo humanizado para el tema: '{topic}'.")
        generated_blocks = []
        block_types = ["introduccion", "explicacion", "analisis", "conclusion"]

        for block_type in block_types:
            block_content = self._generate_block(self.prompts[block_type], topic, block_type)
            if block_content:
                generated_blocks.append(block_content)
            else:
                logger.error(f"❌ ContentWriter: Falló la generación de contenido para el tipo de bloque '{block_type}'. Abortando generación de artículo.")
                return None

        assembled_article = self._assemble_article(generated_blocks)
        is_valid, message = self._validate_article(assembled_article)

        if not is_valid:
            logger.warning(f"⚠️ ContentWriter: El artículo ensamblado falló la validación: {message}. Intentando regeneración completa.")
            return await self.generate_humanized_article(topic, source_url, source_type)

        logger.info("✅ ContentWriter: Artículo humanizado generado y validado exitosamente.")

        # Prepare article data to be returned to the orchestrator for saving
        article_data = {
            "title": topic,
            "content": assembled_article,
            "excerpt": assembled_article[:150] + "...",
            "slug": self._generate_slug(topic),
            "status": "generated", # Status is 'generated' here, orchestrator will save and update
            "source_type": source_type,
            "source_url": source_url,
            "author": "Sistema Automatizado Tech",
            "word_count": len(assembled_article.split()),
            "reading_time": max(1, len(assembled_article.split()) // 200)
        }
        logger.info(f"ContentWriter: Retornando datos del artículo generado para el orquestador.")
        return article_data

# Removed example usage and venv check as orchestration will handle execution
