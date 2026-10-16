"""Ücretli sağlayıcılar için aylık bütçe koruması (tahmini).

- Her ücretli model çağrısından sonra yanıttaki token sayıları ve tarihli fiyat
  kataloğuyla (api/providers.py) tahmini maliyet `usage_costs` tablosuna yazılır.
- Toplam aylık harcama (tüm ücretli sağlayıcılar, UTC ayı) bütçenin %80'ine
  gelince bir kez uyarılır; bütçeye ulaşınca her yeni istekten ÖNCE onay istenir
  (kullanıcı onaylarsa o oturum için bu ay serbest bırakılır).
- TAHMİNDİR: gerçek fatura için sağlayıcı paneline bakın (kalan kredi API'den
  okunamıyor). Uzun bağlam fiyat kademeleri ve önbelleğe yazma ücreti hesaba
  katılmaz.
"""
from __future__ import annotations

from dataclasses import dataclass

WARN_RATIO = 0.8


def format_usd(x: float) -> str:
    """Türkçe ondalık biçim: $1.234,50"""
    return f"${x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass
class BudgetState:
    spent: float
    limit: float
    enforce: bool

    @property
    def ratio(self) -> float:
        return self.spent / self.limit if self.limit > 0 else 0.0

    @property
    def exceeded(self) -> bool:
        return self.enforce and self.limit > 0 and self.spent >= self.limit

    @property
    def warn(self) -> bool:
        return self.limit > 0 and self.ratio >= WARN_RATIO

    def text(self) -> str:
        return f"bu ay tahmini {format_usd(self.spent)} / {format_usd(self.limit)}"


def current_state(db, limit: float, enforce: bool = True) -> BudgetState:
    spent = sum(db.month_spend().values())
    return BudgetState(spent=spent, limit=float(limit), enforce=enforce)
