import os
import sys
import sqlite3
import datetime
import csv
import io
import json
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
import httpx
from wilayas_data import WILAYAS

# Initialize FastAPI
app = FastAPI(title="DZ COD Engine Pro", version="3.0.0")

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    STATIC_DIR = getattr(sys, '_MEIPASS', BASE_DIR)
    STATIC_DIR = os.path.join(STATIC_DIR, "static")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = os.path.join(BASE_DIR, "static")

# If static folder exists locally next to exe, prefer it for easy customization
local_static = os.path.join(BASE_DIR, "static")
if os.path.exists(local_static):
    STATIC_DIR = local_static

DB_PATH = os.path.join(BASE_DIR, "orders.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Orders table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            wilaya_code INTEGER NOT NULL,
            wilaya_name TEXT NOT NULL,
            commune TEXT NOT NULL,
            delivery_type TEXT NOT NULL,
            product_id INTEGER DEFAULT 1,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            product_price INTEGER NOT NULL,
            shipping_price INTEGER NOT NULL,
            total_price INTEGER NOT NULL,
            status TEXT DEFAULT 'nouveau',
            notes TEXT DEFAULT ''
        )
    """)
    
    # 2. Settings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # 3. Products table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subtitle TEXT DEFAULT '',
            image_url TEXT NOT NULL,
            price_1 INTEGER NOT NULL,
            price_2 INTEGER NOT NULL,
            price_3 INTEGER NOT NULL,
            original_price INTEGER DEFAULT 0,
            description TEXT DEFAULT '',
            is_active INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    
    # 4. Shipping rates table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shipping_rates (
            code INTEGER PRIMARY KEY,
            name_ar TEXT NOT NULL,
            name_fr TEXT NOT NULL,
            domicile INTEGER NOT NULL,
            stopdesk INTEGER NOT NULL,
            is_available INTEGER DEFAULT 1
        )
    """)

    # 5. Customer Reviews / Testimonials table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_name TEXT NOT NULL,
            wilaya_name TEXT NOT NULL,
            rating INTEGER DEFAULT 5,
            comment TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)
    
    # Default landing page & store settings
    default_settings = {
        "store_name": "DZ-SmartStore",
        "announcement_bar": "عرض خاص محدود: تخفيض استثنائي 40% + توصيل مجاني عند طلب قطعتين فما فوق!",
        "badge_1_title": "ضمان استبدال",
        "badge_1_desc": "7 أيام تجربة حقيقية",
        "badge_2_title": "دفع عند الاستلام",
        "badge_2_desc": "حتى تقلب وتتأكد",
        "badge_3_title": "توصيل سريع",
        "badge_3_desc": "من 24 إلى 48 ساعة",
        "badge_4_title": "بطارية جبارة",
        "badge_4_desc": "تدوم حتى 5 أيام",
        "features_heading": "علاش هذا المنتج هو الاختيار الأفضل ليك؟",
        "features_json": json.dumps([
            {"title": "شاشة AMOLED عملاقة", "desc": "وضوح فائق تحت أشعة الشمس مع ألوان زاهية ولمس فائق الحساسية."},
            {"title": "إجراء واستقبال المكالمات", "desc": "بميكروفون وسبيكر مدمجين عاليي النقاوة دون الحاجة لإخراج هاتفك."},
            {"title": "مراقبة الصحة والرياضة", "desc": "قياس نبضات القلب، ضغط الدم، الأكسجين، وحساب الخطوات والسعرات الحرارية بدقة."},
            {"title": "متوافقة مع جميع الهواتف", "desc": "تدعم Android و iPhone بسهولة وبشكل كامل باللغة العربية."}
        ], ensure_ascii=False),
        "countdown_enabled": "1",
        "countdown_text": "سارع قبل انتهاء المخزون، العرض الترويجي ينتهي خلال:",
        "countdown_hours": "4",
        "telegram_bot_token": "",
        "telegram_chat_id": ""
    }
    
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
        
    # Seed default product if empty
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO products (title, subtitle, image_url, price_1, price_2, price_3, original_price, description, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (
            "ساعة Ultra 9 الذكية الأصلية",
            "+ 3 أحزمة ألوان مختلفة وشاحن لاسلكي مجاناً!",
            "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&auto=format&fit=crop&q=80",
            4900,
            8900,
            12800,
            8200,
            "أحدث إصدار للساعات الذكية بتصميم فخم وإطار من التيتانيوم المقاوم للصدمات والماء، متوافقة مع كل الهواتف.",
            now
        ))
        
    # Seed shipping rates from WILAYAS if empty
    cursor.execute("SELECT COUNT(*) FROM shipping_rates")
    if cursor.fetchone()[0] == 0:
        for w in WILAYAS:
            cursor.execute("""
                INSERT INTO shipping_rates (code, name_ar, name_fr, domicile, stopdesk, is_available)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (w["code"], w["name_ar"], w["name_fr"], w["domicile"], w["stopdesk"]))

    # Seed default reviews if empty
    cursor.execute("SELECT COUNT(*) FROM reviews")
    if cursor.fetchone()[0] == 0:
        now = datetime.datetime.now().strftime("%Y-%m-%d")
        default_reviews = [
            ("أمين بلقاسم", "وهران", 5, "وصلتني في يومين لوهران، الساعة ماشاء الله جودة ممتازة والأحزمة لي جاو معاها زادو فيها النص. شكرا ليكم."),
            ("حسام عثماني", "الجزائر العاصمة", 5, "كومونديت زوج حبات ليا ولخويا وجاني التوصيل باطل، صوت المكالمات واضح والبطارية تشد مليح. بارك الله فيكم."),
            ("سفيان مداحي", "سطيف", 5, "التعامل قمة فالمصداقية، والموزع فتحلي العلبة شفتها وسيتها قبل ما نخلص. خدمة محترفة وتوصيل سريع.")
        ]
        for r in default_reviews:
            cursor.execute("""
                INSERT INTO reviews (author_name, wilaya_name, rating, comment, created_at, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (r[0], r[1], r[2], r[3], now))

    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==================== PYDANTIC MODELS ====================
class OrderCreate(BaseModel):
    customer_name: str
    customer_phone: str
    wilaya_code: int
    commune: str
    delivery_type: str
    quantity: int = 1
    product_id: Optional[int] = None

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None

class ProductModel(BaseModel):
    title: str
    subtitle: Optional[str] = ""
    image_url: str
    price_1: int
    price_2: int
    price_3: int
    original_price: Optional[int] = 0
    description: Optional[str] = ""

class WilayaRateUpdate(BaseModel):
    domicile: int
    stopdesk: int
    is_available: Optional[int] = 1

class BulkWilayaUpdate(BaseModel):
    domicile_flat: Optional[int] = None
    stopdesk_flat: Optional[int] = None

class ReviewCreate(BaseModel):
    author_name: str
    wilaya_name: str
    rating: int = 5
    comment: str

class LandingConfigUpdate(BaseModel):
    store_name: Optional[str] = None
    announcement_bar: Optional[str] = None
    badge_1_title: Optional[str] = None
    badge_1_desc: Optional[str] = None
    badge_2_title: Optional[str] = None
    badge_2_desc: Optional[str] = None
    badge_3_title: Optional[str] = None
    badge_3_desc: Optional[str] = None
    badge_4_title: Optional[str] = None
    badge_4_desc: Optional[str] = None
    features_heading: Optional[str] = None
    features_json: Optional[str] = None
    countdown_enabled: Optional[str] = None
    countdown_text: Optional[str] = None
    countdown_hours: Optional[str] = None

class SettingsUpdate(BaseModel):
    store_name: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

# Telegram Notification Sender
async def send_telegram_alert(order_data: dict, bot_token: str, chat_id: str):
    if not bot_token or not chat_id:
        return
    deliv_type_str = "توصيل للمنزل 🏠" if order_data["delivery_type"] == "domicile" else "استلام من المكتب (Stop Desk) 🏢"
    msg = (
        f"🚨 <b>طلب جديد وارد! (Commande #{order_data['id']})</b>\n\n"
        f"👤 <b>الزبون:</b> {order_data['customer_name']}\n"
        f"📞 <b>الهاتف:</b> <code>{order_data['customer_phone']}</code>\n"
        f"📍 <b>الولاية:</b> {order_data['wilaya_code']} - {order_data['wilaya_name']}\n"
        f"🏘 <b>البلدية/العنوان:</b> {order_data['commune']}\n"
        f"🚚 <b>نوع التوصيل:</b> {deliv_type_str}\n"
        f"📦 <b>المنتج:</b> {order_data['product_name']}\n"
        f"🔢 <b>الكمية:</b> {order_data['quantity']}\n"
        f"💰 <b>المبلغ الإجمالي:</b> <b>{order_data['total_price']:,} دج</b>\n\n"
        f"⚡ <i>تأكيد فوري: <a href='https://wa.me/213{order_data['customer_phone'].lstrip('0')}'>مراسلة عبر واتساب</a></i>"
    )
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})
    except Exception as e:
        print(f"Telegram notification failed: {e}")

# ==================== LANDING CONFIG API ====================

@app.get("/api/landing-config")
def get_landing_config():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    settings = {r["key"]: r["value"] for r in rows}
    
    # Parse features_json if present
    features = []
    try:
        features = json.loads(settings.get("features_json", "[]"))
    except:
        features = []
        
    return {
        "store_name": settings.get("store_name", "DZ-SmartStore"),
        "announcement_bar": settings.get("announcement_bar", ""),
        "badges": [
            {"title": settings.get("badge_1_title", "ضمان استبدال"), "desc": settings.get("badge_1_desc", "7 أيام تجربة")},
            {"title": settings.get("badge_2_title", "دفع عند الاستلام"), "desc": settings.get("badge_2_desc", "حتى تقلب وتتأكد")},
            {"title": settings.get("badge_3_title", "توصيل سريع"), "desc": settings.get("badge_3_desc", "من 24 إلى 48 ساعة")},
            {"title": settings.get("badge_4_title", "بطارية جبارة"), "desc": settings.get("badge_4_desc", "تدوم حتى 5 أيام")}
        ],
        "features_heading": settings.get("features_heading", "علاش هذا المنتج هو الاختيار الأفضل ليك؟"),
        "features": features,
        "countdown_enabled": settings.get("countdown_enabled", "1") == "1",
        "countdown_text": settings.get("countdown_text", "سارع قبل انتهاء المخزون، العرض الترويجي ينتهي خلال:"),
        "countdown_hours": int(settings.get("countdown_hours", "4"))
    }

@app.post("/api/landing-config")
def update_landing_config(config: LandingConfigUpdate):
    conn = get_db()
    cursor = conn.cursor()
    data = config.model_dump(exclude_unset=True)
    for k, v in data.items():
        if v is not None:
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
    conn.commit()
    conn.close()
    return {"message": "Landing config updated successfully"}

# ==================== REVIEWS / TESTIMONIALS API ====================

@app.get("/api/reviews")
def get_reviews():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reviews WHERE is_active = 1 ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/reviews")
def add_review(review: ReviewCreate):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        INSERT INTO reviews (author_name, wilaya_name, rating, comment, created_at, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
    """, (review.author_name, review.wilaya_name, review.rating, review.comment, now))
    r_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"message": "Review added successfully", "id": r_id}

@app.delete("/api/reviews/{review_id}")
def delete_review(review_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
    conn.commit()
    conn.close()
    return {"message": "Review deleted"}

# ==================== PRODUCTS API ====================

@app.get("/api/products")
def get_products():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products ORDER BY id DESC")
    products = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return products

@app.get("/api/products/active")
def get_active_product():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    if not row:
        cursor.execute("SELECT * FROM products ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="No products found")
    return dict(row)

@app.post("/api/products")
def create_product(product: ProductModel):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO products (title, subtitle, image_url, price_1, price_2, price_3, original_price, description, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (
        product.title, product.subtitle, product.image_url, product.price_1,
        product.price_2, product.price_3, product.original_price, product.description, now
    ))
    prod_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"message": "Product created successfully", "id": prod_id}

@app.put("/api/products/{prod_id}")
def update_product(prod_id: int, product: ProductModel):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE products SET
            title = ?, subtitle = ?, image_url = ?, price_1 = ?,
            price_2 = ?, price_3 = ?, original_price = ?, description = ?
        WHERE id = ?
    """, (
        product.title, product.subtitle, product.image_url, product.price_1,
        product.price_2, product.price_3, product.original_price, product.description, prod_id
    ))
    conn.commit()
    conn.close()
    return {"message": "Product updated"}

@app.post("/api/products/{prod_id}/activate")
def activate_product(prod_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET is_active = 0")
    cursor.execute("UPDATE products SET is_active = 1 WHERE id = ?", (prod_id,))
    conn.commit()
    conn.close()
    return {"message": "Product activated"}

@app.delete("/api/products/{prod_id}")
def delete_product(prod_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (prod_id,))
    conn.commit()
    conn.close()
    return {"message": "Product deleted"}

# ==================== WILAYAS / SHIPPING API ====================

@app.get("/api/wilayas")
def get_wilayas():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM shipping_rates ORDER BY code ASC")
    wilayas = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return wilayas

@app.put("/api/wilayas/{code}")
def update_wilaya_rate(code: int, update: WilayaRateUpdate):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE shipping_rates SET domicile = ?, stopdesk = ?, is_available = ? WHERE code = ?
    """, (update.domicile, update.stopdesk, update.is_available, code))
    conn.commit()
    conn.close()
    return {"message": "Wilaya shipping updated"}

@app.post("/api/wilayas/bulk")
def bulk_update_wilayas(update: BulkWilayaUpdate):
    conn = get_db()
    cursor = conn.cursor()
    if update.domicile_flat is not None:
        cursor.execute("UPDATE shipping_rates SET domicile = ?", (update.domicile_flat,))
    if update.stopdesk_flat is not None:
        cursor.execute("UPDATE shipping_rates SET stopdesk = ?", (update.stopdesk_flat,))
    conn.commit()
    conn.close()
    return {"message": "Bulk update completed"}

@app.post("/api/wilayas/reset")
def reset_wilayas():
    conn = get_db()
    cursor = conn.cursor()
    for w in WILAYAS:
        cursor.execute("""
            UPDATE shipping_rates SET domicile = ?, stopdesk = ?, is_available = 1 WHERE code = ?
        """, (w["domicile"], w["stopdesk"], w["code"]))
    conn.commit()
    conn.close()
    return {"message": "Wilayas reset to defaults"}

# ==================== ORDERS API ====================

@app.post("/api/orders")
async def create_order(order: OrderCreate):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM shipping_rates WHERE code = ? AND is_available = 1", (order.wilaya_code,))
    wilaya = cursor.fetchone()
    if not wilaya:
        conn.close()
        raise HTTPException(status_code=400, detail="الولاية المختارة غير متاحة للتوصيل حالياً")
        
    if order.product_id:
        cursor.execute("SELECT * FROM products WHERE id = ?", (order.product_id,))
    else:
        cursor.execute("SELECT * FROM products WHERE is_active = 1 LIMIT 1")
    product = cursor.fetchone()
    if not product:
        cursor.execute("SELECT * FROM products ORDER BY id DESC LIMIT 1")
        product = cursor.fetchone()
        
    product_title = product["title"] if product else "المنتج"
    prod_id = product["id"] if product else 1
    
    if order.quantity == 2:
        subtotal = product["price_2"]
        shipping_price = 0
    elif order.quantity == 3:
        subtotal = product["price_3"]
        shipping_price = 0
    else:
        subtotal = product["price_1"] * order.quantity
        shipping_price = wilaya["domicile"] if order.delivery_type == "domicile" else wilaya["stopdesk"]
        
    total_price = subtotal + shipping_price
    created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        INSERT INTO orders (
            created_at, customer_name, customer_phone, wilaya_code, wilaya_name,
            commune, delivery_type, product_id, product_name, quantity, product_price,
            shipping_price, total_price, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'nouveau')
    """, (
        created_at, order.customer_name, order.customer_phone, order.wilaya_code,
        wilaya["name_ar"], order.commune, order.delivery_type, prod_id, product_title,
        order.quantity, subtotal, shipping_price, total_price
    ))
    
    order_id = cursor.lastrowid
    
    cursor.execute("SELECT key, value FROM settings")
    settings = {row["key"]: row["value"] for row in cursor.fetchall()}
    conn.commit()
    conn.close()
    
    order_dict = {
        "id": order_id,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "wilaya_code": order.wilaya_code,
        "wilaya_name": wilaya["name_ar"],
        "commune": order.commune,
        "delivery_type": order.delivery_type,
        "product_name": product_title,
        "quantity": order.quantity,
        "total_price": total_price
    }
    
    bot_token = settings.get("telegram_bot_token", "")
    chat_id = settings.get("telegram_chat_id", "")
    if bot_token and chat_id:
        await send_telegram_alert(order_dict, bot_token, chat_id)
        
    return {
        "status": "success",
        "order_id": order_id,
        "message": "تم تسجيل طلبك بنجاح!",
        "order": order_dict
    }

@app.get("/api/orders")
def get_orders(status: Optional[str] = None, search: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
        
    if search:
        query += " AND (customer_name LIKE ? OR customer_phone LIKE ? OR wilaya_name LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])
        
    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.patch("/api/orders/{order_id}")
def update_order(order_id: int, update: OrderUpdate):
    conn = get_db()
    cursor = conn.cursor()
    fields = []
    params = []
    if update.status is not None:
        fields.append("status = ?")
        params.append(update.status)
    if update.notes is not None:
        fields.append("notes = ?")
        params.append(update.notes)
        
    if not fields:
        return {"message": "Nothing to update"}
        
    params.append(order_id)
    query = f"UPDATE orders SET {', '.join(fields)} WHERE id = ?"
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    return {"message": "Order updated"}

@app.delete("/api/orders/{order_id}")
def delete_order(order_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()
    return {"message": "Order deleted"}

@app.get("/api/stats")
def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total FROM orders")
    total = cursor.fetchone()["total"]
    
    cursor.execute("SELECT COUNT(*) as nouveau FROM orders WHERE status = 'nouveau'")
    nouveau = cursor.fetchone()["nouveau"]
    
    cursor.execute("SELECT COUNT(*) as confirme FROM orders WHERE status = 'confirme'")
    confirme = cursor.fetchone()["confirme"]
    
    cursor.execute("SELECT COUNT(*) as livre FROM orders WHERE status = 'livre'")
    livre = cursor.fetchone()["livre"]
    
    cursor.execute("SELECT COUNT(*) as annule FROM orders WHERE status = 'annule'")
    annule = cursor.fetchone()["annule"]
    
    cursor.execute("SELECT SUM(total_price) as revenue FROM orders WHERE status IN ('confirme', 'expedie', 'livre')")
    revenue_row = cursor.fetchone()
    revenue = revenue_row["revenue"] if revenue_row["revenue"] else 0
    
    confirmation_rate = round((confirme + livre) / total * 100, 1) if total > 0 else 0
    
    conn.close()
    return {
        "total_orders": total,
        "new_orders": nouveau,
        "confirmed_orders": confirme,
        "delivered_orders": livre,
        "cancelled_orders": annule,
        "total_revenue": revenue,
        "confirmation_rate": confirmation_rate
    }

@app.get("/api/settings")
def get_settings():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

@app.post("/api/settings")
def update_settings(settings: SettingsUpdate):
    conn = get_db()
    cursor = conn.cursor()
    update_data = settings.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if v is not None:
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
    conn.commit()
    conn.close()
    return {"message": "Settings updated"}

@app.get("/api/export-csv")
def export_csv():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY id DESC")
    orders = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Date", "Nom Client", "Téléphone", "Code Wilaya", "Wilaya",
        "Commune", "Type Livraison", "Produit", "Quantité", "Prix Total (DZD)", "Statut"
    ])
    for o in orders:
        writer.writerow([
            o["id"], o["created_at"], o["customer_name"], o["customer_phone"],
            o["wilaya_code"], o["wilaya_name"], o["commune"], o["delivery_type"],
            o["product_name"], o["quantity"], o["total_price"], o["status"]
        ])
        
    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=commandes_dz_export.csv"}
    )

# Static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_landing():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/admin")
def serve_admin():
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))

if __name__ == "__main__":
    import threading
    import webbrowser
    import time
    import uvicorn

    def open_browser():
        time.sleep(1.5)
        webbrowser.open("http://127.0.0.1:8000/admin")

    threading.Thread(target=open_browser, daemon=True).start()
    print("==================================================================")
    print("   خادم DZ COD Engine Pro يعمل الآن بنجاح على http://localhost:8000")
    print("   صفحة البيع:      http://localhost:8000/")
    print("   لوحة تحكم التاجر: http://localhost:8000/admin")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
