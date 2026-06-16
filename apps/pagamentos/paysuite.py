"""
apps/pagamentos/paysuite.py

Cliente para a API PaySuite (https://paysuite.tech/docs/).
Trata criação de pagamentos, consulta de estado e verificação de webhooks.
"""

import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

PAYSUITE_BASE_URL = "https://paysuite.tech/api/v1"


class PaySuiteError(Exception):
    """Erro genérico devolvido pela PaySuite."""
    def __init__(self, message, status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class PaySuiteClient:
    """
    Wrapper sobre a API REST da PaySuite.

    Configuração necessária em settings.py (ou .env via decouple):
        PAYSUITE_API_KEY   — token Bearer obtido no dashboard
        PAYSUITE_RETURN_URL — URL base para redirect após pagamento (opcional)
        PAYSUITE_CALLBACK_URL — URL do webhook para notificações (opcional)
        PAYSUITE_WEBHOOK_SECRET — segredo para validar assinaturas do webhook
    """

    def __init__(self):
        self.api_key = getattr(settings, "PAYSUITE_API_KEY", "")
        self.return_url = getattr(settings, "PAYSUITE_RETURN_URL", "")
        self.callback_url = getattr(settings, "PAYSUITE_CALLBACK_URL", "")
        self.webhook_secret = getattr(settings, "PAYSUITE_WEBHOOK_SECRET", "")
        self.timeout = 30  # segundos

        if not self.api_key:
            raise PaySuiteError(
                "PAYSUITE_API_KEY não configurado em settings.py"
            )

    # ------------------------------------------------------------------
    # Sessão HTTP
    # ------------------------------------------------------------------

    def _session(self):
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        return session

    def _handle_response(self, response):
        """Verifica erros HTTP e devolve o JSON ou lança PaySuiteError."""
        try:
            data = response.json()
        except ValueError:
            raise PaySuiteError(
                f"Resposta inválida da PaySuite (HTTP {response.status_code})",
                status_code=response.status_code,
            )

        if response.status_code >= 400:
            message = data.get("message", f"Erro HTTP {response.status_code}")
            raise PaySuiteError(
                message,
                status_code=response.status_code,
                response=data,
            )

        return data

    # ------------------------------------------------------------------
    # Criar pagamento
    # ------------------------------------------------------------------

    def criar_pagamento(
        self,
        amount: float,
        reference: str,
        description: str = "",
        method: str = None,
        return_url: str = None,
        callback_url: str = None,
    ) -> dict:
        """
        Cria um novo pedido de pagamento na PaySuite.

        Parâmetros:
            amount       — valor em MZN
            reference    — referência única (ex: "PAG-123")
            description  — descrição opcional (max 125 chars)
            method       — 'mpesa' | 'emola' | 'credit_card' | None (escolha no checkout)
            return_url   — URL de redirect após pagamento
            callback_url — URL do webhook (sobrepõe PAYSUITE_CALLBACK_URL)

        Devolve o dict 'data' da resposta PaySuite, incluindo:
            id           — ULID do pagamento PaySuite
            status       — 'pending'
            checkout_url — URL para redirigir o utilizador
        """
        payload = {
            "amount": str(amount),
            "reference": reference[:50],  # max 50 chars
            "description": description[:125] if description else "",
            "return_url": return_url or self.return_url,
            "callback_url": callback_url or self.callback_url,
        }
        if method:
            payload["method"] = method

        # Remover campos vazios para não enviar strings vazias desnecessárias
        payload = {k: v for k, v in payload.items() if v}

        logger.info("PaySuite: criar pagamento ref=%s amount=%s", reference, amount)

        try:
            resp = self._session().post(
                f"{PAYSUITE_BASE_URL}/payments",
                json=payload,
                timeout=self.timeout,
            )
            data = self._handle_response(resp)
        except requests.Timeout:
            raise PaySuiteError("Timeout ao contactar PaySuite")
        except requests.ConnectionError as e:
            raise PaySuiteError(f"Erro de ligação à PaySuite: {e}")

        return data.get("data", data)

    # ------------------------------------------------------------------
    # Consultar estado de pagamento
    # ------------------------------------------------------------------

    def obter_pagamento(self, paysuite_id: str) -> dict:
        """
        Consulta o estado de um pagamento pelo ID da PaySuite (ULID).

        Devolve o dict 'data' com campos:
            id, amount, reference, status, transaction (se pago)
        """
        logger.info("PaySuite: consultar pagamento id=%s", paysuite_id)
        try:
            resp = self._session().get(
                f"{PAYSUITE_BASE_URL}/payments/{paysuite_id}",
                timeout=self.timeout,
            )
            data = self._handle_response(resp)
        except requests.Timeout:
            raise PaySuiteError("Timeout ao consultar PaySuite")
        except requests.ConnectionError as e:
            raise PaySuiteError(f"Erro de ligação à PaySuite: {e}")

        return data.get("data", data)

    # ------------------------------------------------------------------
    # Verificar assinatura do webhook
    # ------------------------------------------------------------------

    def verificar_webhook(self, payload_bytes: bytes, signature: str) -> bool:
        """
        Verifica a assinatura HMAC-SHA256 enviada pela PaySuite no header
        X-Webhook-Signature.

        Parâmetros:
            payload_bytes — corpo bruto da request (request.body)
            signature     — valor do header X-Webhook-Signature

        Devolve True se válido, False caso contrário.
        """
        if not self.webhook_secret:
            logger.warning("PAYSUITE_WEBHOOK_SECRET não configurado - recusando verificação")
            return False  # permissivo em dev; em prod DEVE estar configurado

        expected = hmac.new(
            self.webhook_secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)


# Instância singleton para importar directamente
paysuite = PaySuiteClient
