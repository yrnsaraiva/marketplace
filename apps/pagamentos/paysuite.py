"""
apps/pagamentos/paysuite.py
"""
import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PAYSUITE_BASE_URL = "https://paysuite.tech/api/v1"


class PaySuiteError(Exception):
    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class PaySuiteClient:
    def __init__(self):
        self.api_key = getattr(settings, "PAYSUITE_API_KEY", "")
        self.return_url = getattr(settings, "PAYSUITE_RETURN_URL", "")
        self.callback_url = getattr(settings, "PAYSUITE_CALLBACK_URL", "")
        self.webhook_secret = getattr(settings, "PAYSUITE_WEBHOOK_SECRET", "")
        self.timeout = 30

        if not self.api_key:
            raise PaySuiteError("PAYSUITE_API_KEY não configurado em settings.py")

    def _session(self):
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        return session

    def _handle_response(self, response):
        try:
            data = response.json()
        except ValueError:
            raise PaySuiteError(
                f"Resposta inválida da PaySuite (HTTP {response.status_code})",
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            message = data.get("message", f"Erro HTTP {response.status_code}")
            raise PaySuiteError(message, status_code=response.status_code, response=data)
        return data

    def criar_pagamento(self, amount, reference, description="", method=None,
                        return_url=None, callback_url=None):
        payload = {
            "amount": str(amount),
            "reference": reference[:50],
            "description": description[:125] if description else "",
            "return_url": return_url or self.return_url,
            "callback_url": callback_url or self.callback_url,
        }
        if method:
            payload["method"] = method
        payload = {k: v for k, v in payload.items() if v}

        logger.info("PaySuite: criar pagamento ref=%s amount=%s", reference, amount)
        try:
            resp = self._session().post(f"{PAYSUITE_BASE_URL}/payments", json=payload, timeout=self.timeout)
            data = self._handle_response(resp)
        except requests.Timeout:
            raise PaySuiteError("Timeout ao contactar PaySuite")
        except requests.ConnectionError as e:
            raise PaySuiteError(f"Erro de ligação à PaySuite: {e}")
        return data.get("data", data)

    def obter_pagamento(self, paysuite_id):
        logger.info("PaySuite: consultar pagamento id=%s", paysuite_id)
        try:
            resp = self._session().get(f"{PAYSUITE_BASE_URL}/payments/{paysuite_id}", timeout=self.timeout)
            data = self._handle_response(resp)
        except requests.Timeout:
            raise PaySuiteError("Timeout ao consultar PaySuite")
        except requests.ConnectionError as e:
            raise PaySuiteError(f"Erro de ligação à PaySuite: {e}")
        return data.get("data", data)

    def verificar_webhook(self, payload_bytes: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            logger.warning("PAYSUITE_WEBHOOK_SECRET não configurado")
            return False
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

# FIX: removida a linha 'paysuite = PaySuiteClient' que era enganosa
# (era uma referência à classe, não uma instância).
# Usar directamente: client = PaySuiteClient()