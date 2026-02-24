# core/jira_client.py
import time
from typing import Generator, List

import requests
from requests.auth import HTTPBasicAuth

DEFAULT_TIMEOUT = (10, 120)
TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_RETRIES = 5


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

        # Prefer search/jql but keep robust fallback to /search.
        self.search_jql_api = f"{self.url}/rest/api/3/search/jql"
        self.search_api = f"{self.url}/rest/api/3/search"

        self.logger.info(
            "[jira] JiraClient init | url=%s | timeout=%s",
            self.url,
            self.timeout,
        )

    def _post_with_retries(
        self,
        *,
        url: str,
        body: dict,
        stats: dict,
        endpoint_name: str,
    ) -> requests.Response:
        last_response = None

        for attempt in range(1, MAX_RETRIES + 1):
            stats["api_requests"] += 1

            self.logger.info(
                "[jira] POST %s | endpoint=%s | attempt=%d/%d",
                url,
                endpoint_name,
                attempt,
                MAX_RETRIES,
            )

            response = self.session.post(
                url,
                json=body,
                timeout=self.timeout,
            )
            last_response = response

            self.logger.info("[jira] status=%s", response.status_code)

            if response.status_code == 200:
                return response

            if response.status_code in TRANSIENT_STATUS_CODES:
                if attempt > 1:
                    stats["api_retries_total"] += 1

                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait = int(retry_after)
                else:
                    wait = min(2 ** attempt, 60)

                if response.status_code == 429:
                    stats["rate_limit_events"] += 1
                    stats["rate_limit_wait_seconds"] += wait
                elif response.status_code >= 500:
                    stats["api_5xx_events"] += 1

                self.logger.warning(
                    "[jira] transient error %s in %s. Retrying in %ss",
                    response.status_code,
                    endpoint_name,
                    wait,
                )
                time.sleep(wait)
                continue

            self.logger.error("[jira] response body: %s", response.text)
            response.raise_for_status()

        self.logger.error(
            "[jira] retries exhausted in %s. Last status=%s",
            endpoint_name,
            last_response.status_code if last_response else "N/A",
        )
        if last_response is not None:
            self.logger.error("[jira] response body: %s", last_response.text)
            last_response.raise_for_status()
        raise RuntimeError(f"Jira request failed for {endpoint_name}")

    def _fetch_issues_search_jql(
        self,
        *,
        jql: str,
        batch_size: int,
        stats: dict,
    ) -> Generator[List[dict], None, None]:
        next_page_token = None

        while True:
            body = {
                "jql": jql,
                "maxResults": batch_size,
                "fields": ["*all"],
                "expand": "changelog",
            }
            if next_page_token:
                body["nextPageToken"] = next_page_token

            response = self._post_with_retries(
                url=self.search_jql_api,
                body=body,
                stats=stats,
                endpoint_name="search/jql",
            )

            data = response.json()
            issues = data.get("issues", [])
            if not issues:
                self.logger.info("[jira] no more issues (search/jql)")
                break

            yield issues

            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                self.logger.info("[jira] no nextPageToken, end")
                break

    def _fetch_issues_search(
        self,
        *,
        jql: str,
        batch_size: int,
        stats: dict,
    ) -> Generator[List[dict], None, None]:
        start_at = 0

        while True:
            body = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": batch_size,
                "fields": ["*all"],
                "expand": ["changelog"],
            }

            response = self._post_with_retries(
                url=self.search_api,
                body=body,
                stats=stats,
                endpoint_name="search",
            )

            data = response.json()
            issues = data.get("issues", [])
            total = data.get("total", 0)

            if not issues:
                self.logger.info("[jira] no more issues (search)")
                break

            yield issues

            start_at += len(issues)
            if start_at >= total:
                self.logger.info("[jira] pagination complete startAt=%s total=%s", start_at, total)
                break

    def fetch_issues_by_project(
        self,
        *,
        project_key: str,
        jql: str,
        batch_size: int,
        stats: dict,
    ) -> Generator[List[dict], None, None]:
        self.logger.info("[jira] fetch_issues_by_project start")
        self.logger.info("[jira] project=%s", project_key)
        self.logger.info("[jira] JQL final:\n%s", jql)

        try:
            yield from self._fetch_issues_search_jql(
                jql=jql,
                batch_size=batch_size,
                stats=stats,
            )
            return
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status not in {404, 500, 502, 503, 504}:
                raise
            self.logger.warning(
                "[jira] search/jql failed with status=%s, using fallback /search",
                status,
            )
            stats["fallback_to_search_used"] = 1

        yield from self._fetch_issues_search(
            jql=jql,
            batch_size=batch_size,
            stats=stats,
        )
