# bot-shopee-Test-1

## Menjalankan bot

Gunakan Python dari virtual environment proyek:

```bash
./.venv/bin/python bot_engine.py
```

Atur environment variable berikut sebelum menjalankan bot:

`GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, dan `X_ACCESS_SECRET`.

`UNSPLASH_ACCESS_KEY` bersifat opsional. Tanpa key tersebut, bot tetap dapat mengirim posting tanpa gambar.

### Auto Post

```bash
.github
└── workflows
    └── auto_post.yml
```