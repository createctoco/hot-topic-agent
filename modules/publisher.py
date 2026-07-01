"""Reliable wrapper around the toutiao-ops CLI."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).parent.parent


class ToutiaoPublisher:
    """Run toutiao-ops and accept only structured, confirmed results."""

    def __init__(self, work_dir: str = ".", validate_environment: bool = True):
        self.work_dir = Path(work_dir).resolve()
        self.node_binary = os.environ.get("TOUTIAO_NODE_BINARY") or shutil.which("node")
        override = os.environ.get("TOUTIAO_OPS_INDEX")
        self.index_js = (
            Path(override).expanduser().resolve()
            if override
            else self.work_dir
            / "node_modules"
            / "@openclaw-cn"
            / "toutiao-ops"
            / "index.js"
        )
        self._supported_opts: set[str] | None = None
        self._help_output = ""
        if validate_environment:
            self._check_environment()

    def _check_environment(self) -> None:
        if not self.node_binary:
            raise RuntimeError(
                "Node.js was not found. Install Node.js 20+ or set TOUTIAO_NODE_BINARY."
            )
        if not self.index_js.is_file():
            raise RuntimeError(
                "toutiao-ops is not installed. Run `npm install` in the project directory; "
                f"expected {self.index_js}."
            )
        result = subprocess.run(
            [self.node_binary, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "Node.js failed to start.")
        logger.info("Node.js: %s", result.stdout.strip())

    @staticmethod
    def _extract_last_json(output: str) -> dict[str, Any] | None:
        decoder = json.JSONDecoder()
        objects: list[tuple[int, int, dict[str, Any]]] = []
        for match in re.finditer(r"\{", output):
            try:
                value, length = decoder.raw_decode(output[match.start() :])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                objects.append((match.start(), match.start() + length, value))
        if not objects:
            return None
        # Prefer the object ending latest in the stream. If nested objects share
        # the same end position, select the earliest start (the outer object).
        _, _, value = max(objects, key=lambda item: (item[1], -item[0]))
        return value

    @staticmethod
    def _error_message(payload: dict[str, Any] | None, output: str) -> str:
        if payload:
            for key in ("error", "message", "reason"):
                value = payload.get(key)
                if value:
                    return str(value)
        return output.strip() or "toutiao-ops returned no diagnostic output."

    def _run_toutiao_cmd(self, args: list[str], timeout: int = 120) -> dict[str, Any]:
        if not self.node_binary or not self.index_js.is_file():
            return {
                "success": False,
                "returncode": None,
                "message": f"toutiao-ops is unavailable: {self.index_js}",
                "output": "",
                "data": None,
            }

        cmd = [self.node_binary, str(self.index_js), *args]
        logger.info("Running toutiao-ops: %s", " ".join(args[:3]))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=self.work_dir,
                env={**os.environ, "NO_COLOR": "1"},
            )
        except subprocess.TimeoutExpired as exc:
            partial = "".join(
                part.decode("utf-8", "replace") if isinstance(part, bytes) else (part or "")
                for part in (exc.stdout, exc.stderr)
            )
            return {
                "success": False,
                "returncode": None,
                "message": f"toutiao-ops timed out after {timeout} seconds.",
                "output": partial,
                "data": None,
            }
        except OSError as exc:
            return {
                "success": False,
                "returncode": None,
                "message": str(exc),
                "output": "",
                "data": None,
            }

        output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        payload = self._extract_last_json(output)
        success = result.returncode == 0 and not (payload and payload.get("error"))
        return {
            "success": success,
            "returncode": result.returncode,
            "message": "toutiao-ops completed." if success else self._error_message(payload, output),
            "output": output,
            "data": payload,
        }

    def _get_supported_options(self) -> set[str]:
        if self._supported_opts is not None:
            return self._supported_opts
        result = self._run_toutiao_cmd(["publish", "article", "--help"], timeout=30)
        self._help_output = result.get("output", "")
        self._supported_opts = set(
            re.findall(r"--([a-zA-Z][\w-]*)", self._help_output)
        )
        if not result["success"] or not {"title", "content-file"}.issubset(
            self._supported_opts
        ):
            raise RuntimeError(
                "Unable to read compatible `publish article --help` output. "
                + result.get("message", "")
            )
        return self._supported_opts

    def check_login(self) -> bool:
        args = ["auth", "check"]
        if os.environ.get("NON_INTERACTIVE") or os.environ.get("CI"):
            args.append("--headless")
        result = self._run_toutiao_cmd(args, timeout=90)
        payload = result.get("data") or {}
        logged_in = result["success"] and payload.get("logged_in") is True
        if not logged_in:
            logger.error("Toutiao login check failed: %s", result.get("message"))
        return logged_in

    def login(self) -> dict[str, Any]:
        return self._run_toutiao_cmd(["auth", "login"], timeout=360)

    def publish_article(
        self,
        title: str,
        content: str,
        category: str = "",
        first_publish: bool = True,
        ai_declared: bool = True,
        cover_keyword: str = "",
    ) -> dict[str, Any]:
        opts = self._get_supported_options()
        content_file = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".html", delete=False
            ) as handle:
                handle.write(content)
                content_file = handle.name

            args = [
                "publish",
                "article",
                "--title",
                title,
                "--content-file",
                content_file,
            ]
            if "format" in opts:
                args += ["--format", "markdown"]

            cover_path = os.environ.get("TOUTIAO_COVER_PATH", "").strip()
            if cover_path:
                if not Path(cover_path).is_file():
                    return {"success": False, "message": f"Cover image not found: {cover_path}"}
                args += ["--cover", str(Path(cover_path).resolve())]
                if "cover-mode" in opts:
                    args += ["--cover-mode", "single"]
            elif "cover-mode" in opts:
                # Toutiao removed the free-library tab from some publisher UI
                # variants. No-cover mode is the only deterministic fallback.
                args += ["--cover-mode", "none"]
            elif "cover-free" in opts:
                args.append("--cover-free")
                if "cover-keyword" in opts:
                    args += ["--cover-keyword", cover_keyword or title[:8]]
            else:
                return {
                    "success": False,
                    "message": (
                        "This toutiao-ops build requires a real cover image. Set "
                        "TOUTIAO_COVER_PATH or run `npm install` so the bundled compatibility "
                        "patch enables --cover-free."
                    ),
                }

            if first_publish and "first-publish" in opts:
                args.append("--first-publish")
            if ai_declared and "declaration" in opts:
                args += ["--declaration", "引用AI"]
            if (os.environ.get("NON_INTERACTIVE") or os.environ.get("CI")) and "headless" in opts:
                args.append("--headless")

            logger.info("Publishing Toutiao article: [%s] %s", category, title)
            result = self._run_toutiao_cmd(args, timeout=240)
            payload = result.get("data") or {}
            confirmed = (
                result["success"]
                and payload.get("success") is True
                and payload.get("action") == "published"
            )
            result["success"] = confirmed
            if confirmed:
                result["url"] = payload.get("url", "")
                result["message"] = "Toutiao confirmed the article was published."
            else:
                result["message"] = self._error_message(payload, result.get("output", ""))
            return result
        finally:
            if content_file:
                try:
                    Path(content_file).unlink(missing_ok=True)
                except OSError:
                    logger.warning("Could not remove temporary article file: %s", content_file)
