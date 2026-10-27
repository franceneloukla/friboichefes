"""Gerador de BR Code Pix (EMV) para a taxa de ativação."""

from __future__ import annotations

import re

PIX_CHAVE = "02916265000160"      # CNPJ 02.916.265/0001-60 (Friboi)
PIX_NOME = "FRIBOI"
PIX_CIDADE = "SAO PAULO"
VALOR_ATIVACAO = "1.00"


def _crc16(payload: str) -> str:
    crc = 0xFFFF
    for ch in payload:
        crc ^= ord(ch) << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def _campo(campo: str, valor: str) -> str:
    return f"{campo}{len(valor):02d}{valor}"


def _limpar(texto: str, limite: int) -> str:
    sem_acento = re.sub(r"[^\x20-\x7E]", "", re.sub(r"[\u0300-\u036f]", "", texto))
    return sem_acento.strip()[:limite]


def build_pix(valor: str = VALOR_ATIVACAO, txid: str = "***") -> str:
    """Monta o copia-e-cola do Pix (estático, com valor)."""
    chave = re.sub(r"\D", "", PIX_CHAVE)
    merchant = _campo("00", "BR.GOV.BCB.PIX") + _campo("01", chave)
    tx = _campo("05", re.sub(r"[^A-Za-z0-9]", "", txid)[:25] or "***")

    payload = (
        _campo("00", "01")
        + _campo("26", merchant)
        + _campo("52", "0000")
        + _campo("53", "986")
        + _campo("54", f"{float(valor):.2f}")
        + _campo("58", "BR")
        + _campo("59", _limpar(PIX_NOME, 25) or "FRIBOI")
        + _campo("60", _limpar(PIX_CIDADE, 15) or "SAO PAULO")
        + _campo("62", tx)
    )
    payload += "6304"
    return payload + _crc16(payload)
