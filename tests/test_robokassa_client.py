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
