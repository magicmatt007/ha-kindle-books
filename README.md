# Kindle Books for Home Assistant

A Home Assistant custom integration that shows the book you're **currently reading** on your Kindle and the books you've **finished**.

## How it works

Amazon doesn't offer a public API for Kindle reading data. Kindle can sync your reading to **Goodreads**, which Amazon owns, and every Goodreads shelf has a public RSS feed. This integration reads that feed:

```
Kindle ──(built-in Goodreads sync)──▶ Goodreads shelves ──(RSS)──▶ Home Assistant
```

You don't need an Amazon password, cookies or scraping.

## Setup

### 1. Connect your Kindle to Goodreads

On your Kindle, go to **Settings → Your Account → Social Networks → Goodreads** and sign in. (The Kindle app on iOS and Android has the same option.)

When you open a new book, Kindle offers to mark it as *Currently reading*. When you reach the end, it offers to mark it as *Read* and ask for a rating. Accept these prompts and your shelves stay up to date. You can also fix shelves by hand on goodreads.com.

### 2. Make your shelves visible

On Goodreads, go to **Account settings → Privacy** and set *Who can view my profile* to **anyone** (including non-Goodreads members). Private profiles don't publish the RSS feed.

### 3. Find your Goodreads user ID

Open your Goodreads profile. The URL looks like `https://www.goodreads.com/user/show/12345678-matt`, and the number is your ID. When you set up the integration, you can paste either the number or the whole URL.

### 4. Install the integration

**HACS (recommended):** HACS → ⋮ → *Custom repositories* → add `https://github.com/magicmatt007/ha-kindle-books` as an *Integration*. Then install **Kindle Books** and restart Home Assistant.

**Manual:** copy `custom_components/kindle_books` into your `config/custom_components/` folder and restart.

Then go to **Settings → Devices & services → Add integration → Kindle Books**.

## Entities

| Entity | State | Attributes |
| --- | --- | --- |
| `sensor.kindle_books_currently_reading` | Title of the book you started most recently | `author`, `cover`, `pages`, `added_at`, `link`, … plus `books` (every book on the shelf, if you read several at once). The entity picture is the cover. |
| `sensor.kindle_books_last_finished` | Title of the book you finished most recently | `author`, `cover`, `read_at`, `user_rating`, … |
| `sensor.kindle_books_books_read` | Total number of finished books | `books`: your most recent finished books (20 by default) |
| `sensor.kindle_books_books_read_this_year` | Number of books finished this calendar year | `books` |

## Options

Open **Configure** on the integration to change:

- **Shelf names:** use these if you track Kindle books on a custom shelf such as `kindle`.
- **Update interval:** default 60 minutes, minimum 15.
- **Books listed in attributes:** default 20.

## Dashboard example

```yaml
type: vertical-stack
cards:
  - type: markdown
    content: >
      {% set b = states.sensor.kindle_books_currently_reading %}
      {% if b.state not in ['unknown', 'unavailable'] %}
      <img src="{{ b.attributes.cover }}" width="100" align="left" style="margin-right:12px">

      ## 📖 {{ b.state }}

      *{{ b.attributes.author }}*
      {% else %}
      Not reading anything right now.
      {% endif %}
  - type: markdown
    title: Recently finished
    content: >
      {% for b in state_attr('sensor.kindle_books_books_read', 'books')[:10] %}
      - **{{ b.title }}** — {{ b.author }}{% if b.user_rating %} {{ '⭐' * b.user_rating }}{% endif %}
      {% endfor %}
```

## Development

```bash
pip install -r requirements_test.txt
pytest
```

## Limitations

- The data comes from Goodreads, so a book appears only after it reaches your Goodreads shelves. Kindle sync is fairly reliable, but some books are missing: sideloaded books, and books that aren't in the Goodreads catalogue.
- Goodreads doesn't publish reading progress (percent read), so the integration can't show it.
