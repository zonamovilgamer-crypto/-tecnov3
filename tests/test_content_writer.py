import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.content_writer import HumanizedWriter
from services.ai_providers import AIService

class TestHumanizedWriter(unittest.TestCase):

    @patch('services.ai_providers.GroqService')
    @patch('services.ai_providers.CohereService')
    @patch('services.ai_providers.HuggingFaceService')
    @patch('services.ai_providers.GeminiService')
    def setUp(self, MockGeminiService, MockHuggingFaceService, MockCohereService, MockGroqService):
        # Mock AI services to be available and return predictable content
        self.mock_services = []

        mock_groq = MockGroqService.return_value
        mock_groq.is_available = True
        mock_groq.service_name = "MockGroq"
        mock_groq.generate_text.return_value = "This is an engaging introduction from Groq, full of interesting facts and a personal touch. It aims to captivate the reader from the very first sentence, drawing them into the narrative with a compelling hook. The language is fluid and natural, avoiding any robotic patterns. " * 10 # ~200 words
        self.mock_services.append(mock_groq)

        mock_cohere = MockCohereService.return_value
        mock_cohere.is_available = True
        mock_cohere.service_name = "MockCohere"
        mock_cohere.generate_text.return_value = "Here's a clear and conversational explanation from Cohere, breaking down complex ideas into digestible parts. It uses analogies and simple terms to ensure broad understanding, making technical topics accessible to everyone. The flow is smooth and human-like. " * 10 # ~200 words
        self.mock_services.append(mock_cohere)

        mock_huggingface = MockHuggingFaceService.return_value
        mock_huggingface.is_available = True
        mock_huggingface.service_name = "MockHuggingFace"
        mock_huggingface.generate_text.return_value = "This block offers a thoughtful analysis from HuggingFace, presenting a unique perspective backed by solid examples. It encourages critical thinking and provides fresh insights, making the content both informative and engaging. The tone is authoritative yet approachable. " * 10 # ~200 words
        self.mock_services.append(mock_huggingface)

        mock_gemini = MockGeminiService.return_value
        mock_gemini.is_available = True
        mock_gemini.service_name = "MockGemini"
        mock_gemini.generate_text.return_value = "Finally, a practical and reflective conclusion from Gemini, summarizing key takeaways and inspiring further thought. It leaves the reader with a lasting impression and a clear call to action or deeper consideration of the topic. The ending feels natural and complete. " * 10 # ~200 words
        self.mock_services.append(mock_gemini)

        # Patch the _initialize_ai_services to use our mocks
        with patch.object(HumanizedWriter, '_initialize_ai_services', return_value=None):
            self.writer = HumanizedWriter()
            self.writer.ai_services = self.mock_services # Manually set the mocked services
            self.writer.min_article_length = 800 # Ensure validation passes for 4 blocks * 200 words

    def test_generate_humanized_article_success(self):
        topic = "The Future of AI in Education"
        article_content = self.writer.generate_humanized_article(topic) # Expect string

        self.assertIsNotNone(article_content)
        self.assertTrue(len(article_content.split()) >= self.writer.min_article_length)

        # Verify each service was called at least once (due to rotation)
        for mock_service in self.mock_services:
            self.assertTrue(mock_service.generate_text.called)
            mock_service.generate_text.reset_mock() # Reset for potential future tests

    def test_generate_humanized_article_service_failure_and_fallback(self):
        topic = "Quantum Computing Breakthroughs"

        # Test block resilience: first service fails, then another service succeeds after a retry
        # We need to mock side_effect for all services to simulate rotation and prompt changes
        # For simplicity, let's make the first few attempts fail or be robotic, then succeed.

        # Mock Groq to fail initially, then succeed on retry
        def mock_groq_generate(*args, **kwargs):
            mock_groq_generate.call_count = getattr(mock_groq_generate, 'call_count', 0) + 1
            if mock_groq_generate.call_count == 1:
                return None # First attempt with Groq fails
            return "This is a regenerated block from MockGroq, with a different prompt. " * 40 # Subsequent attempts succeed
        self.mock_services[0].generate_text.side_effect = mock_groq_generate

        # Mock Cohere to return robotic content initially, then succeed
        def mock_cohere_generate(*args, **kwargs):
            mock_cohere_generate.call_count = getattr(mock_cohere_generate, 'call_count', 0) + 1
            if mock_cohere_generate.call_count == 1:
                return "En conclusión, este contenido es robótico. " * 40 # Robotic content
            return "This is a humanized block from MockCohere after regeneration. " * 40 # Humanized content
        self.mock_services[1].generate_text.side_effect = mock_cohere_generate

        # Mock HuggingFace and Gemini to always succeed with humanized content
        self.mock_services[2].generate_text.return_value = "This is a humanized block from MockHuggingFace. " * 40
        self.mock_services[3].generate_text.return_value = "This is a humanized block from MockGemini. " * 40

        article_content = self.writer.generate_humanized_article(topic) # Expect string
        self.assertIsNotNone(article_content)
        self.assertTrue(len(article_content.split()) >= self.writer.min_article_length)

        # Verify that multiple services were called and retries happened
        # The exact call count can be complex due to rotation and robotic detection,
        # so we check for overall success and that at least some retries occurred.
        self.assertTrue(self.mock_services[0].generate_text.call_count >= 1)
        self.assertTrue(self.mock_services[1].generate_text.call_count >= 1)

        # Test salvamento system
    def test_generate_humanized_article_salvamento_fallback(self):
        topic = "The Limits of AI"
        # Make all services fail for the main generation loop (all retries return None)
        for service in self.mock_services:
            service.generate_text.side_effect = [None] * self.writer.max_block_retries

        # After the main loop fails, the salvamento system will iterate through services.
        # We need to ensure at least one service provides content during this salvamento iteration.
        # We'll make the first service succeed on its *first* call during the salvamento loop.
        # To do this, we'll temporarily override its generate_text method for the salvamento phase.

        # Make all services fail for the main generation loop (all retries return None)
        for service in self.mock_services:
            def failing_generate(*args, **kwargs):
                failing_generate.call_count = getattr(failing_generate, 'call_count', 0) + 1
                if failing_generate.call_count <= self.writer.max_block_retries:
                    return None
                return "This is generic salvamento content from MockService. " * 40 # For salvamento phase
            service.generate_text.side_effect = failing_generate

        # Ensure at least one service provides content during the salvamento iteration
        # We'll make the first service succeed on its *first* call during the salvamento loop.
        # The `failing_generate` function above handles this by returning content after `max_block_retries` Nones.

        article_content = self.writer.generate_humanized_article(topic) # Expect string
        self.assertIsNotNone(article_content) # Should return content from salvamento
        self.assertIn("generic salvamento content", article_content.lower()) # Check for generic content from salvamento
        self.assertTrue(len(article_content.split()) >= self.writer.min_article_length)

    def test_generate_humanized_article_all_services_and_salvamento_fail(self):
        topic = "Deep Sea Exploration"
        # Make all services fail for both main generation and salvamento
        for service in self.mock_services:
            def always_fail_generate(*args, **kwargs):
                return None
            service.generate_text.side_effect = always_fail_generate

        article_content = self.writer.generate_humanized_article(topic) # Expect string
        self.assertIsNone(article_content)

    def test_validate_article_length_failure(self):
        short_article = "This is a very short article."
        is_valid, message = self.writer._validate_article(short_article)
        self.assertFalse(is_valid)
        self.assertIn("too short", message)

    def test_is_robotic_detection(self):
        # This text should now be detected as robotic due to the patterns
        robotic_text = "En conclusión, es importante destacar que la finalidad de este documento es analizar los datos. Asimismo, se ha demostrado que la información es relevante."
        self.assertTrue(self.writer._is_robotic(robotic_text), f"Expected robotic text to be detected, but it wasn't. Text: {robotic_text}")

        human_text = "Wow, what an incredible journey! I truly believe this will change everything. Let's dive in. This article is truly amazing and I'm sure you'll love it."
        self.assertFalse(self.writer._is_robotic(human_text), f"Expected human text not to be detected as robotic, but it was. Text: {human_text}")

if __name__ == '__main__':
    unittest.main()
