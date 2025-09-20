from __future__ import annotations

import base64
import json
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

import binascii
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from .constants import (
    AES_IV,
    AES_KEY_HEX,
    ENDPOINT_PATH,
    PRIMARY_DOMAIN,
    SECONDARY_DOMAIN,
    TOKEN,
    USER_AGENT,
)


class CollectorAPIError(RuntimeError):
    """Raised when the upstream采集接口返回异常。"""


@dataclass(slots=True)
class LeaderboardEntry:
    user_id: int
    nick_name: str
    payload: Dict[str, Any]


@dataclass(slots=True)
class LeaderboardResult:
    issue_name: str
    lottery_id: int
    entries: List[LeaderboardEntry]


@dataclass(slots=True)
class ExpertScheme:
    playtype_id: int
    playtype_name: str
    numbers: Sequence[Sequence[int]] | Sequence[int] | str


@dataclass(slots=True)
class DetailResult:
    issue_name: str
    lottery_id: int
    schemes: List[ExpertScheme]


def _aes_encrypt(plaintext: str) -> str:
    key = binascii.unhexlify(AES_KEY_HEX)
    cipher = AES.new(key, AES.MODE_CBC, AES_IV)
    padded = pad(plaintext.encode("utf-8"), AES.block_size)
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(encrypted).decode("utf-8")


def _request_header(action_code: str) -> Dict[str, Any]:
    return {
        "action": action_code,
        "appVersion": "4.0.6",
        "appVersionCode": 40006,
        "brand": "szcapp",
        "cmdId": 10024,
        "cmdName": "app_ald1",
        "idfa": "170976fa8bb848a7579",
        "imei": "",
        "phoneModel": "V2324HA",
        "phoneName": "vivo",
        "platformCode": "Android",
        "platformVersion": "12",
        "token": TOKEN,
        "uDomain": "17chdd.com",
        "userId": "18838011",
        "userType": "1",
        "uuid": "1ab3cdb1-c5df-3973-968c-b5119b2958fd",
    }


def _build_payload(action_code: str, body: Dict[str, Any]) -> str:
    body_json = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    header = _request_header(action_code)
    wrapper = json.dumps({"body": body_json, "header": header}, separators=(",", ":"), ensure_ascii=False)
    return _aes_encrypt(wrapper)


def _headers() -> Dict[str, str]:
    return {"User-Agent": USER_AGENT}


class _BaseClient:
    domains = (PRIMARY_DOMAIN, SECONDARY_DOMAIN)

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self._session = session or requests.Session()

    def _post_with_failover(self, payload: str, retries: int = 3, delay: float = 1.5) -> requests.Response:
        files = {"request": (None, payload)}
        headers = _headers()
        last_error: Optional[Exception] = None
        for domain in self.domains:
            url = f"https://{domain}{ENDPOINT_PATH}"
            for attempt in range(retries):
                try:
                    response = self._session.post(url, headers=headers, files=files, timeout=15)
                    if response.status_code == 200:
                        return response
                    msg = f"HTTP {response.status_code} from {domain}"
                    raise CollectorAPIError(msg)
                except Exception as exc:  # noqa: BLE001 - keep diagnostics simple
                    last_error = exc
                    sleep_time = delay * (0.8 + random.random() * 0.4)
                    time.sleep(sleep_time)
            # 当前 domain 重试完毕，换备用域名
        if last_error is None:
            last_error = CollectorAPIError("未知错误导致请求失败")
        raise last_error


class LeaderboardClient(_BaseClient):
    """调用 40030 接口获取排行榜专家列表。"""

    def fetch(
        self,
        *,
        lottery_id: int,
        playtype_id: int,
        sort_type: int,
        limit: int,
        issue_count: int,
    ) -> LeaderboardResult:
        body = {
            "issueCount": issue_count,
            "limit": limit,
            "lotteryId": str(lottery_id),
            "playTypeId": int(playtype_id),
            "sortType": int(sort_type),
        }
        payload = _build_payload("40030", body)
        response = self._post_with_failover(payload)
        data = response.json()
        if data.get("code") != 0:
            raise CollectorAPIError(f"排行榜接口返回异常: {data}")
        data_section = data.get("data") or {}
        issue_name = data_section.get("issueName") or ""
        lottery = int(data_section.get("lotteryId", lottery_id))
        rank_list: Sequence[Dict[str, Any]] = data_section.get("rankList") or []
        entries = [
            LeaderboardEntry(
                user_id=int(item.get("userId")),
                nick_name=item.get("nickName") or "",
                payload=item,
            )
            for item in rank_list
            if item.get("userId") is not None
        ]
        return LeaderboardResult(issue_name=issue_name, lottery_id=lottery, entries=entries)


class DetailClient(_BaseClient):
    """调用 40016 接口获取专家方案。"""

    def fetch(
        self,
        *,
        lottery_id: int,
        user_id: int,
        issue_name: Optional[str] = None,
    ) -> DetailResult:
        body = {
            "issueName": issue_name or "",
            "lotteryId": str(lottery_id),
            "recomTenantCode": "recom",
            "recomUserId": str(user_id),
        }
        payload = _build_payload("40016", body)
        response = self._post_with_failover(payload)
        data = response.json()
        if data.get("code") != 0:
            raise CollectorAPIError(f"方案接口返回异常: {data}")
        data_section = data.get("data") or {}
        issue = data_section.get("issueName") or issue_name or ""
        lottery = int(data_section.get("lotteryId", lottery_id))
        raw_list: Sequence[Dict[str, Any]] = data_section.get("schemeContentModelList") or []
        schemes: List[ExpertScheme] = []
        for item in raw_list:
            playtype_id = int(item.get("playtypeId", 0))
            playtype_name = item.get("playtypeName") or ""
            numbers: Any
            if item.get("dwNumberList"):
                numbers = [tuple(int(num) for num in sublist) for sublist in item["dwNumberList"]]
            elif item.get("numberList"):
                numbers = [int(num) for num in item["numberList"]]
            else:
                numbers = item.get("numbers") or ""
            schemes.append(
                ExpertScheme(
                    playtype_id=playtype_id,
                    playtype_name=playtype_name,
                    numbers=numbers,
                )
            )
        return DetailResult(issue_name=issue, lottery_id=lottery, schemes=schemes)
