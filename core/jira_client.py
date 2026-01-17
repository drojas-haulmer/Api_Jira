# core/jira_client.py
print(">>> core/jira_client.py LOADED")

import time
import requests
from typing import List, Dict, Generator
from requests.auth import HTTPBasicAuth

DEFAULT_TIMEOUT = (10, 120)


class JiraClient:
    def __init__(
        self,
        *,
        url: str,
        user: str,
        token: str,
        logger,
        timeout: tuple | None = None,
    ):
        self.logger = logger
        self.url = url.rstrip("/")
        self.timeout = timeout or DEFAULT_TIMEOUT

        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(user, token)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        # ✅ ENDPOINT NUEVO CORRECTO
        self.search_jql_api = f"{self.url}/rest/api/3/search/jql"

        self.logger.info(
            "🧩 [jira] JiraClient init | url=%s | timeout=%s",
            self.url,
            self.timeout,
        )

    # ==========================================================
    # 📦 FETCH ISSUES POR PROJECT (API NUEVA search/jql)
    # ==========================================================
    def fetch_issues_by_project(
        self,
        *,
        project_key: str,
        jql: str,
        batch_size: int,
        stats: dict,
    ) -> Generator[List[dict], None, None]:

        self.logger.info("🧪 [jira] fetch_issues_by_project START")
        self.logger.info("🔎 [jira] JQL final:\n%s", jql)

        next_page_token = None

        while True:
            stats["api_requests"] += 1

            body = {
                "jql": jql,
                "maxResults": batch_size,
                "fields": ["*all"],
                "expand": "changelog",   # 🔥 STRING, no lista
            }

            if next_page_token:
                body["nextPageToken"] = next_page_token

            self.logger.info(
                "➡️ [jira] POST %s | nextPageToken=%s",
                self.search_jql_api,
                next_page_token,
            )

            r = self.session.post(
                self.search_jql_api,
                json=body,
                timeout=self.timeout,
            )

            self.logger.info("⬅️ [jira] status=%s", r.status_code)

            if r.status_code in (403, 429):
                wait = int(r.headers.get("Retry-After", 60))
                stats["rate_limit_events"] += 1
                stats["rate_limit_wait_seconds"] += wait
                time.sleep(wait)
                continue

            if r.status_code != 200:
                self.logger.error("🔥 [jira] RESPONSE: %s", r.text)
                r.raise_for_status()

            data = r.json()
            issues = data.get("issues", [])

            if not issues:
                self.logger.info("📭 [jira] No more issues")
                break

            yield issues

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                self.logger.info("🚫 [jira] No nextPageToken → END")
                break
