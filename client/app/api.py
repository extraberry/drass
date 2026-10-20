"""HTTP client for the ResearchVault server. The desktop client never talks to MySQL."""
import os
from typing import Callable, Optional
import requests


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 0, fields: Optional[dict] = None):
        super().__init__(message)
        self.code, self.message, self.status, self.fields = code, message, status, fields or {}


FRIENDLY = {"SESSION_EXPIRED": "Session expired.\nPlease log in again.",
            "DATABASE_UNAVAILABLE": "The database is currently unavailable. Please try again shortly.",
            "INTERNAL_ERROR": "Something went wrong on the server. Please try again or contact the administrator."}


class ApiClient:
    def __init__(self, base_url: Optional[str] = None):
        self.base = (base_url or os.environ.get("DRASS_SERVER_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.token: Optional[str] = None
        self.user: Optional[dict] = None
        self.http = requests.Session()

    @property
    def role(self) -> str:
        return (self.user or {}).get("role", "")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _raise(self, r: requests.Response) -> None:
        try:
            body = r.json()
            code, msg, fields = body.get("error_code", "HTTP_ERROR"), body.get("message", ""), body.get("fields")
        except ValueError:
            code, msg, fields = "HTTP_ERROR", "", None
        raise ApiError(code, FRIENDLY.get(code) or msg or f"The server returned an error ({r.status_code}).", r.status_code, fields)

    PUBLIC_PREFIXES = ("/lookups", "/repository", "/search/semantic", "/recommendations")

    def request(self, method: str, path: str, **kw):
        if not self.token:                                  # guest: use the unauthenticated, read-only endpoints
            for pre in self.PUBLIC_PREFIXES:
                if path == pre or path.startswith(pre + "/"):
                    path = "/public" + path
                    break
        kw.setdefault("timeout", 30)
        kw["headers"] = {**self._headers(), **kw.get("headers", {})}
        try:
            r = self.http.request(method, self.base + path, **kw)
        except requests.exceptions.ConnectionError:
            raise ApiError("SERVER_UNREACHABLE", "Cannot reach the ResearchVault server. Check that it is running and that you are on the campus network.")
        except requests.exceptions.Timeout:
            raise ApiError("TIMEOUT", "The server took too long to respond. Please try again.")
        if r.status_code >= 400:
            self._raise(r)
        return r

    def get(self, path, **params):
        return self.request("GET", path, params={k: v for k, v in params.items() if v not in (None, "")}).json()

    def post(self, path, json=None):
        return self.request("POST", path, json=json if json is not None else {}).json()

    def patch(self, path, json):
        return self.request("PATCH", path, json=json).json()

    def put(self, path, json):
        return self.request("PUT", path, json=json).json()

    # ---- auth ----
    def login(self, username: str, password: str) -> dict:
        data = self.request("POST", "/auth/login", json={"username": username, "password": password}).json()
        self.token, self.user = data["token"], data["user"]
        return self.user

    def enter_guest(self) -> None:
        self.token = None
        self.user = {"user_id": None, "username": "guest", "full_name": "Guest visitor", "role": "GUEST", "email": ""}

    def register_student(self, body: dict) -> dict:
        return self.request("POST", "/auth/register-student", json=body).json()

    def logout(self) -> None:
        try:
            if self.token:
                self.request("POST", "/auth/logout", json={})
        except ApiError:
            pass
        self.token = self.user = None

    # ---- binary ----
    def page_image(self, work_id: int, page: int, scale: float) -> tuple[bytes, dict]:
        r = self.request("GET", f"/reader/{work_id}/pages/{page}", params={"scale": scale})
        meta = {"page_count": int(r.headers["X-Page-Count"]), "page_width": float(r.headers["X-Page-Width"]),
                "page_height": float(r.headers["X-Page-Height"])}
        return r.content, meta

    def report_csv(self, kind: str, params: dict) -> bytes:
        return self.request("GET", f"/reports/{kind}", params={**params, "format": "csv"}).content

    def upload(self, work_id: int, file_type: str, path: str, progress: Optional[Callable[[int], None]] = None) -> dict:
        """Stream a file with a real Content-Length (a generator + Content-Length header breaks the request)."""
        reader = _ProgressReader(path, progress)
        try:
            return self.request("PUT", f"/submissions/{work_id}/files/{file_type}", params={"filename": os.path.basename(path)},
                                data=reader, headers={"Content-Type": "application/octet-stream"}, timeout=3600).json()
        finally:
            reader.close()


class _ProgressReader:
    """File-like body with __len__ so `requests` sets Content-Length and streams it in blocks."""
    def __init__(self, path: str, cb: Optional[Callable[[int], None]] = None):
        self.size = os.path.getsize(path)
        self.f, self.cb, self.sent = open(path, "rb"), cb, 0

    def __len__(self) -> int:
        return self.size

    def read(self, n: int = -1) -> bytes:
        b = self.f.read(n)
        self.sent += len(b)
        if self.cb and b:
            self.cb(int(self.sent * 100 / max(self.size, 1)))
        return b

    def close(self) -> None:
        self.f.close()
