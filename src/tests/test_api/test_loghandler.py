import logging
from unittest.mock import ANY, patch

import pytest
from azure.core.exceptions import HttpResponseError

from brp_kennisgevingen.kennisgevingen.loghandler import AuditLogResponseError, BRPAuditLogHandler
from brp_kennisgevingen.kennisgevingen.views import audit_log
from brp_kennisgevingen.settings import CustomJsonFormatter


class TestAuditLogHandler:

    @pytest.fixture
    def audit_log_handler(self, settings):
        """Set settings needed for audit log handler and temporary add the handler"""
        settings.AZURE_DATA_COLLECTION_ENDPOINT = "mock-endpoint"
        settings.AZURE_DATA_COLLECTION_RULE_ID = "mock-rule-id"
        settings.AZURE_DATA_COLLECTION_STREAM_NAME = "mock-stream-name"
        settings.MANAGED_IDENTITY_CLIENT_ID = "mock-client-id"

        handler = BRPAuditLogHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(CustomJsonFormatter("%(asctime)s $(levelname)s %(name)s %(message)s"))
        audit_log.addHandler(handler)

        yield

        # Remove the handler after the tests
        audit_log.removeHandler(handler)

    @patch("brp_kennisgevingen.kennisgevingen.loghandler.LogsIngestionClient.upload")
    def test_audit_log_handler(self, mock_log_upload, caplog, audit_log_handler):
        log_message = "Audit log message"
        audit_log.info(
            log_message,
            extra={"burgerservicenummers": ["123456789"], "response": {"status": "success"}},
        )
        # Assert the upload function is called
        mock_log_upload.assert_called_with(
            rule_id="mock-rule-id", stream_name="mock-stream-name", logs=ANY
        )
        # Assert extra parameters have been added to the logs
        for parameter in ["logSize", "burgerservicenummersGzip", "responseGzip"]:
            assert all(parameter in log for log in mock_log_upload.call_args_list[0][1]["logs"])

        assert log_message in caplog.messages

    @patch("brp_kennisgevingen.kennisgevingen.loghandler.LogsIngestionClient.upload")
    def test_audit_log_handler_exception(self, mock_log_upload, audit_log_handler):
        mock_log_upload.side_effect = HttpResponseError("Failed to upload log")

        log_message = "Log message"
        with pytest.raises(AuditLogResponseError):
            audit_log.info(log_message)
