"""Testes de destinatários de alerta."""

import os

from notifier import _alert_recipients, _smtp_configured


def test_alert_recipients_merges_primary_and_cc(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL", "joao@gmail.com")
    monkeypatch.setenv("ALERT_EMAIL_CC", "thiagofm.br@gmail.com")
    assert _alert_recipients() == ["joao@gmail.com", "thiagofm.br@gmail.com"]


def test_alert_recipients_deduplicates_and_splits(monkeypatch):
    monkeypatch.setenv("ALERT_EMAIL", "a@test.com, b@test.com;a@test.com")
    monkeypatch.delenv("ALERT_EMAIL_CC", raising=False)
    assert _alert_recipients() == ["a@test.com", "b@test.com"]


def test_smtp_configured_requires_all_secrets(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    assert _smtp_configured() is False
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USER", "a@test.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    assert _smtp_configured() is True
