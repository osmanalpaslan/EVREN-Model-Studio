"""EVREN API hata sınıflandırması ve yeniden deneme politikası.

Kurallar (docs/knowledge/RECOVERY_PLAYBOOK.md ile uyumlu):
- 400/422 : istek hatalı — tekrar deneme (yeni bilgi olmadan) YOK
- 401/403 : kimlik doğrulama — tekrar deneme YOK, kullanıcıya anahtar kontrolü
- 404     : model/endpoint yok — tekrar deneme YOK
- 413     : istek çok büyük — tekrar deneme YOK
- 408     : zaman aşımı — sınırlı tekrar
- 429     : kota — Retry-After'a uy, yoksa artan bekleme
- 500/502/503/504 : sağlayıcı — Retry-After varsa ona uy, yoksa artan bekleme;
                    503 'sağlıklı endpoint yok' sağlayıcı kaynaklıdır, istemci
                    hatası DEĞİLDİR. En fazla 3 otomatik deneme.
- execution_unknown : akış kopması — otomatik tekrar YOK; önce
  GET /v1/requests/{id} sorgusu, sonuç belirsizse kullanıcı kararı.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass


class ErrorKind(enum.Enum):
    AUTH = "kimlik_doğrulama"
    NOT_FOUND = "bulunamadı"
    RATE_LIMIT = "kota_sınırı"
    SERVER_UNAVAILABLE = "sunucu_kullanılamıyor"
    SERVER_ERROR = "sunucu_hatası"
    TIMEOUT = "zaman_aşımı"
    REQUEST_TOO_LARGE = "istek_çok_büyük"
    VALIDATION = "geçersiz_istek"
    NETWORK = "ağ_hatası"
    UNKNOWN_RESULT = "belirsiz_sonuç"
    UNKNOWN = "bilinmeyen"


STATUS_MAP = {
    400: ErrorKind.VALIDATION,
    401: ErrorKind.AUTH,
    403: ErrorKind.AUTH,
    404: ErrorKind.NOT_FOUND,
    408: ErrorKind.TIMEOUT,
    413: ErrorKind.REQUEST_TOO_LARGE,
    422: ErrorKind.VALIDATION,
    429: ErrorKind.RATE_LIMIT,
    500: ErrorKind.SERVER_ERROR,
    502: ErrorKind.SERVER_ERROR,
    503: ErrorKind.SERVER_UNAVAILABLE,
    504: ErrorKind.SERVER_ERROR,
}

# Otomatik tekrar DENENEBİLECEK türler (kullanıcı ayarıyla sınırlı).
RETRYABLE_KINDS = {
    ErrorKind.RATE_LIMIT,
    ErrorKind.SERVER_UNAVAILABLE,
    ErrorKind.SERVER_ERROR,
    ErrorKind.TIMEOUT,
    ErrorKind.NETWORK,
}

TURKCE_ACIKLAMALAR = {
    ErrorKind.AUTH: (
        "API anahtarı reddedildi veya bu işlem için yetkiniz yok. "
        "Anahtarın doğru ve aktif olduğunu EVREN panelinden kontrol edin."
    ),
    ErrorKind.NOT_FOUND: (
        "İstenen model veya adres bulunamadı. Model adını model listesinden "
        "seçtiğinizden emin olun; sağlayıcı modeli geçici olarak kaldırmış olabilir."
    ),
    ErrorKind.RATE_LIMIT: (
        "Kullanım sınırına ulaşıldı (429). Sistem, Retry-After süresine uygun "
        "bekleyip sınırlı sayıda yeniden deneyecek. Kota sayfanızdan kullanım "
        "durumunu görebilirsiniz."
    ),
    ErrorKind.SERVER_UNAVAILABLE: (
        "Sunucu hizmet veremiyor (503). Bu genellikle sağlayıcı kaynaklıdır: "
        "model için sağlıklı endpoint bulunmuyor veya bakım sürüyor. "
        "Yerel bilgisayarınızda veya anahtarınızda sorun yoktur."
    ),
    ErrorKind.SERVER_ERROR: (
        "Sunucu tarafında geçici bir hata oluştu. Sistem sınırlı sayıda "
        "yeniden deneme yapacak; sorun sürerse EVREN Durum İzleme'yi çalıştırın."
    ),
    ErrorKind.TIMEOUT: (
        "İstek zaman aşımına uğradı. İstek sunucuda çalışmış olabilir; "
        "aynı uzun istek otomatik olarak tekrar gönderilmez."
    ),
    ErrorKind.REQUEST_TOO_LARGE: (
        "İstek çok büyük (413). Mesajı kısaltın veya dosyayı küçültün."
    ),
    ErrorKind.VALIDATION: (
        "İstek geçersiz (400/422). Gönderilen parametreler bu model tarafından "
        "desteklenmiyor olabilir; model yetenekleri sayfasını kontrol edin."
    ),
    ErrorKind.NETWORK: (
        "Ağ bağlantısı kurulamadı. İnternet bağlantınızı kontrol edin; "
        "bağlantı yoksa uygulama yerel çalışmaya devam eder."
    ),
    ErrorKind.UNKNOWN_RESULT: (
        "Sonuç belirsiz: yanıt gelirken bağlantı kesildi. İsteğin sunucuda "
        "tamamlanıp tamamlanmadığı bilinmiyor; otomatik tekrar yapılmaz. "
        "İstek durumu sorgulanıp size bilgi verilecek."
    ),
    ErrorKind.UNKNOWN: "Beklenmeyen bir hata oluştu. Ayrıntılar hata merkezinde.",
}


@dataclass
class ApiError(Exception):
    """Sınıflandırılmış API hatası; kurtarma sisteminin girdisidir."""

    kind: ErrorKind
    message: str
    status: int | None = None
    code: str | None = None
    request_id: str | None = None
    retry_after_seconds: float | None = None
    operation: str = ""
    model: str | None = None
    api_path: str | None = None

    def __str__(self) -> str:  # pragma: no cover - sadece gösterim
        base = TURKCE_ACIKLAMALAR.get(self.kind, self.message)
        parts = [base]
        if self.model:
            parts.append(f"Model: {self.model}")
        if self.status:
            parts.append(f"HTTP {self.status}")
        if self.retry_after_seconds is not None:
            parts.append(f"Önerilen bekleme: {int(self.retry_after_seconds)} sn")
        return " | ".join(parts)

    @property
    def signature(self) -> str:
        """Hata imzası: aynı sorun sınıfını geçmiş kayıtlarda bulmak için."""
        return f"{self.operation}:{self.kind.value}:{self.status}:{self.model or '-'}"

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE_KINDS


def classify_status(status: int) -> ErrorKind:
    return STATUS_MAP.get(status, ErrorKind.UNKNOWN)


def parse_retry_after(value: str | None) -> float | None:
    """Retry-After başlığını saniyeye çevirir (yalnız sayısal biçim)."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def backoff_seconds(attempt: int) -> float:
    """Retry-After yoksa artan bekleme: 5, 10, 20 saniye."""
    return min(5.0 * (2 ** max(0, attempt - 1)), 60.0)


def error_from_httpx(exc: Exception, operation: str, model: str | None = None,
                     api_path: str | None = None) -> ApiError:
    """httpx özel durumlarını ApiError'a çevirir."""
    import httpx

    # Bağlantı HİÇ kurulmadıysa istek sunucuya gitmemiştir → güvenli tekrar.
    if isinstance(exc, (httpx.ConnectTimeout, httpx.PoolTimeout)):
        return ApiError(
            kind=ErrorKind.NETWORK,
            message=f"Bağlantı zaman aşımı (istek gönderilmedi): {type(exc).__name__}",
            operation=operation, model=model, api_path=api_path,
        )
    if isinstance(exc, httpx.ConnectError):
        return ApiError(
            kind=ErrorKind.NETWORK,
            message=f"Bağlantı kurulamadı: {exc}",
            operation=operation, model=model, api_path=api_path,
        )
    # İstek gönderildikten sonra zaman aşımı → sonuç belirsiz, tekrar YOK.
    if isinstance(exc, httpx.TimeoutException):
        return ApiError(
            kind=ErrorKind.UNKNOWN_RESULT,
            message=f"Zaman aşımı: {type(exc).__name__}",
            operation=operation, model=model, api_path=api_path,
        )
    if isinstance(exc, httpx.HTTPError):
        return ApiError(
            kind=ErrorKind.NETWORK,
            message=f"Ağ hatası: {type(exc).__name__}: {exc}",
            operation=operation, model=model, api_path=api_path,
        )
    return ApiError(
        kind=ErrorKind.UNKNOWN,
        message=f"Beklenmeyen hata: {type(exc).__name__}: {exc}",
        operation=operation, model=model, api_path=api_path,
    )
