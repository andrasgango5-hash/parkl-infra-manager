import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

import requests
from flask import current_app, has_app_context


DEFAULT_RMS_BASE_URL = "https://api.rms.teltonika-networks.com"
RMS_TIMEOUT_SECONDS = 20
RESPONSE_LOG_LIMIT = 500
RMS_DEVICE_DEFAULT_PAGE_SIZE = 10
RMS_DEVICE_MAX_PAGES = 1000


class TeltonikaRMSError(RuntimeError):
    """Base error for safe, user-facing RMS failures."""


class TeltonikaRMSConfigurationError(TeltonikaRMSError):
    pass


class TeltonikaRMSRequestError(TeltonikaRMSError):
    pass


def get_rms_headers():
    token = os.environ.get("TELTONIKA_RMS_API_TOKEN", "").strip()
    if not token:
        raise TeltonikaRMSConfigurationError(
            "Hiányzik a TELTONIKA_RMS_API_TOKEN környezeti változó."
        )
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Parkl-Infra-Manager/1.0",
    }


def build_rms_url(path, params=None):
    base_url = os.environ.get(
        "TELTONIKA_RMS_API_BASE_URL", DEFAULT_RMS_BASE_URL
    ).rstrip("/")
    normalized_path = "/" + str(path or "").lstrip("/")
    url = f"{base_url}{normalized_path}"
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"
    return url


def rms_get(path, params=None):
    logger = _get_logger()
    url = build_rms_url(path, params)
    logger.info("Teltonika RMS GET URL=%s", url)
    try:
        response = requests.get(
            url,
            headers=get_rms_headers(),
            timeout=RMS_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        logger.exception(
            "Teltonika RMS timeout URL=%s timeout=%ss",
            url,
            RMS_TIMEOUT_SECONDS,
        )
        raise TeltonikaRMSRequestError(
            "A Teltonika RMS API hívása időtúllépés miatt megszakadt."
        ) from exc
    except requests.ConnectionError as exc:
        logger.exception(
            "Teltonika RMS connection error URL=%s exception_type=%s error=%s",
            url,
            type(exc).__name__,
            exc,
        )
        raise TeltonikaRMSRequestError(
            "A Teltonika RMS API nem érhető el kapcsolati hiba miatt."
        ) from exc
    except requests.RequestException as exc:
        logger.exception(
            "Teltonika RMS request error URL=%s exception_type=%s error=%s",
            url,
            type(exc).__name__,
            exc,
        )
        raise TeltonikaRMSRequestError(
            "A Teltonika RMS API hívása technikai hiba miatt nem sikerült."
        ) from exc

    logger.info(
        "Teltonika RMS response status_code=%s body=%s",
        response.status_code,
        _response_preview(response.text),
    )
    if not response.ok:
        logger.error(
            "Teltonika RMS HTTP error URL=%s status_code=%s body=%s",
            url,
            response.status_code,
            _response_preview(response.text),
        )
        if response.status_code == 403 and "/data-usage" in url:
            raise TeltonikaRMSRequestError(
                "A havi RMS adatforgalom nem kérdezhető le. "
                "Valószínűleg hiányzik a company_device_statistics:read RMS scope."
            )
        raise TeltonikaRMSRequestError(
            f"A Teltonika RMS API HTTP {response.status_code} hibát adott."
        )
    try:
        payload = response.json()
    except requests.JSONDecodeError as exc:
        logger.exception(
            "Teltonika RMS JSON parse error URL=%s status_code=%s body=%s",
            url,
            response.status_code,
            _response_preview(response.text),
        )
        raise TeltonikaRMSRequestError(
            "A Teltonika RMS API válasza nem érvényes JSON."
        ) from exc
    keys = sorted(payload.keys()) if isinstance(payload, dict) else []
    logger.info("Teltonika RMS response JSON keys=%s", keys)
    return payload


def list_rms_devices():
    logger = _get_logger()
    devices = []
    seen_devices = set()
    page = 1
    page_count = 0

    while page <= RMS_DEVICE_MAX_PAGES:
        payload = rms_get("/devices", params={"page": page})
        page_devices = _extract_rms_device_page(payload)
        page_count += 1

        new_devices = 0
        for index, raw_device in enumerate(page_devices):
            identity = _rms_device_identity(raw_device, page, index)
            if identity in seen_devices:
                continue
            seen_devices.add(identity)
            devices.append(raw_device)
            new_devices += 1

        pagination = _rms_pagination_state(
            payload,
            page=page,
            page_size=len(page_devices),
        )
        logger.info(
            "Teltonika RMS devices page=%s records=%s new_records=%s "
            "total_collected=%s last_page=%s total_expected=%s has_more=%s",
            page,
            len(page_devices),
            new_devices,
            len(devices),
            pagination["last_page"],
            pagination["total"],
            pagination["has_more"],
        )
        if not pagination["has_more"]:
            break
        if page_devices and new_devices == 0:
            logger.warning(
                "Teltonika RMS pagination stopped because page %s repeated "
                "already collected devices.",
                page,
            )
            break
        page = pagination["next_page"]
    else:
        raise TeltonikaRMSRequestError(
            "A Teltonika RMS eszközlapozás elérte a biztonsági oldallimitet."
        )

    _log_rms_device_counts(devices, page_count)
    return devices


def _extract_rms_device_page(payload):
    logger = _get_logger()
    if not isinstance(payload, dict):
        raise TeltonikaRMSRequestError(
            "A Teltonika RMS válasza nem objektum."
        )
    if payload.get("success") is not True:
        logger.error(
            "Teltonika RMS unsuccessful response success=%r keys=%s",
            payload.get("success"),
            sorted(payload.keys()),
        )
        raise TeltonikaRMSRequestError(
            "A Teltonika RMS API sikertelen választ adott."
        )
    devices = payload.get("data")
    if not isinstance(devices, list):
        logger.error(
            "Teltonika RMS invalid data field type=%s keys=%s",
            type(devices).__name__,
            sorted(payload.keys()),
        )
        raise TeltonikaRMSRequestError(
            "A Teltonika RMS válasz data mezője nem eszközlista."
        )
    return devices


def _log_rms_device_counts(devices, page_count):
    logger = _get_logger()
    normalized = []
    iccid_count = 0
    mobile_count = 0
    wired_count = 0
    for raw_device in devices:
        try:
            device = normalize_rms_device(raw_device)
        except (TypeError, ValueError):
            continue
        normalized.append(device)
        if device["iccid"]:
            iccid_count += 1
        if device["connection_type"] == "mobile":
            mobile_count += 1
        else:
            wired_count += 1
    logger.info(
        "Teltonika RMS devices complete pages=%s received=%s valid=%s "
        "with_iccid=%s mobile=%s wired=%s",
        page_count,
        len(devices),
        len(normalized),
        iccid_count,
        mobile_count,
        wired_count,
    )


def _rms_pagination_state(payload, page, page_size):
    containers = [payload]
    for key in ("meta", "pagination", "page"):
        value = payload.get(key)
        if isinstance(value, dict):
            containers.append(value)

    current_page = _first_positive_int(
        containers,
        "current_page",
        "currentPage",
        "page",
        "number",
    ) or page
    last_page = _first_positive_int(
        containers,
        "last_page",
        "lastPage",
        "total_pages",
        "totalPages",
        "pages",
    )
    total = _first_nonnegative_int(
        containers,
        "total",
        "total_count",
        "totalCount",
        "total_records",
        "totalRecords",
    )
    per_page = _first_positive_int(
        containers,
        "per_page",
        "perPage",
        "page_size",
        "pageSize",
        "limit",
    )
    next_page = _next_page_from_links(payload) or current_page + 1

    if last_page is not None:
        has_more = current_page < last_page
    elif total is not None:
        effective_page_size = per_page or page_size or RMS_DEVICE_DEFAULT_PAGE_SIZE
        has_more = current_page * effective_page_size < total
    elif _next_page_from_links(payload) is not None:
        has_more = True
    else:
        has_more = page_size >= RMS_DEVICE_DEFAULT_PAGE_SIZE

    return {
        "current_page": current_page,
        "last_page": last_page,
        "total": total,
        "next_page": next_page,
        "has_more": has_more,
    }


def _first_positive_int(containers, *keys):
    value = _first_int(containers, *keys)
    return value if value is not None and value > 0 else None


def _first_nonnegative_int(containers, *keys):
    value = _first_int(containers, *keys)
    return value if value is not None and value >= 0 else None


def _first_int(containers, *keys):
    for container in containers:
        for key in keys:
            value = container.get(key)
            try:
                if value not in (None, ""):
                    return int(value)
            except (TypeError, ValueError):
                continue
    return None


def _next_page_from_links(payload):
    links = payload.get("links")
    next_value = links.get("next") if isinstance(links, dict) else None
    if next_value in (None, "", False):
        next_value = payload.get("next")
    if isinstance(next_value, int):
        return next_value
    if isinstance(next_value, str):
        match = re.search(r"[?&]page=(\d+)", next_value)
        if match:
            return int(match.group(1))
    next_page = payload.get("next_page")
    try:
        if next_page not in (None, ""):
            return int(next_page)
    except (TypeError, ValueError):
        pass
    return None


def _rms_device_identity(raw_device, page, index):
    if isinstance(raw_device, dict):
        for key in ("id", "rms_device_id", "device_id"):
            if raw_device.get(key) not in (None, ""):
                return f"id:{raw_device[key]}"
        return "record:" + json.dumps(
            raw_device,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
    return f"page:{page}:index:{index}:{raw_device!r}"


def get_device_usage(device_id, start_date, end_date, return_summary=False):
    logger = _get_logger()
    if device_id in (None, ""):
        raise ValueError("Az RMS eszközazonosító kötelező.")

    start = _coerce_date(start_date, "start_date")
    end = _coerce_date(end_date, "end_date")
    if start > end:
        raise ValueError("A kezdő dátum nem lehet későbbi a záró dátumnál.")

    daily_by_date = {}
    chunk_requests = 0
    chunk_errors = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=6), end)
        chunk_requests += 1
        try:
            rows = _get_device_usage_chunk(device_id, chunk_start, chunk_end)
        except TeltonikaRMSError as exc:
            chunk_errors.append(exc)
            logger.exception(
                "Teltonika RMS data usage chunk failed device_id=%s "
                "start_date=%s end_date=%s exception_type=%s",
                device_id,
                chunk_start.isoformat(),
                chunk_end.isoformat(),
                type(exc).__name__,
            )
            chunk_start = chunk_end + timedelta(days=1)
            continue
        for row in rows:
            if row["date"] in daily_by_date:
                logger.warning(
                    "Teltonika RMS duplicate daily usage date device_id=%s date=%s",
                    device_id,
                    row["date"],
                )
            daily_by_date[row["date"]] = row
        chunk_start = chunk_end + timedelta(days=1)

    usage = [daily_by_date[key] for key in sorted(daily_by_date)]
    summary = {
        "records": usage,
        "chunk_requests": chunk_requests,
        "chunk_errors": len(chunk_errors),
        "scope_errors": sum(
            "company_device_statistics:read" in str(exc)
            for exc in chunk_errors
        ),
        "error_message": str(chunk_errors[0]) if chunk_errors else None,
    }
    if not usage and chunk_errors and not return_summary:
        raise chunk_errors[0]
    logger.info(
        "Teltonika RMS device usage complete device_id=%s start_date=%s "
        "end_date=%s chunks=%s chunk_errors=%s daily_records=%s",
        device_id,
        start.isoformat(),
        end.isoformat(),
        chunk_requests,
        len(chunk_errors),
        len(usage),
    )
    if return_summary:
        return summary
    return usage


def _get_device_usage_chunk(device_id, start, end):
    logger = _get_logger()
    params = {
        "start_date": f"{start.isoformat()} 00:00:00",
        "end_date": f"{end.isoformat()} 23:59:59",
        "version": "new",
    }
    payload = rms_get(f"/devices/{device_id}/data-usage", params=params)
    logger.debug(
        "Teltonika RMS device usage raw response device_id=%s response=%s",
        device_id,
        json.dumps(payload, ensure_ascii=False, default=str),
    )
    if not isinstance(payload, dict):
        raise TeltonikaRMSRequestError(
            "A Teltonika RMS adatforgalmi válasza nem objektum."
        )
    if payload.get("success") is not True:
        logger.error(
            "Teltonika RMS device usage unsuccessful device_id=%s keys=%s",
            device_id,
            sorted(payload.keys()),
        )
        raise TeltonikaRMSRequestError(
            "A Teltonika RMS sikertelen adatforgalmi választ adott."
        )
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise TeltonikaRMSRequestError(
            "A Teltonika RMS adatforgalmi válasz data mezője nem lista."
        )

    usage = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("date"):
            logger.warning(
                "Teltonika RMS invalid daily usage row device_id=%s row=%s",
                device_id,
                row,
            )
            continue
        sent, received = _daily_usage_totals(row)
        usage.append(
            {
                "date": str(row["date"]),
                "sent": _plain_number(sent),
                "received": _plain_number(received),
                "total": _plain_number(sent + received),
            }
        )
    logger.info(
        "Teltonika RMS device usage device_id=%s start_date=%s end_date=%s "
        "daily_records=%s",
        device_id,
        start.isoformat(),
        end.isoformat(),
        len(usage),
    )
    return usage


def normalize_rms_device(raw_device):
    if not isinstance(raw_device, dict):
        raise ValueError("Az RMS eszközrekord nem objektum.")

    def first_value(*keys):
        containers = [raw_device]
        for nested_key in ("device", "attributes", "mobile", "modem", "statistics"):
            nested = raw_device.get(nested_key)
            if isinstance(nested, dict):
                containers.append(nested)
        for container in containers:
            for key in keys:
                value = container.get(key)
                if value not in (None, ""):
                    return value
        return None

    sent, sent_unit = _traffic_value_and_unit(
        raw_device, "sent", ("sent_mb", "tx_mb", "data_sent_mb")
    )
    received, received_unit = _traffic_value_and_unit(
        raw_device, "received", ("received_mb", "rx_mb", "data_received_mb")
    )
    iccid = normalize_iccid(first_value("iccid", "sim_iccid", "sim_number"))
    rms_device_id = first_value("id", "rms_device_id", "device_id")
    name = _clean_text(first_value("name", "device_name"))
    if rms_device_id is None and not iccid and not name:
        raise ValueError("Az RMS eszközrekord nem tartalmaz azonosítható adatot.")
    return {
        "rms_device_id": str(rms_device_id) if rms_device_id is not None else None,
        "name": name,
        "serial": _clean_text(first_value("serial", "serial_number")),
        "imei": _clean_text(first_value("imei")),
        "iccid": iccid,
        "operator": _clean_text(first_value("operator", "network_operator")),
        "model": _clean_text(first_value("model", "device_model")),
        "online_status": first_value(
            "wan_state", "online", "status", "online_status"
        ),
        "sent": sent,
        "received": received,
        "sent_unit": sent_unit,
        "received_unit": received_unit,
        "remaining_data": first_value(
            "remaining_data", "data_remaining", "remaining"
        ),
        "connection_type": _normalize_connection_type(
            first_value("connection_type"), iccid
        ),
        "raw": raw_device,
    }


def sync_rms_devices_to_m2m(raw_devices=None):
    from app import db
    from models import M2MSubscription

    devices = list_rms_devices() if raw_devices is None else raw_devices
    subscriptions = M2MSubscription.query.all()
    by_iccid = {
        normalize_iccid(item.sim_number): item
        for item in subscriptions
        if normalize_iccid(item.sim_number)
    }
    by_rms_id = {
        str(item.teltonika_rms_device_id): item
        for item in subscriptions
        if item.teltonika_rms_device_id
    }
    result = _empty_sync_result(len(devices))
    now = datetime.now(timezone.utc)

    for raw_device in devices:
        try:
            device = normalize_rms_device(raw_device)
        except (ValueError, TypeError):
            result["errors"] += 1
            continue

        subscription = (
            by_iccid.get(device["iccid"]) if device["iccid"] else None
        )
        if subscription is None and device["rms_device_id"]:
            subscription = by_rms_id.get(device["rms_device_id"])

        if device["connection_type"] != "mobile":
            result["skipped_wired_unknown"] += 1
            if subscription:
                _apply_rms_metadata(subscription, device, now)
                subscription.connection_type = "wired"
            continue
        if subscription is None:
            result["unmatched_mobile"] += 1
            continue

        _apply_rms_metadata(subscription, device, now)
        subscription.connection_type = "mobile"
        result["linked_by_iccid"] += int(
            bool(device["iccid"])
            and normalize_iccid(subscription.sim_number) == device["iccid"]
        )
        result["mobile_updated"] += 1

    db.session.flush()
    return result


def sync_rms_usage_to_m2m(raw_devices=None, sync_period=None):
    from app import db
    from models import M2MMonthlyUsage, M2MSubscription

    devices = list_rms_devices() if raw_devices is None else raw_devices
    period = sync_period or date.today()
    period_date = period.date() if isinstance(period, datetime) else period
    month_start = period_date.replace(day=1)
    subscriptions = M2MSubscription.query.all()
    by_iccid = {
        normalize_iccid(item.sim_number): item
        for item in subscriptions
        if normalize_iccid(item.sim_number)
    }
    result = _empty_sync_result(len(devices))
    now = datetime.now(timezone.utc)

    for raw_device in devices:
        try:
            device = normalize_rms_device(raw_device)
        except (ValueError, TypeError):
            result["errors"] += 1
            continue
        if device["connection_type"] != "mobile":
            result["skipped_wired_unknown"] += 1
            continue

        subscription = by_iccid.get(device["iccid"])
        if subscription is None:
            result["unmatched_mobile"] += 1
            continue
        _apply_rms_metadata(subscription, device, now)
        subscription.connection_type = "mobile"
        result["linked_by_iccid"] += 1
        result["mobile_updated"] += 1

        if not device["rms_device_id"]:
            subscription.last_rms_error = (
                "A havi adatforgalomhoz hiányzik az RMS eszközazonosító."
            )
            result["errors"] += 1
            continue
        result["usage_requested"] += 1
        try:
            usage_summary = get_device_usage(
                device["rms_device_id"],
                month_start,
                period_date,
                return_summary=True,
            )
        except TeltonikaRMSError as exc:
            subscription.last_rms_error = str(exc)
            result["errors"] += 1
            if "company_device_statistics:read" in str(exc):
                result["scope_errors"] += 1
            _get_logger().exception(
                "Teltonika RMS monthly usage sync failed subscription_id=%s "
                "rms_device_id=%s exception_type=%s",
                subscription.id,
                device["rms_device_id"],
                type(exc).__name__,
            )
            continue
        except Exception as exc:
            subscription.last_rms_error = (
                "Váratlan hiba történt a havi RMS adatforgalom lekérésekor."
            )
            result["errors"] += 1
            _get_logger().exception(
                "Unexpected Teltonika RMS monthly usage error "
                "subscription_id=%s rms_device_id=%s exception_type=%s",
                subscription.id,
                device["rms_device_id"],
                type(exc).__name__,
            )
            continue
        result["usage_chunk_requests"] += usage_summary["chunk_requests"]
        result["usage_chunk_errors"] += usage_summary["chunk_errors"]
        result["scope_errors"] += usage_summary["scope_errors"]
        result["errors"] += usage_summary["chunk_errors"]
        daily_usage = usage_summary["records"]
        result["usage_daily_records"] += len(daily_usage)
        if not daily_usage and usage_summary["chunk_errors"]:
            subscription.last_rms_error = usage_summary["error_message"]
            continue
        if not daily_usage:
            subscription.last_rms_error = None
            result["usage_no_data"] += 1
            continue

        monthly_sent = sum(
            (_decimal_or_none(item.get("sent")) or Decimal("0"))
            for item in daily_usage
        )
        monthly_received = sum(
            (_decimal_or_none(item.get("received")) or Decimal("0"))
            for item in daily_usage
        )
        monthly_total = sum(
            (_decimal_or_none(item.get("total")) or Decimal("0"))
            for item in daily_usage
        )
        if monthly_total != monthly_sent + monthly_received:
            monthly_total = monthly_sent + monthly_received
        total_mb = monthly_total / Decimal(1024 * 1024)
        result["usage_total_mb"] += total_mb
        _get_logger().info(
            "Teltonika RMS monthly usage subscription_id=%s rms_device_id=%s "
            "monthly_sent_bytes=%s monthly_received_bytes=%s "
            "monthly_total_bytes=%s monthly_total_mb=%s",
            subscription.id,
            device["rms_device_id"],
            monthly_sent,
            monthly_received,
            monthly_total,
            total_mb,
        )
        usage = M2MMonthlyUsage.query.filter_by(
            subscription_id=subscription.id,
            year=period_date.year,
            month=period_date.month,
            source="teltonika_api",
        ).first()
        if usage is None:
            usage = M2MMonthlyUsage(
                subscription_id=subscription.id,
                year=period_date.year,
                month=period_date.month,
                source="teltonika_api",
            )
            db.session.add(usage)
            result["usage_created"] += 1
        else:
            result["usage_updated"] += 1
        usage.usage_mb = total_mb
        subscription.last_rms_error = (
            "A havi adatforgalom részleges: "
            f"{usage_summary['chunk_errors']} chunk lekérése hibázott."
            if usage_summary["chunk_errors"]
            else None
        )

    _get_logger().info(
        "Teltonika RMS monthly usage sync requested=%s created=%s updated=%s "
        "chunks=%s chunk_errors=%s daily_records=%s total_mb=%s "
        "no_data=%s errors=%s scope_errors=%s",
        result["usage_requested"],
        result["usage_created"],
        result["usage_updated"],
        result["usage_chunk_requests"],
        result["usage_chunk_errors"],
        result["usage_daily_records"],
        result["usage_total_mb"],
        result["usage_no_data"],
        result["errors"],
        result["scope_errors"],
    )
    db.session.flush()
    return result


def normalize_iccid(value):
    if value in (None, ""):
        return None
    normalized = re.sub(r"[\s-]+", "", str(value).strip())
    return normalized or None


def _clean_text(value):
    return str(value).strip() if value not in (None, "") else None


def _normalize_connection_type(value, iccid):
    if iccid:
        return "mobile"
    normalized = str(value or "").strip().lower()
    if normalized in {"mobile", "cellular", "gsm", "lte", "5g", "4g", "3g"}:
        return "mobile"
    if normalized in {"wired", "ethernet", "lan"}:
        return "wired"
    return "wired"


def _decimal_or_none(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _coerce_date(value, field_name):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"A {field_name} mező YYYY-MM-DD formátumban szükséges."
        ) from exc


def _daily_usage_totals(row):
    sent = Decimal("0")
    received = Decimal("0")
    modems = row.get("modems")
    if isinstance(modems, list):
        for modem in modems:
            if not isinstance(modem, dict):
                continue
            sims = modem.get("sims")
            if not isinstance(sims, list):
                continue
            for sim in sims:
                data = sim.get("data") if isinstance(sim, dict) else None
                if not isinstance(data, dict):
                    continue
                sent += _decimal_or_none(data.get("tx")) or Decimal("0")
                received += _decimal_or_none(data.get("rx")) or Decimal("0")
        return sent, received

    # Backward compatibility with the pre-2025 RMS response.
    for key, value in row.items():
        if re.fullmatch(r"sim\d+_tx", str(key)):
            sent += _decimal_or_none(value) or Decimal("0")
        elif re.fullmatch(r"sim\d+_rx", str(key)):
            received += _decimal_or_none(value) or Decimal("0")
    if sent or received:
        return sent, received

    sent = _decimal_or_none(row.get("sent", row.get("tx"))) or Decimal("0")
    received = (
        _decimal_or_none(row.get("received", row.get("rx"))) or Decimal("0")
    )
    return sent, received


def _plain_number(value):
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _traffic_value_and_unit(raw_device, base_key, mb_keys):
    containers = [raw_device]
    for nested_key in ("statistics", "traffic", "mobile", "data_usage"):
        nested = raw_device.get(nested_key)
        if isinstance(nested, dict):
            containers.append(nested)
    for container in containers:
        for key in mb_keys:
            if container.get(key) not in (None, ""):
                return container.get(key), "MB"
    for container in containers:
        value = container.get(base_key)
        if value not in (None, ""):
            unit = (
                container.get(f"{base_key}_unit")
                or container.get("traffic_unit")
                or container.get("data_unit")
                or raw_device.get(f"{base_key}_unit")
                or raw_device.get("traffic_unit")
                or raw_device.get("data_unit")
            )
            return value, str(unit).upper() if unit else None
    return None, None


def _apply_rms_metadata(subscription, device, synced_at):
    subscription.teltonika_rms_device_id = device["rms_device_id"]
    subscription.teltonika_rms_name = device["name"]
    subscription.teltonika_imei = device["imei"]
    subscription.teltonika_operator = device["operator"]
    subscription.last_rms_sync_at = synced_at
    subscription.last_api_sync_at = synced_at
    subscription.rms_sent_raw = (
        str(device["sent"]) if device["sent"] is not None else None
    )
    subscription.rms_received_raw = (
        str(device["received"]) if device["received"] is not None else None
    )
    subscription.last_rms_error = None


def _empty_sync_result(device_count):
    return {
        "rms_devices": device_count,
        "linked_by_iccid": 0,
        "mobile_updated": 0,
        "skipped_wired_unknown": 0,
        "unmatched_mobile": 0,
        "usage_created": 0,
        "usage_updated": 0,
        "usage_requested": 0,
        "usage_chunk_requests": 0,
        "usage_chunk_errors": 0,
        "usage_daily_records": 0,
        "usage_total_mb": Decimal("0"),
        "usage_no_data": 0,
        "scope_errors": 0,
        "errors": 0,
    }


def _get_logger():
    if has_app_context():
        return current_app.logger
    return logging.getLogger(__name__)


def _response_preview(payload):
    text = str(payload or "").replace("\r", " ").replace("\n", " ")
    return text[:RESPONSE_LOG_LIMIT]
