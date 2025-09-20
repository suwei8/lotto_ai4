from config import settings

_collector = settings.collector

PRIMARY_DOMAIN = _collector.primary_domain
SECONDARY_DOMAIN = _collector.secondary_domain
ENDPOINT_PATH = _collector.endpoint_path
TOKEN = _collector.token
AES_KEY_HEX = _collector.aes_key_hex
AES_IV = _collector.aes_iv.encode("utf-8")
USER_AGENT = _collector.user_agent

if len(AES_IV) != 16:  # pragma: no cover - configuration validation
    raise ValueError("COLLECTOR_AES_IV 必须是 16 字节长度的字符串。当前配置无效。")
