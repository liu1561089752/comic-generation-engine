"""敏感配置加密工具 — AES-256-GCM。

用于 LLM / 生图 API Key 落库前加密、读取时解密。
密钥从 settings.APP_SECRET_KEY 派生（sha256 → 32 字节），
因此 APP_SECRET_KEY 必须在 .env 中固定，否则重启后旧密文无法解密。
"""
import base64
import hashlib
import os
import logging

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

logger = logging.getLogger(__name__)

# 密文格式：base64(nonce(12B) + ciphertext)
_NONCE_LEN = 12


def _derive_key() -> bytes:
    """从 APP_SECRET_KEY 派生 32 字节 AES-256 密钥。"""
    return hashlib.sha256(settings.APP_SECRET_KEY.encode("utf-8")).digest()


def encrypt_secret(plain: str) -> str:
    """加密明文，返回 base64 密文；空串直接返回空。"""
    if not plain:
        return ""
    try:
        nonce = os.urandom(_NONCE_LEN)
        ciphertext = AESGCM(_derive_key()).encrypt(nonce, plain.encode("utf-8"), None)
        return base64.b64encode(nonce + ciphertext).decode("ascii")
    except Exception as e:
        logger.error(f"加密 API Key 失败: {e}")
        raise


def decrypt_secret(cipher: str) -> str | None:
    """解密密文；无法解密（密钥变更/非本工具加密的旧明文）时返回 None。

    调用方对 None 的处理：按明文原样使用并记录 warning，
    保证旧明文数据在升级后仍可用。
    """
    if not cipher:
        return ""
    try:
        raw = base64.b64decode(cipher)
        nonce, ciphertext = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
        return AESGCM(_derive_key()).decrypt(nonce, ciphertext, None).decode("utf-8")
    except Exception:
        return None
