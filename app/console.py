from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class VerificationPayload:
    dns_txt: str
    html_file: str
    html_token: str


class SearchConsoleService:
    def build_verification_payload(self, domain: str, token: str) -> VerificationPayload:
        normalized = domain.lower().strip()
        txt = f"open-search-site-verification={token}"
        html_file = f"open-search-{token}.html"
        html_body = f"open-search-site-verification: {normalized}:{token}"
        return VerificationPayload(dns_txt=txt, html_file=html_file, html_token=html_body)

    @staticmethod
    def create_token() -> str:
        return secrets.token_urlsafe(24)

    @staticmethod
    def build_svg_bars(values: list[int], width: int = 640, height: int = 220) -> str:
        if not values:
            values = [0]
        max_value = max(values) or 1
        bar_width = max(width // len(values), 8)
        bars: list[str] = []
        for index, value in enumerate(values):
            ratio = value / max_value
            bar_height = int((height - 30) * ratio)
            x = index * bar_width
            y = height - bar_height - 20
            bars.append(f'<rect x="{x}" y="{y}" width="{bar_width - 2}" height="{bar_height}" fill="#4f46e5" />')
        return (
            f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">'
            '<rect width="100%" height="100%" fill="#f8fafc" />'
            + "".join(bars)
            + '</svg>'
        )

    @staticmethod
    def default_daily_metrics(days: int = 14) -> list[dict[str, int | str]]:
        now = datetime.now(timezone.utc).date()
        rows: list[dict[str, int | str]] = []
        for i in range(days):
            date = now - timedelta(days=days - i - 1)
            impressions = 100 + (i * 17) % 160
            clicks = int(impressions * (0.08 + (i % 4) * 0.01))
            ctr = round((clicks / impressions) * 100, 2)
            position = round(9.8 - (i * 0.08), 2)
            rows.append(
                {
                    "metric_date": date.isoformat(),
                    "impressions": impressions,
                    "clicks": clicks,
                    "ctr": ctr,
                    "avg_position": position,
                }
            )
        return rows
