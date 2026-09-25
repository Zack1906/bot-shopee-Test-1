import os
import requests
import feedparser
import time
import tweepy
import google.generativeai as genai
from supabase import create_client, Client

# --- 1. INISIALISASI KUNCI AKSES (ENVIRONMENT VARIABLES) ---
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")

# X API Keys
X_API_KEY = os.environ.get("X_API_KEY")
X_API_SECRET = os.environ.get("X_API_SECRET")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.environ.get("X_ACCESS_SECRET")

ai_model = None
supabase: Client | None = None
client_x = None
api_x_v1 = None


def initialize_services():
    """Initialize external services only after configuration is available."""
    global ai_model, supabase, client_x, api_x_v1

    required_keys = {
        "GEMINI_API_KEY": GEMINI_KEY,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "X_API_KEY": X_API_KEY,
        "X_API_SECRET": X_API_SECRET,
        "X_ACCESS_TOKEN": X_ACCESS_TOKEN,
        "X_ACCESS_SECRET": X_ACCESS_SECRET,
    }
    missing_keys = [name for name, value in required_keys.items() if not value]
    if missing_keys:
        raise RuntimeError(
            "Environment variable belum diatur: " + ", ".join(missing_keys)
        )

    genai.configure(api_key=GEMINI_KEY)
    ai_model = genai.GenerativeModel("gemini-1.5-flash")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    client_x = tweepy.Client(
        consumer_key=X_API_KEY, consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN, access_token_secret=X_ACCESS_SECRET
    )
    auth = tweepy.OAuth1UserHandler(
        X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
    )
    api_x_v1 = tweepy.API(auth)

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=15).raise_for_status()
    except requests.RequestException as error:
        print(f"Telegram gagal mengirim pesan: {error}")

def get_free_image(query):
    # Mengambil gambar gratis & aman hak cipta via Unsplash API
    if not UNSPLASH_ACCESS_KEY:
        return None

    url = f"https://api.unsplash.com/photos/random?query={query}&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        image_url = response.json().get("urls", {}).get("regular")
        if image_url:
            image_response = requests.get(image_url, timeout=30)
            image_response.raise_for_status()
            with open("temp.jpg", "wb") as image_file:
                image_file.write(image_response.content)
            return "temp.jpg"
    except (requests.RequestException, ValueError):
        return None
    return None

def fetch_affiliate_product():
    if supabase is None:
        raise RuntimeError("Supabase belum diinisialisasi")

    # Mengambil 1 link affiliate dari Supabase dengan status READY
    response = supabase.table("affiliate_links").select("*").eq("status", "READY").limit(1).execute()
    data = response.data
    if data:
        return data[0]
    return None

def mark_product_posted(product_id):
    if supabase is None:
        raise RuntimeError("Supabase belum diinisialisasi")

    supabase.table("affiliate_links").update({"status": "POSTED"}).eq("id", product_id).execute()

def run_bot():
    try:
        initialize_services()

        # Cek Notifikasi Online
        send_telegram("🟢 **BOT STATUS: ONLINE**\nSedang memproses postingan baru...")

        # 1. Ambil Berita / Funfact via RSS Feed
        rss_url = "https://www.cnnindonesia.com/nasional/rss"
        rss_response = requests.get(rss_url, timeout=30)
        rss_response.raise_for_status()
        feed = feedparser.parse(rss_response.content)
        if not feed.entries:
            raise RuntimeError("RSS berita tidak memiliki artikel")
        item = feed.entries[0]
        title_berita = item.title
        summary_berita = item.summary

        # 2. Ambil Link Affiliate dari Database Supabase
        produk = fetch_affiliate_product()
        if not produk:
            send_telegram("⚠️ **Peringatan:** Stok Link Affiliate di Database Habis/Kosong!")
            return

        # 3. Generate Teks Hook Berita Gen-Z (Maksimal 250 karakter untuk X)
        prompt_hook = f"""
        Ubah berita ini menjadi Tweet Hook gaya Gen-Z Indonesia yang bikin penasaran, lucu, atau kaget.
        Sertakan 2 hashtag populer di akhir. 
        Maksimal panjang teks 240 karakter!
        Berita: {title_berita} - {summary_berita}
        """
        hook_text = ai_model.generate_content(prompt_hook).text.strip()

        # 4. Generate Reply Penjelasan Berita
        prompt_reply_info = f"Buat ringkasan penjelasan dari berita '{title_berita}' dalam 150 karakter gaya santai santuy."
        info_reply_text = ai_model.generate_content(prompt_reply_info).text.strip()

        # 5. Eksekusi Upload Foto + Post Utama di X
        img_path = get_free_image("indonesia news")
        if img_path:
            media = api_x_v1.media_upload(img_path)
            post_1 = client_x.create_tweet(text=hook_text, media_ids=[media.media_id])
        else:
            post_1 = client_x.create_tweet(text=hook_text)
        
        tweet_id = post_1.data['id']
        time.sleep(15) # Delay alami layaknya manusia

        # 6. Reply 1: Penjelasan Berita
        reply_1 = client_x.create_tweet(text=info_reply_text, in_reply_to_tweet_id=tweet_id)
        time.sleep(20)

        # 7. Reply 2: Link Affiliate Produk yang Berbeda-beda
        affiliate_text = f"Btw yang lagi nyari {produk['nama_produk']} promo murah cuma Rp{produk['harga']} (Terjual {produk['terjual']}), gas cek shopee mumpung ada diskon 👉 {produk['link_affiliate']}"
        client_x.create_tweet(text=affiliate_text, in_reply_to_tweet_id=reply_1.data['id'])

        # Update Status Produk di Supabase agar tidak terulang
        mark_product_posted(produk['id'])

        # Kirim Laporan ke Telegram HP
        send_telegram(f"✅ **Post Berhasil Dipublikasikan!**\n\n📌 **Produk:** {produk['nama_produk']}\n🔗 **Link:** {produk['link_affiliate']}\n\n🔴 **BOT STATUS: OFFLINE (Memasuki Mode Istirahat)**")

    except Exception as e:
        send_telegram(f"❌ **Error Bot:** {str(e)}")

if __name__ == "__main__":
    run_bot()