"""
Symbol mapping service — resolves news entities/text to Indian NSE symbols.

Strategy (in priority order):
  1. Provider-supplied symbol  → look up in company_master by symbol
  2. Provider-supplied entity name → exact / alias match in company_master
  3. Headline + description    → alias match, then partial-name match
  4. AI-returned symbol        → validate against company_master

Never creates a mapping from a weak keyword match.
Never hardcodes a default symbol.
Global/macro news that has no reliable Indian company → CONTEXT_ONLY.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Alias map  — maps common short names / abbreviations → canonical DB name
# The canonical name must exactly match company_master.company_name
# ---------------------------------------------------------------------------
_ALIASES: dict[str, str] = {
    # Reliance
    "RELIANCE": "Reliance Industries",
    "RIL": "Reliance Industries",
    "RELIANCE INDUSTRIES": "Reliance Industries",
    "RELIANCE INDUSTRIES LIMITED": "Reliance Industries",
    "RELIANCE INDUSTRIES LTD": "Reliance Industries",
    # TCS
    "TCS": "Tata Consultancy Services",
    "TATA CONSULTANCY": "Tata Consultancy Services",
    "TATA CONSULTANCY SERVICES": "Tata Consultancy Services",
    "TATA CONSULTANCY SERVICES LIMITED": "Tata Consultancy Services",
    # HDFC Bank
    "HDFC BANK": "HDFC Bank",
    "HDFC BANK LIMITED": "HDFC Bank",
    "HDFCBANK": "HDFC Bank",
    # Infosys
    "INFOSYS": "Infosys",
    "INFOSYS LIMITED": "Infosys",
    "INFOSYS LTD": "Infosys",
    "INFY": "Infosys",
    # ICICI Bank
    "ICICI BANK": "ICICI Bank",
    "ICICI BANK LIMITED": "ICICI Bank",
    "ICICIBANK": "ICICI Bank",
    # SBI
    "SBI": "State Bank of India",
    "STATE BANK": "State Bank of India",
    "STATE BANK OF INDIA": "State Bank of India",
    # Bharti Airtel
    "AIRTEL": "Bharti Airtel",
    "BHARTI AIRTEL": "Bharti Airtel",
    "BHARTIARTL": "Bharti Airtel",
    # ITC
    "ITC": "ITC",
    "ITC LIMITED": "ITC",
    # Kotak
    "KOTAK": "Kotak Mahindra Bank",
    "KOTAK BANK": "Kotak Mahindra Bank",
    "KOTAK MAHINDRA": "Kotak Mahindra Bank",
    "KOTAK MAHINDRA BANK": "Kotak Mahindra Bank",
    "KOTAKBANK": "Kotak Mahindra Bank",
    # L&T — only match the full form, not bare "LT" (too ambiguous in English text)
    "L&T": "Larsen & Toubro",
    "LARSEN": "Larsen & Toubro",
    "LARSEN & TOUBRO": "Larsen & Toubro",
    "LARSEN AND TOUBRO": "Larsen & Toubro",
    # Axis Bank
    "AXIS BANK": "Axis Bank",
    "AXIS BANK LIMITED": "Axis Bank",
    "AXISBANK": "Axis Bank",
    # Bajaj Finance
    "BAJAJ FINANCE": "Bajaj Finance",
    "BAJFINANCE": "Bajaj Finance",
    # Wipro
    "WIPRO": "Wipro",
    "WIPRO LIMITED": "Wipro",
    # HCL
    "HCL": "HCL Technologies",
    "HCL TECH": "HCL Technologies",
    "HCL TECHNOLOGIES": "HCL Technologies",
    "HCLTECH": "HCL Technologies",
    # Maruti
    "MARUTI": "Maruti Suzuki",
    "MARUTI SUZUKI": "Maruti Suzuki",
    "MARUTI SUZUKI INDIA": "Maruti Suzuki",
    # Sun Pharma
    "SUN PHARMA": "Sun Pharmaceutical",
    "SUN PHARMACEUTICAL": "Sun Pharmaceutical",
    "SUNPHARMA": "Sun Pharmaceutical",
    # Tata Motors
    "TATA MOTORS": "Tata Motors",
    "TATAMOTORS": "Tata Motors",
    # Titan
    "TITAN": "Titan Company",
    "TITAN COMPANY": "Titan Company",
    # Asian Paints
    "ASIAN PAINTS": "Asian Paints",
    "ASIANPAINT": "Asian Paints",
    # Bajaj Auto
    "BAJAJ AUTO": "Bajaj Auto",
    "BAJAJ-AUTO": "Bajaj Auto",
    # Tech Mahindra
    "TECH MAHINDRA": "Tech Mahindra",
    "TECHM": "Tech Mahindra",
    # UltraTech
    "ULTRATECH": "UltraTech Cement",
    "ULTRATECH CEMENT": "UltraTech Cement",
    "ULTRACEMCO": "UltraTech Cement",
    # Nestle
    "NESTLE": "Nestle India",
    "NESTLE INDIA": "Nestle India",
    "NESTLEIND": "Nestle India",
    # ONGC
    "ONGC": "Oil and Natural Gas Corporation",
    "OIL AND NATURAL GAS": "Oil and Natural Gas Corporation",
    # Adani
    "ADANI PORTS": "Adani Ports",
    "ADANIPORTS": "Adani Ports",
    "ADANI ENTERPRISES": "Adani Enterprises",
    "ADANIENT": "Adani Enterprises",
    "ADANI GREEN": "Adani Green Energy",
    "ADANIGREEN": "Adani Green Energy",
    # Tata Steel
    "TATA STEEL": "Tata Steel",
    "TATASTEEL": "Tata Steel",
    # JSW Steel
    "JSW STEEL": "JSW Steel",
    "JSWSTEEL": "JSW Steel",
    # Hindalco
    "HINDALCO": "Hindalco Industries",
    "HINDALCO INDUSTRIES": "Hindalco Industries",
    # Vedanta
    "VEDANTA": "Vedanta",
    "VEDL": "Vedanta",
    # Coal India
    "COAL INDIA": "Coal India",
    "COALINDIA": "Coal India",
    # BPCL
    "BPCL": "Bharat Petroleum",
    "BHARAT PETROLEUM": "Bharat Petroleum",
    # IOC
    "IOC": "Indian Oil Corporation",
    "INDIAN OIL": "Indian Oil Corporation",
    "IOCL": "Indian Oil Corporation",
    # Cipla
    "CIPLA": "Cipla",
    # Dr Reddy's
    "DR REDDY": "Dr Reddy's Laboratories",
    "DR REDDY'S": "Dr Reddy's Laboratories",
    "DRREDDY": "Dr Reddy's Laboratories",
    # Divi's
    "DIVI'S": "Divi's Laboratories",
    "DIVIS": "Divi's Laboratories",
    "DIVISLAB": "Divi's Laboratories",
    # Eicher
    "EICHER": "Eicher Motors",
    "EICHER MOTORS": "Eicher Motors",
    "EICHERMOT": "Eicher Motors",
    # Hero MotoCorp
    "HERO MOTOCORP": "Hero MotoCorp",
    "HERO MOTO": "Hero MotoCorp",
    "HEROMOTOCO": "Hero MotoCorp",
    # M&M
    "M&M": "Mahindra & Mahindra",
    "MAHINDRA": "Mahindra & Mahindra",
    "MAHINDRA & MAHINDRA": "Mahindra & Mahindra",
    # Grasim
    "GRASIM": "Grasim Industries",
    # IndusInd
    "INDUSIND": "IndusInd Bank",
    "INDUSIND BANK": "IndusInd Bank",
    "INDUSINDBK": "IndusInd Bank",
    # Bajaj Finserv
    "BAJAJ FINSERV": "Bajaj Finserv",
    "BAJAJFINSV": "Bajaj Finserv",
    # Zomato
    "ZOMATO": "Zomato",
    # Paytm
    "PAYTM": "Paytm",
    "ONE97": "Paytm",
    # GAIL
    "GAIL": "GAIL India",
    "GAIL INDIA": "GAIL India",
    # NTPC
    "NTPC": "NTPC",
    # Power Grid
    "POWER GRID": "Power Grid Corporation",
    "POWERGRID": "Power Grid Corporation",
    # Tata Power
    "TATA POWER": "Tata Power",
    "TATAPOWER": "Tata Power",
    # BHEL
    "BHEL": "Bharat Heavy Electricals",
    "BHARAT HEAVY ELECTRICALS": "Bharat Heavy Electricals",
    # HAL
    "HAL": "HAL",
    "HINDUSTAN AERONAUTICS": "HAL",
    # BEL
    "BEL": "Bharat Electronics",
    "BHARAT ELECTRONICS": "Bharat Electronics",
    # IndiGo
    "INDIGO": "Interglobe Aviation",
    "INTERGLOBE": "Interglobe Aviation",
    # Lupin
    "LUPIN": "Lupin",
    # Aurobindo
    "AUROBINDO": "Aurobindo Pharma",
    "AUROPHARMA": "Aurobindo Pharma",
    # Zydus
    "ZYDUS": "Zydus Lifesciences",
    "ZYDUSLIFE": "Zydus Lifesciences",
    # Bank of Baroda — "BOB" is too ambiguous (common English word/name)
    "BANK OF BARODA": "Bank of Baroda",
    "BANKBARODA": "Bank of Baroda",
    # PNB
    "PNB": "Punjab National Bank",
    "PUNJAB NATIONAL BANK": "Punjab National Bank",
    # Canara Bank
    "CANARA BANK": "Canara Bank",
    "CANBK": "Canara Bank",
    # Yes Bank
    "YES BANK": "Yes Bank",
    "YESBANK": "Yes Bank",
    # Tata Chemicals
    "TATA CHEMICALS": "Tata Chemicals",
    "TATACHEM": "Tata Chemicals",
    # UPL
    "UPL": "UPL",
    # Info Edge / Naukri
    "NAUKRI": "Info Edge",
    "INFO EDGE": "Info Edge",
    # Persistent
    "PERSISTENT": "Persistent Systems",
    "PERSISTENT SYSTEMS": "Persistent Systems",
    # Mphasis
    "MPHASIS": "Mphasis",
    # Coforge
    "COFORGE": "Coforge",
    # Tata Elxsi
    "TATA ELXSI": "Tata Elxsi",
    "TATAELXSI": "Tata Elxsi",
    # Hindustan Unilever
    "HUL": "Hindustan Unilever",
    "HINDUSTAN UNILEVER": "Hindustan Unilever",
    "HINDUNILVR": "Hindustan Unilever",
    # Pidilite
    "PIDILITE": "Pidilite Industries",
    "PIDILITIND": "Pidilite Industries",
    # Havells
    "HAVELLS": "Havells India",
    # Voltas
    "VOLTAS": "Voltas",
    # Bosch
    "BOSCH": "Bosch",
    "BOSCHLTD": "Bosch",
    # Siemens
    "SIEMENS": "Siemens",
    # ABB
    "ABB": "ABB India",
    "ABB INDIA": "ABB India",
    # Shriram Finance
    "SHRIRAM FINANCE": "Shriram Finance",
    "SHRIRAMFIN": "Shriram Finance",
    # Muthoot
    "MUTHOOT": "Muthoot Finance",
    "MUTHOOT FINANCE": "Muthoot Finance",
    "MUTHOOTFIN": "Muthoot Finance",
    # Cholamandalam
    "CHOLA": "Cholamandalam Investment",
    "CHOLAFIN": "Cholamandalam Investment",
    # SBI Life
    "SBI LIFE": "SBI Life Insurance",
    "SBILIFE": "SBI Life Insurance",
    # HDFC Life
    "HDFC LIFE": "HDFC Life Insurance",
    "HDFCLIFE": "HDFC Life Insurance",
    # Britannia
    "BRITANNIA": "Britannia Industries",
    # Tata Consumer
    "TATA CONSUMER": "Tata Consumer Products",
    "TATACONSUM": "Tata Consumer Products",
    # Godrej Consumer
    "GODREJ": "Godrej Consumer Products",
    "GODREJCP": "Godrej Consumer Products",
    # Dixon
    "DIXON": "Dixon Technologies",
    # Jubilant FoodWorks
    "JUBILANT": "Jubilant FoodWorks",
    "JUBLFOOD": "Jubilant FoodWorks",
    # Federal Bank
    "FEDERAL BANK": "Federal Bank",
    "FEDERALBNK": "Federal Bank",
    # IDFC First
    "IDFC FIRST": "IDFC First Bank",
    "IDFCFIRSTB": "IDFC First Bank",
    # AU Small Finance
    "AU BANK": "AU Small Finance Bank",
    "AUBANK": "AU Small Finance Bank",
    # Bandhan Bank
    "BANDHAN": "Bandhan Bank",
    "BANDHANBNK": "Bandhan Bank",
    # Petronet
    "PETRONET": "Petronet LNG",
    "PETRONET LNG": "Petronet LNG",
    # IGL
    "IGL": "Indraprastha Gas",
    "INDRAPRASTHA GAS": "Indraprastha Gas",
    # MGL
    "MGL": "Mahanagar Gas",
    "MAHANAGAR GAS": "Mahanagar Gas",
    # Gujarat Gas
    "GUJARAT GAS": "Gujarat Gas",
    "GUJGASLTD": "Gujarat Gas",
    # Castrol
    "CASTROL": "Castrol India",
    "CASTROLIND": "Castrol India",
    # Nykaa
    "NYKAA": "Nykaa",
    # Delhivery
    "DELHIVERY": "Delhivery",
    # SpiceJet
    "SPICEJET": "SpiceJet",
    # Mazagon Dock
    "MAZAGON": "Mazagon Dock",
    "MAZDOCK": "Mazagon Dock",
    # Torrent Pharma
    "TORRENT PHARMA": "Torrent Pharmaceuticals",
    "TORNTPHARM": "Torrent Pharmaceuticals",
    # L&T Technology Services
    "LTTS": "L&T Technology Services",
    "L&T TECHNOLOGY": "L&T Technology Services",
}

# ---------------------------------------------------------------------------
# Tokens that indicate global/macro news — do NOT force to an Indian stock
# ---------------------------------------------------------------------------
_GLOBAL_MACRO_TOKENS = {
    "FEDERAL RESERVE", "FED RESERVE", "US FED", "FOMC",
    "ECB", "EUROPEAN CENTRAL BANK",
    "US CPI", "US INFLATION", "US JOBS", "US GDP", "US TREASURY",
    "TREASURY YIELD", "TREASURY YIELDS",
    "CRUDE OIL", "BRENT CRUDE", "WTI CRUDE",
    "GOLD PRICE", "SILVER PRICE",
    "GEOPOLITICAL", "UKRAINE", "RUSSIA", "IRAN", "ISRAEL",
    "CHINA GDP", "CHINA ECONOMY",
    "NASDAQ", "DOW JONES", "S&P 500", "NYSE",
    "APPLE INC", "MICROSOFT CORP", "AMAZON", "ALPHABET", "META PLATFORMS",
    "TESLA INC", "NVIDIA CORP",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class SymbolMappingResult:
    __slots__ = (
        "company_name", "nse_symbol", "yahoo_symbol",
        "sector", "match_method", "status", "reason",
    )

    def __init__(
        self,
        company_name: Optional[str] = None,
        nse_symbol: Optional[str] = None,
        yahoo_symbol: Optional[str] = None,
        sector: Optional[str] = None,
        match_method: Optional[str] = None,
        status: str = "NO_TRADABLE_SYMBOL",
        reason: Optional[str] = None,
    ):
        self.company_name = company_name
        self.nse_symbol = nse_symbol
        self.yahoo_symbol = yahoo_symbol
        self.sector = sector
        self.match_method = match_method
        self.status = status          # SUCCESS | CONTEXT_ONLY | NO_TRADABLE_SYMBOL
        self.reason = reason


def resolve_symbol(
    db,
    title: str,
    description: str = "",
    provider_symbols: list[str] | None = None,
    provider_entities: list[str] | None = None,
    ai_symbol: str | None = None,
) -> SymbolMappingResult:
    """
    Resolve the best Indian NSE symbol for a news article.

    Priority:
      1. Provider-supplied symbol → validate in company_master
      2. Provider-supplied entity names → alias + exact match
      3. AI-returned symbol → validate in company_master
      4. Headline + description → alias match, then DB word-boundary match
      5. Global/macro detection → CONTEXT_ONLY (no forced symbol)
    """
    combined_text = f"{title or ''} {description or ''}".strip()
    upper_text = combined_text.upper()

    # ── Strategy 1: provider-supplied symbols ────────────────────────────────
    for raw_sym in (provider_symbols or []):
        if not raw_sym:
            continue
        sym = raw_sym.strip().upper().replace(".NS", "").replace(".BO", "")
        company = _lookup_by_symbol(db, sym)
        if company:
            return _make_result(company, "provider_symbol", title)

        # Provider symbol might be an alias key
        canonical = _ALIASES.get(sym)
        if canonical:
            company = _lookup_by_name(db, canonical)
            if company:
                return _make_result(company, "provider_symbol_alias", title)

    # ── Strategy 2: provider-supplied entity names ───────────────────────────
    for entity in (provider_entities or []):
        if not entity:
            continue
        result = _match_text_to_company(db, entity.upper(), "provider_entity")
        if result:
            return result

    # ── Strategy 3: AI-returned symbol ───────────────────────────────────────
    if ai_symbol:
        sym = ai_symbol.strip().upper().replace(".NS", "").replace(".BO", "")
        company = _lookup_by_symbol(db, sym)
        if company:
            return _make_result(company, "ai_symbol", title)
        canonical = _ALIASES.get(sym)
        if canonical:
            company = _lookup_by_name(db, canonical)
            if company:
                return _make_result(company, "ai_symbol_alias", title)

    # ── Strategy 4: headline + description text matching ─────────────────────
    result = _match_text_to_company(db, upper_text, "text_match")
    if result:
        return result

    # ── Strategy 5: global/macro detection ───────────────────────────────────
    for token in _GLOBAL_MACRO_TOKENS:
        if token in upper_text:
            _log_mapping(
                headline=title,
                detected_entity=token,
                match_method="global_macro_token",
                matched_company=None,
                nse_symbol=None,
                yahoo_symbol=None,
                status="CONTEXT_ONLY",
                reason=f"Global/macro token '{token}' — no direct Indian tradable company",
            )
            return SymbolMappingResult(
                status="CONTEXT_ONLY",
                reason=f"Global/macro news ({token}) — no direct Indian tradable company identified",
            )

    # ── No match ─────────────────────────────────────────────────────────────
    _log_mapping(
        headline=title,
        detected_entity=None,
        match_method=None,
        matched_company=None,
        nse_symbol=None,
        yahoo_symbol=None,
        status="NO_TRADABLE_SYMBOL",
        reason="No Indian company identified in headline or description",
    )
    return SymbolMappingResult(
        status="NO_TRADABLE_SYMBOL",
        reason="No Indian company identified in headline or description",
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _match_text_to_company(db, upper_text: str, method_prefix: str):
    """Try alias map first, then DB word-boundary scan."""
    # Alias map — longest match wins (sorted by length desc at module load).
    # Continue through ALL aliases even if one fires but has no DB row —
    # a shorter alias further down the list may still resolve correctly.
    for alias, canonical in _SORTED_ALIASES:
        if re.search(r"\b" + re.escape(alias) + r"\b", upper_text):
            company = _lookup_by_name(db, canonical)
            if company:
                return _make_result(company, f"{method_prefix}_alias", upper_text[:80])
            # Alias fired but company_master has no matching row — log once
            # and keep iterating so shorter/more-specific aliases still run.
            logger.warning(
                "[SYMBOL_MAPPING] alias='%s' canonical='%s' NOT IN company_master — "
                "continuing alias scan",
                alias, canonical,
            )

    # DB word-boundary scan (existing logic in CompanyRepository)
    from repositories.company_repository import CompanyRepository
    company = CompanyRepository.find_in_title(db, upper_text)
    if company:
        return _make_result(company, f"{method_prefix}_db_scan", upper_text[:80])

    return None


def _lookup_by_symbol(db, symbol: str):
    from repositories.company_repository import CompanyRepository
    return CompanyRepository.get_by_symbol(db, symbol)


def _lookup_by_name(db, name: str):
    from repositories.company_repository import CompanyRepository
    return CompanyRepository.get_by_company_name(db, name)


def _make_result(company, method: str, headline: str) -> SymbolMappingResult:
    nse_symbol = company.symbol
    yahoo_symbol = f"{nse_symbol}.NS"
    _log_mapping(
        headline=headline,
        detected_entity=company.company_name,
        match_method=method,
        matched_company=company.company_name,
        nse_symbol=nse_symbol,
        yahoo_symbol=yahoo_symbol,
        status="SUCCESS",
        reason=None,
    )
    return SymbolMappingResult(
        company_name=company.company_name,
        nse_symbol=nse_symbol,
        yahoo_symbol=yahoo_symbol,
        sector=company.sector,
        match_method=method,
        status="SUCCESS",
    )


def _log_mapping(
    headline: str,
    detected_entity,
    match_method,
    matched_company,
    nse_symbol,
    yahoo_symbol,
    status: str,
    reason,
    news_id=None,
    provider=None,
    provider_symbols=None,
    provider_entities=None,
):
    logger.info(
        "[SYMBOL_MAPPING]\n"
        "  news_id=%s\n"
        "  headline=%s\n"
        "  provider=%s\n"
        "  provider_symbols=%s\n"
        "  provider_entities=%s\n"
        "  detected_entity=%s\n"
        "  match_method=%s\n"
        "  matched_company=%s\n"
        "  nse_symbol=%s\n"
        "  yahoo_symbol=%s\n"
        "  status=%s\n"
        "  reason=%s",
        news_id,
        (headline or "")[:120],
        provider,
        provider_symbols,
        provider_entities,
        detected_entity,
        match_method,
        matched_company,
        nse_symbol,
        yahoo_symbol,
        status,
        reason,
    )


# Pre-sort aliases by length descending so longer/more-specific matches win
_SORTED_ALIASES: list[tuple[str, str]] = sorted(
    _ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True
)
