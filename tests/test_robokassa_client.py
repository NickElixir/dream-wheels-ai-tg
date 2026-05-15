import pytest

from src import robokassa_client


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
