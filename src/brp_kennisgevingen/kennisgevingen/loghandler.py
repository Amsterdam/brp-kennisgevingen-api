import base64
import gzip
import json
import logging

from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential
from azure.monitor.ingestion import LogsIngestionClient
from django.conf import settings

logger = logging.getLogger(__name__)


class AuditLogResponseError(Exception):
    pass


class BRPAuditLogHandler(logging.Handler):

    def __init__(self):
        super().__init__()
        self.endpoint = settings.AZURE_DATA_COLLECTION_ENDPOINT
        self.rule_id = settings.AZURE_DATA_COLLECTION_RULE_ID
        self.stream_name = settings.AZURE_DATA_COLLECTION_STREAM_NAME

        self._credential = DefaultAzureCredential(
            managed_identity_client_id=settings.MANAGED_IDENTITY_CLIENT_ID
        )
        self._client = LogsIngestionClient(
            endpoint=self.endpoint, credential=self._credential, logging_enable=True
        )

    def emit(self, record) -> None:
        # Data collection endpoint expects a list of records
        if not isinstance(record, list):
            record = [record]

        # The custom jsonformatter returns a json string, so we'll convert it to python
        logs = [json.loads(self.format(r)) for r in record]

        # Add logSize to each log, so BenK can use the gzippedResponse for large logs
        for log in logs:
            log["logSize"] = len(json.dumps(log).encode("utf-8"))

            # Gzip the response and burgerservicenummers to be able to process large logs in Azure
            if "burgerservicenummers" in log:
                log["burgerservicenummersGzip"] = base64.b64encode(
                    gzip.compress(json.dumps(log["burgerservicenummers"]).encode("utf-8"))
                ).decode("utf-8")
            if "response" in log:
                log["responseGzip"] = base64.b64encode(
                    gzip.compress(json.dumps(log["response"]).encode("utf-8"))
                ).decode("utf-8")

        try:
            self._client.upload(
                rule_id=self.rule_id,
                stream_name=self.stream_name,
                logs=logs,
            )
        except HttpResponseError as e:
            logger.error(e)
            raise AuditLogResponseError("Failed to emit audit log") from e
