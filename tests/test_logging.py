import unittest
import os
import json
import logging
from unittest.mock import patch, MagicMock
from core.logging_config import setup_logging, get_logger, log_execution, CustomJsonFormatter

class TestLogging(unittest.TestCase):

    def setUp(self):
        # Ensure logs directory exists and is empty for clean tests
        self.log_dir = 'logs'
        os.makedirs(self.log_dir, exist_ok=True)
        for f in os.listdir(self.log_dir):
            os.remove(os.path.join(self.log_dir, f))

        # Reset logging handlers to avoid interference between tests
        logging.getLogger().handlers = []
        for name in ['root', 'scraper', 'writer', 'publisher', 'celery']:
            logging.getLogger(name).handlers = []

        # Reload logging configuration for each test
        setup_logging()

    def tearDown(self):
        # Clean up log files after each test
        for f in os.listdir(self.log_dir):
            os.remove(os.path.join(self.log_dir, f))
        os.rmdir(self.log_dir)

    def _read_log_file(self, filename):
        filepath = os.path.join(self.log_dir, filename)
        if not os.path.exists(filepath):
            return []
        with open(filepath, 'r', encoding='utf8') as f:
            return [json.loads(line) for line in f if line.strip()]

    def test_json_formatter_fields(self):
        logger = get_logger('root')
        logger.info("Test message for JSON fields", extra={'trace_id': '123', 'context_data': {'key': 'value'}})
        logs = self._read_log_file('app.log')
        self.assertTrue(logs)
        log_entry = logs[0]
        self.assertIn('timestamp', log_entry)
        self.assertIn('level', log_entry)
        self.assertEqual(log_entry['level'], 'INFO')
        self.assertIn('logger', log_entry)
        self.assertEqual(log_entry['logger'], 'root')
        self.assertIn('function', log_entry)
        self.assertIn('message', log_entry)
        self.assertEqual(log_entry['message'], 'Test message for JSON fields')
        self.assertIn('trace_id', log_entry)
        self.assertEqual(log_entry['trace_id'], '123')
        self.assertIn('context_data', log_entry)
        self.assertEqual(log_entry['context_data'], {'key': 'value'})

    def test_component_specific_logging(self):
        scraper_logger = get_logger('scraper')
        writer_logger = get_logger('writer')

        scraper_logger.info("Scraper specific log")
        writer_logger.error("Writer specific error")

        scraper_logs = self._read_log_file('scraper.log')
        writer_logs = self._read_log_file('writer.log')
        root_logs = self._read_log_file('app.log') # Should not contain component-specific logs due to propagate=False

        self.assertTrue(scraper_logs)
        self.assertEqual(scraper_logs[0]['message'], 'Scraper specific log')
        self.assertEqual(scraper_logs[0]['logger'], 'scraper')

        self.assertTrue(writer_logs)
        self.assertEqual(writer_logs[0]['message'], 'Writer specific error')
        self.assertEqual(writer_logs[0]['logger'], 'writer')

        # Verify root logger does not get propagated logs
        for log in root_logs:
            self.assertNotIn(log['logger'], ['scraper', 'writer'])

    @patch('time.perf_counter', side_effect=[0, 0.1, 0.1, 0.3]) # Mock time for execution time measurement
    def test_log_execution_decorator_success(self, mock_perf_counter):
        @log_execution(logger_name='root')
        def test_func(a, b):
            return a + b

        result = test_func(1, 2)
        self.assertEqual(result, 3)

        logs = self._read_log_file('app.log')
        self.assertEqual(len(logs), 2) # Entry and exit logs

        start_log = logs[0]
        self.assertEqual(start_log['message'], "Executing function 'test_func'")
        self.assertEqual(start_log['context_data']['args'], ['1', '2'])
        self.assertEqual(start_log['context_data']['kwargs'], {})

        end_log = logs[1]
        self.assertEqual(end_log['message'], "Function 'test_func' executed successfully in 0.1000 seconds")
        self.assertEqual(end_log['context_data']['execution_time_seconds'], 0.1)
        self.assertEqual(end_log['context_data']['return_value'], '3')

    @patch('time.perf_counter', side_effect=[0, 0.1, 0.1, 0.3]) # Mock time for execution time measurement
    def test_log_execution_decorator_failure(self, mock_perf_counter):
        @log_execution(logger_name='root')
        def test_func_fail(a, b):
            raise ValueError("Test error")

        with self.assertRaises(ValueError):
            test_func_fail(1, 2)

        logs = self._read_log_file('app.log')
        self.assertEqual(len(logs), 2) # Entry and error logs

        start_log = logs[0]
        self.assertEqual(start_log['message'], "Executing function 'test_func_fail'")

        error_log = logs[1]
        self.assertTrue("Function 'test_func_fail' failed" in error_log['message'])
        self.assertEqual(error_log['level'], 'ERROR')
        self.assertEqual(error_log['context_data']['error_type'], 'ValueError')
        self.assertEqual(error_log['context_data']['error_message'], 'Test error')
        self.assertIn('exc_info', error_log) # Check for exception info

    def test_log_rotation(self):
        # Temporarily override env vars for this test
        os.environ['LOG_ROTATION_SIZE_MB'] = '1' # 1MB
        os.environ['LOG_BACKUP_COUNT'] = '2'
        setup_logging() # Re-setup logging with new env vars

        logger = get_logger('root')
        long_message = "a" * 1000 # 1KB message

        # Write enough logs to trigger rotation (more than 1MB)
        for i in range(1500): # 1500 * 1KB = 1.5MB
            logger.info(f"Log entry {i}: {long_message}")

        log_files = sorted([f for f in os.listdir(self.log_dir) if f.startswith('app.log')])
        # Expect app.log, app.log.1, app.log.2 (up to backup count)
        self.assertGreaterEqual(len(log_files), 3)
        self.assertIn('app.log', log_files)
        self.assertIn('app.log.1', log_files)
        self.assertIn('app.log.2', log_files)

        # Clean up env vars
        del os.environ['LOG_ROTATION_SIZE_MB']
        del os.environ['LOG_BACKUP_COUNT']

if __name__ == '__main__':
    unittest.main()
