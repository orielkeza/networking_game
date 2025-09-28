import os, json, requests

BASE  = os.environ.get("SNOWFLAKE_BASE", "").rstrip("/")
TOKEN = os.environ.get("SNOWFLAKE_API_TOKEN", "")
MODEL = os.environ.get("SNOWFLAKE_MODEL", "mistral-large")

class SnowflakeError(RuntimeError):
    pass

def _assert_env():
    missing = []
    if not BASE:  missing.append("SNOWFLAKE_BASE")
    if not TOKEN: missing.append("SNOWFLAKE_API_TOKEN")
    if not MODEL: missing.append("SNOWFLAKE_MODEL")
    if missing:
        raise SnowflakeError(f"Missing env: {', '.join(missing)}")

def _post_json(url, payload):
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
    if r.status_code == 401:
        raise SnowflakeError("401 Unauthorized — invalid/expired token or wrong account.")
    if r.status_code == 403:
        raise SnowflakeError("403 Forbidden — permissions/network policy.")
    if r.status_code == 404:
        raise SnowflakeError("404 Not Found — endpoint path may differ for your account.")
    if r.status_code == 400:
        try:
            msg = r.json()
        except Exception:
            msg = r.text
        raise SnowflakeError(f"400 Bad Request — {msg}")
    if not r.ok:
        raise SnowflakeError(f"{r.status_code} {r.reason}: {r.text}")
    return r.json()

def sf_complete(prompt: str, max_tokens: int = 300) -> str:
    """
    Calls Snowflake Cortex inference:complete endpoint with a simple prompt.
    Returns the assistant text. Requires env vars: SNOWFLAKE_BASE, SNOWFLAKE_API_TOKEN, SNOWFLAKE_MODEL
    """
    _assert_env()
    url = f"{BASE}/api/v2/cortex/inference:complete"
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a concise, friendly networking writing assistant."},
            {"role": "user",   "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.4
    }
    data = _post_json(url, payload)

    # Normalize multiple possible response shapes
    txt = None
    if isinstance(data, dict):
        if isinstance(data.get("choices"), list) and data["choices"]:
            msg = data["choices"][0].get("message") or {}
            txt = msg.get("content")
        if not txt:
            txt = data.get("output")
        if not txt and isinstance(data.get("candidates"), list) and data["candidates"]:
            txt = data["candidates"][0].get("content")
    if not txt:
        raise SnowflakeError(f"Unexpected response: {data}")
    return txt.strip()