# Message Handling Flow

How an incoming Telegram message is routed through `app/bot.py`, and how a request to the
REST API (`app/api.py`) compares. Both paths converge on the same URL-processing logic —
see [`url-processing-flow.md`](./url-processing-flow.md) for what happens inside that box.

## Telegram bot: `handle_message`

```mermaid
flowchart TD
    A["Incoming Telegram message"] --> B{"Group/supergroup chat<br/>AND a reply to another message?"}

    B -- yes --> C{"Is it a reply to<br/>the bot's own message?"}
    C -- yes --> D["Reply with ¯\\_(ツ)_/¯<br/>and stop"]
    C -- no --> E

    B -- no --> E["Extract all http(s):// URLs<br/>from the message text"]

    E --> F{"Any URLs found?"}
    F -- no --> G{"Chat type?"}
    G -- "group / supergroup" --> H["Stay silent"]
    G -- "private" --> I["Reply: 'Please send<br/>a valid URL to process!'"]

    F -- yes --> J["For each URL found:"]
    J --> K["Validate as URLMessage<br/>(pydantic HttpUrl)"]
    K -- "invalid URL" --> L["Log warning, reply:<br/>'Invalid URL provided: ...'"]
    K -- "valid" --> M["process_url_request(url, is_group_chat)"]

    M --> N{"Result is None?"}
    N -- yes --> O["Stay silent for this URL<br/>(e.g. group chat, nothing to add)"]
    N -- no --> P["Reply with the result text<br/>(Markdown, may include links)"]
```

## REST API: `POST /process_url/`

```mermaid
flowchart TD
    A["POST /process_url/<br/>JSON body: { url: string }"] --> B["Parse into URLRequest<br/>(no URL-format validation!)"]
    B --> C["process_url_request(url)<br/>is_group_chat defaults to False"]
    C --> D{"Raised an exception?"}
    D -- yes --> E["HTTP 400<br/>{ detail: str(exception) }"]
    D -- no --> F["HTTP 200<br/>{ status: success, data: result }"]
```

## Notes on the two entry points

- The bot path always validates the URL shape first (`URLMessage.url: HttpUrl`) and knows
  whether the chat is a group, which lets `process_url_request` stay silent in groups when
  there is nothing useful to add.
- The API path skips URL validation (`URLRequest.url: str`) and always behaves as if
  `is_group_chat=False`, so it never returns a silent/empty result — see
  [`BUGS.md` #12](../BUGS.md#12-unauthenticated-api-is-an-ssrf-capable-open-proxy-lowcontextual)
  for the security implication of that gap.
- Both paths call the exact same `process_url_request()` function — the "brain" of the bot is
  shared, only the transport and pre-validation differ.
