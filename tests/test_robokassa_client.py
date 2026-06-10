from urllib.parse import parse_qs, unquote_plus, urlparse

import pytest

from src import robokassa_client
from src.payments_api import calculate_topup_credits


def test_robokassa_result_signature_with_shp_params(monkeypatch):
    monkeypatch.setattr(robokassa_client, "ROBOKASSA_MERCHANT_LOGIN", "demo")
    monkeypatch.setattr(robokassa_client, "ROBOKASSA_PASSWORD1", "password1")
    monkeypatch.setattr(robokassa_client, "ROBOKASSA_PASSWORD2", "password2")

    params = {
        "OutSum": "990.00",
        "InvId": "42",
        "Shp_preorder_id": "abc",
        "SignatureValue": "74b40585da5eb3beb0ed39b998ed8e27",
    }

    robokassa_client.verify_result_signature(params)


def test_robokassa_result_signature_rejects_bad_signature(monkeypatch):
    monkeypatch.setattr(robokassa_client, "ROBOKASSA_MERCHANT_LOGIN", "demo")
    monkeypatch.setattr(robokassa_client, "ROBOKASSA_PASSWORD1", "password1")
    monkeypatch.setattr(robokassa_client, "ROBOKASSA_PASSWORD2", "password2")

    params = {
        "OutSum": "990.00",
        "InvId": "42",
        "Shp_preorder_id": "abc",
        "SignatureValue": "bad",
    }

    with pytest.raises(robokassa_client.RobokassaSignatureError):
        robokassa_client.verify_result_signature(params)


def test_topup_credit_tiers_are_server_side():
    assert calculate_topup_credits("100.00") == 3
    assert calculate_topup_credits("200.00") == 7
    assert calculate_topup_credits("500.00") == 20
    assert calculate_topup_credits("1000.00") == 45


def test_receipt_payload_is_minimal_for_self_employed():
    receipt = robokassa_client.build_receipt(
        name="Dream Wheels AI render credits",
        amount_rub="100.00",
    )

    assert receipt == {
        "items": [
            {
                "name": "Dream Wheels AI render credits",
                "quantity": 1,
                "sum": 100,
                "tax": "none",
            }
        ]
    }


def test_payment_url_includes_receipt_in_signature(monkeypatch):
    monkeypatch.setattr(robokassa_client, "ROBOKASSA_MERCHANT_LOGIN", "demo")
    monkeypatch.setattr(robokassa_client, "ROBOKASSA_PASSWORD1", "password1")
    monkeypatch.setattr(robokassa_client, "ROBOKASSA_PASSWORD2", "password2")
    monkeypatch.setattr(robokassa_client, "ROBOKASSA_IS_TEST", True)

    receipt = robokassa_client.build_receipt(
        name="Dream Wheels AI render credits",
        amount_rub="100.00",
    )
    url = robokassa_client.build_payment_url(
        amount_rub="100.00",
        invoice_id=7,
        payment_id="payment-7",
        description="Dream Wheels AI render credits #7",
        receipt=receipt,
    )

    query = parse_qs(urlparse(url).query)
    receipt_once_encoded = robokassa_client.encode_receipt(receipt)
    assert query["Receipt"] == [receipt_once_encoded]
    assert unquote_plus(receipt_once_encoded) == (
        '{"items":[{"name":"Dream Wheels AI render credits",'
        '"quantity":1,"sum":100,"tax":"none"}]}'
    )
    assert query["SignatureValue"] == ["270dda2f5180f1c59d36ef8eb3148aaa"]
