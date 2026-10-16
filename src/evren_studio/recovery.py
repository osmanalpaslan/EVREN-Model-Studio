"""Kalıcı hata bilgisi ve kurtarma sistemi.

Her hatada uygulanacak süreç (docs/knowledge/RECOVERY_PLAYBOOK.md ile
uyumlu):
1. Mevcut işi ve dosyaları koru.
2. Hatayı sınıflandır (ApiError.kind).
3. Geçmiş hata kayıtlarını imza ile ara.
4. Daha önce başarılı çözüm varsa geçerliliğini doğrula.
5. Başarısız çözümü yeni bilgi olmadan tekrarlama.
6. Sorun kaynağını ayır: istemci/ağ/kimlik/kota/model/yerel.
7. Güvenli ve sınırlı çözüm uygula, sonucu kaydet.

Bu modül karar DESTEĞİ sağlar; otomatik eylem zorlamaz.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .api.errors import ApiError, ErrorKind
from .db import Database, ErrorRecord

# Hata türü → önerilen ilk adım (kurtarma rehberinin kod tarafındaki özeti).
PLAYBOOK = {
    ErrorKind.AUTH: (
        "Anahtarı Ayarlar'dan yeniden girip bağlantı testi yapın. "
        "Anahtar EVREN panelinde aktif mi kontrol edin. "
        "Otomatik tekrar denemeyin."
    ),
    ErrorKind.RATE_LIMIT: (
        "Kullanım/Kota sayfasını açın. Retry-After süresi beklenmiş olacak; "
        "sınır hâlâ doluysa günlük sınırın sıfırlanmasını bekleyin. "
        "Daha küçük max_tokens deneyin."
    ),
    ErrorKind.SERVER_UNAVAILABLE: (
        "Sağlayıcı kaynaklı olabilir: EVREN Durum İzleme'yi çalıştırıp "
        "duyuruları ve sağlık uçlarını kontrol edin. Kodu değiştirmeyin; "
        "model geçici olarak kullanılamıyor olarak işaretlenir. "
        "Kullanıcı izni olmadan başka modele geçilmez."
    ),
    ErrorKind.SERVER_ERROR: (
        "Geçici sunucu hatası; otomatik tekrarlar tükendi. Birkaç dakika "
        "bekleyip yeniden deneyin; sürerse Durum İzleme'yi çalıştırın."
    ),
    ErrorKind.TIMEOUT: (
        "Sonuç belirsiz olabilir: aynı uzun isteği hemen tekrar göndermeyin. "
        "İstek durumu sorgusu sonucu bekleyin veya kullanıcı kararıyla "
        "kontrollü yeniden deneme yapın."
    ),
    ErrorKind.UNKNOWN_RESULT: (
        "İsteğin sunucuda çalışıp çalışmadığı bilinmiyor. İstek durumu "
        "sorgusu (GET /v1/requests/{id}) yapılacak; sonuç yine belirsizse "
        "kullanıcıya kontrollü tekrar seçeneği sunulur."
    ),
    ErrorKind.QUOTA_EXHAUSTED: (
        "Ücretli sağlayıcı: panelden kredi yükleyin veya harcama limitini "
        "artırın (OpenAI: Settings > Limits/Billing, Anthropic: Settings > "
        "Billing). Bekleyip tekrar denemek sorunu çözmez. Ücretsiz EVREN "
        "modellerine geçebilirsiniz."
    ),
    ErrorKind.NOT_FOUND: (
        "Model listesini yenileyin; model kaldırılmış olabilir. "
        "Model adını listeden seçtiğinizden emin olun."
    ),
    ErrorKind.REQUEST_TOO_LARGE: (
        "Mesajı/dosyayı küçültün; uzun bağlamı bölün."
    ),
    ErrorKind.VALIDATION: (
        "Model yeteneklerini kontrol edin: desteklenmeyen parametre "
        "(örn. tools) gönderilmiş olabilir. Model sayfasındaki yetenek "
        "satırıyla karşılaştırın."
    ),
    ErrorKind.NETWORK: (
        "İnternet bağlantısını kontrol edin. Uygulama yerel çalışmaya devam "
        "eder; bağlantı dönünce sohbetler senkron şekilde devam eder."
    ),
    ErrorKind.UNKNOWN: (
        "Ayrıntıları Hata Merkezi'nden inceleyin; tekrarlanırsa geliştirici "
        "belgelerine kaydedin."
    ),
}


@dataclass
class RecoveryAdvice:
    """Kullanıcıya sunulacak kurtarma önerisi."""

    signature: str
    kind: ErrorKind
    source_guess: str
    recommended_steps: list[str] = field(default_factory=list)
    past_success: str | None = None
    past_failures: list[str] = field(default_factory=list)
    auto_retry_happened: bool = False


SOURCE_BY_KIND = {
    ErrorKind.AUTH: "kimlik doğrulama (anahtar)",
    ErrorKind.RATE_LIMIT: "kota sınırı (sağlayıcı politikası)",
    ErrorKind.SERVER_UNAVAILABLE: "muhtemel sağlayıcı kaynaklı sorun",
    ErrorKind.SERVER_ERROR: "sağlayıcı sunucu hatası",
    ErrorKind.TIMEOUT: "ağ/sunucu gecikmesi (sonuç belirsiz olabilir)",
    ErrorKind.UNKNOWN_RESULT: "bağlantı kesilmesi (sonuç belirsiz)",
    ErrorKind.NETWORK: "yerel ağ / internet bağlantısı",
    ErrorKind.NOT_FOUND: "model kaydı / adres",
    ErrorKind.REQUEST_TOO_LARGE: "istemci tarafında çok büyük istek",
    ErrorKind.VALIDATION: "istemci ile model sözleşmesi uyumsuzluğu",
    ErrorKind.QUOTA_EXHAUSTED: "sağlayıcı hesabı (kredi/harcama sınırı)",
    ErrorKind.UNKNOWN: "bilinmiyor",
}


class RecoveryEngine:
    """Hata kaydı + geçmiş arama + öneri üretimi."""

    def __init__(self, db: Database, app_version: str):
        self.db = db
        self.app_version = app_version

    def record_error(self, err: ApiError, monitor_state: str | None = None,
                     context: str | None = None) -> int:
        rec = ErrorRecord(
            app_version=self.app_version,
            operation=err.operation,
            model=err.model,
            api_path=err.api_path,
            http_status=err.status,
            error_code=err.code,
            message=err.message,
            request_id=err.request_id,
            retry_after=(
                f"{err.retry_after_seconds:.0f} sn"
                if err.retry_after_seconds is not None else None
            ),
            monitor_state=monitor_state,
            context=context,
            signature=err.signature,
        )
        return self.db.add_error(rec)

    def advise(self, err: ApiError, auto_retry_happened: bool = False) -> RecoveryAdvice:
        """Geçmiş kayıtları tarayıp öneri üretir (salt okunur karar desteği)."""
        past = self.db.find_similar_errors(err.signature)
        past_success = None
        past_failures: list[str] = []
        for row in past:
            if row["fix_result"] and "başarılı" in row["fix_result"].lower():
                past_success = row["attempted_fix"] or "(kayıtlı çözüm)"
            elif row["fix_result"]:
                past_failures.append(
                    f"#{row['id']} ({row['fix_result'][:80]})"
                )
        steps = []
        base = PLAYBOOK.get(err.kind, PLAYBOOK[ErrorKind.UNKNOWN])
        steps.append(base)
        if past_success:
            steps.append(
                f"Aynı imzada daha önce işe yaramış çözüm (doğrulayarak "
                f"kullanın): {past_success}"
            )
        if past_failures:
            steps.append(
                "Aşağıdaki çözümler daha önce BAŞARISIZ oldu; yeni bilgi "
                "olmadan tekrar denemeyin: " + "; ".join(past_failures[:3])
            )
        return RecoveryAdvice(
            signature=err.signature,
            kind=err.kind,
            source_guess=SOURCE_BY_KIND.get(err.kind, "bilinmiyor"),
            recommended_steps=steps,
            past_success=past_success,
            past_failures=past_failures,
            auto_retry_happened=auto_retry_happened,
        )

    def resolve_and_update(self, error_id: int, attempted_fix: str,
                           fix_result: str, next_steps: str) -> None:
        """Uygulanan çözümü ve kanıtını kalıcı kayda geçirir."""
        self.db.update_error_fix(error_id, attempted_fix, fix_result, next_steps)
