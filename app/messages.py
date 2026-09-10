# messages.py
# -*- coding: utf-8 -*-

from jinja2 import (Environment, PackageLoader, StrictUndefined,
                    TemplateNotFound)

from app.config import settings

_DEFAULT_LOCALE = "en"

# #UFB-0037
_env = Environment(
    loader=PackageLoader("app", "templates/messages"),
    autoescape=True,  # every template is ".html.j2", not ".html" — the
    # `select_autoescape()` default extension list wouldn't match it and
    # escaping would silently stay off.
    trim_blocks=True,
    lstrip_blocks=True,
    undefined=StrictUndefined,
)


# #UFB-0037
def _render(name: str, **context) -> str:
    """Renders `<locale>/<name>` (settings.MESSAGE_LOCALE), falling back to
    `en/<name>` if the configured locale has no matching template. Output is
    stripped of the trailing newline template files end with."""
    locale = settings.MESSAGE_LOCALE
    try:
        template = _env.get_template(f"{locale}/{name}")
    except TemplateNotFound:
        template = _env.get_template(f"{_DEFAULT_LOCALE}/{name}")
    return template.render(**context).strip()


# #UFB-0001, #UFB-0037
def start() -> str:
    return _render("start.html.j2")


# #UFB-0003, #UFB-0037
def no_url_prompt() -> str:
    return _render("no_url_prompt.html.j2")


# #UFB-0006, #UFB-0037
def invalid_url() -> str:
    return _render("invalid_url.html.j2")


# #UFB-0005, #UFB-0037
def shrug() -> str:
    return _render("shrug.html.j2")


# #UFB-0015, #UFB-0032, #UFB-0036, #UFB-0037
def download_result(watch_url: str, source_url: str) -> str:
    return _render(
        "download_result.html.j2", watch_url=watch_url, source_url=source_url
    )


# #UFB-0036, #UFB-0037
def too_large(body: str) -> str:
    return _render("too_large.html.j2", body=body)


# #UFB-0010, #UFB-0037
def domain_not_allowed(original_url: str) -> str:
    return _render("domain_not_allowed.html.j2", original_url=original_url)


# #UFB-0010, #UFB-0037
def domain_not_allowed_with_mirror(mirror_url: str, original_url: str) -> str:
    return _render(
        "domain_not_allowed_with_mirror.html.j2",
        mirror_url=mirror_url,
        original_url=original_url,
    )


# #UFB-0013, #UFB-0037
def download_failed_mirror(mirror_url: str, original_url: str) -> str:
    return _render(
        "download_failed_mirror.html.j2",
        mirror_url=mirror_url,
        original_url=original_url,
    )
