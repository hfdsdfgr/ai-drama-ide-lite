"""API Key 安全存储：OS 凭据管理器（keyring），无明文回退。

数据库只存 key_ref，密钥本身只进系统凭据管理器
（Windows Credential Manager / macOS Keychain / Linux SecretService）。
"""

from app.core.errors import AppError
from app.core.logging import get_logger

logger = get_logger("secrets")

SERVICE_NAME = "ai-drama-ide"


class SecretStore:
    def set(self, username: str, value: str) -> None:
        raise NotImplementedError

    def get(self, username: str) -> str | None:
        raise NotImplementedError

    def delete(self, username: str) -> None:
        raise NotImplementedError


class KeyringSecretStore(SecretStore):
    """生产实现：keyring → OS 凭据管理器。keyring 依赖延迟加载。"""

    _backend = None

    def _keyring(self):
        if KeyringSecretStore._backend is None:
            try:
                import keyring
            except ImportError as exc:
                raise AppError(
                    500,
                    "keyring_missing",
                    "系统安全存储组件不可用（keyring 未安装）",
                ) from exc
            KeyringSecretStore._backend = keyring
        return KeyringSecretStore._backend

    def set(self, username: str, value: str) -> None:
        try:
            self._keyring().set_password(SERVICE_NAME, username, value)
        except AppError:
            raise
        except Exception as exc:
            logger.exception("Failed to write secret %s", username)
            raise AppError(
                500,
                "secret_store_unavailable",
                "无法写入系统凭据管理器，请检查系统安全设置",
            ) from exc

    def get(self, username: str) -> str | None:
        try:
            return self._keyring().get_password(SERVICE_NAME, username)
        except AppError:
            raise
        except Exception as exc:
            logger.exception("Failed to read secret %s", username)
            raise AppError(
                500,
                "secret_store_unavailable",
                "无法读取系统凭据管理器，请检查系统安全设置",
            ) from exc

    def delete(self, username: str) -> None:
        try:
            self._keyring().delete_password(SERVICE_NAME, username)
        except AppError:
            raise
        except Exception:
            # 凭据不存在或删除失败都视为已清理
            logger.warning("Failed to delete secret %s", username)


class MemorySecretStore(SecretStore):
    """仅用于测试的内存实现（禁止用于生产）。"""

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def set(self, username: str, value: str) -> None:
        self._data[username] = value

    def get(self, username: str) -> str | None:
        return self._data.get(username)

    def delete(self, username: str) -> None:
        self._data.pop(username, None)
