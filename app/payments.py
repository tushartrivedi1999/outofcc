from __future__ import annotations

import hmac
import hashlib


class PaymentError(Exception):
    pass


class RazorpayGateway:
    def __init__(self, key_id: str, key_secret: str, webhook_secret: str = "") -> None:
        self.key_id = key_id
        self.key_secret = key_secret
        self.webhook_secret = webhook_secret

    def create_order(self, amount_paise: int, receipt: str, currency: str = "INR") -> dict:
        if not self.key_id or not self.key_secret:
            raise PaymentError("Razorpay keys are not configured")
        try:
            import razorpay  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency in this environment
            raise PaymentError("Razorpay SDK not available") from exc

        client = razorpay.Client(auth=(self.key_id, self.key_secret))
        return client.order.create({"amount": amount_paise, "currency": currency, "receipt": receipt})


    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        if not self.webhook_secret or not signature:
            return False
        expected = hmac.new(self.webhook_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def verify_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        if not self.key_secret:
            return False
        payload = f"{order_id}|{payment_id}".encode("utf-8")
        expected = hmac.new(self.key_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
