import os, sqlite3, secrets
from functools import wraps
from datetime import datetime
from flask import Flask, g, render_template, request, redirect, url_for, session, flash, abort, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ICE_DB_PATH", os.path.join(APP_DIR, "ice_neighborhood.db"))
ADMIN_PASSWORD = os.environ.get("ICE_ADMIN_PASSWORD", "change-this-password")
SECRET_KEY = os.environ.get("ICE_SECRET_KEY", "change-this-secret-key-before-deploying")

app = Flask(__name__)
app.secret_key = SECRET_KEY

PRODUCT_CATEGORIES = ["바류", "콘류", "펜슬류", "샌드류", "컵류", "카톤류"]

AREAS = {
    "수원시": ["장안구", "권선구", "팔달구", "영통구"],
    "성남시": ["수정구", "중원구", "분당구"],
    "고양시": ["덕양구", "일산동구", "일산서구"],
    "용인시": ["처인구", "기흥구", "수지구"],
    "부천시": ["원미구", "소사구", "오정구"],
    "안산시": ["상록구", "단원구"],
    "안양시": ["만안구", "동안구"],
    "화성시": ["동탄구", "만세구", "효행구", "병점구"],
    "평택시": ["팽성읍", "비전동", "고덕동"],
    "의정부시": ["의정부동", "민락동", "가능동"],
    "남양주시": ["다산동", "별내동", "화도읍"],
    "파주시": ["운정동", "금촌동", "문산읍"],
    "김포시": ["장기동", "구래동", "풍무동"],
    "광주시": ["경안동", "태전동", "오포읍"],
    "하남시": ["미사동", "감일동", "덕풍동"],
    "시흥시": ["배곧동", "정왕동", "은행동"],
    "군포시": ["산본동", "금정동", "당동"],
    "오산시": ["세교동", "오산동", "원동"],
    "이천시": ["창전동", "증포동", "부발읍"],
    "구리시": ["갈매동", "인창동", "수택동"],
    "양주시": ["옥정동", "덕계동", "회천동"],
    "의왕시": ["내손동", "포일동", "오전동"],
    "안성시": ["공도읍", "아양동", "금산동"],
    "포천시": ["소흘읍", "포천동", "선단동"],
    "양평군": ["양평읍", "용문면"],
    "여주시": ["여흥동", "오학동"],
    "동두천시": ["생연동", "지행동"],
    "과천시": ["중앙동", "별양동"],
    "가평군": ["가평읍", "청평면"],
    "연천군": ["전곡읍", "연천읍"]
}

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS stores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        city TEXT NOT NULL,
        district TEXT NOT NULL,
        neighborhood TEXT NOT NULL,
        address TEXT NOT NULL,
        phone TEXT DEFAULT '',
        delivery_fee INTEGER NOT NULL DEFAULT 2500,
        min_order INTEGER NOT NULL DEFAULT 10000,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        category TEXT NOT NULL DEFAULT '바류',
        price INTEGER NOT NULL CHECK(price >= 0),
        cost_price INTEGER NOT NULL DEFAULT 0 CHECK(cost_price >= 0),
        stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
        image_url TEXT DEFAULT '',
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_code TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        city TEXT NOT NULL,
        district TEXT NOT NULL,
        neighborhood TEXT NOT NULL,
        memo TEXT DEFAULT '',
        subtotal INTEGER NOT NULL,
        delivery_fee INTEGER NOT NULL,
        total INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT '주문접수',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
        product_id INTEGER NOT NULL REFERENCES products(id),
        product_name TEXT NOT NULL,
        unit_price INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        line_total INTEGER NOT NULL
    );
    """)
    # Safe schema migration for databases created by an earlier version.
    product_columns = {row[1] for row in conn.execute("PRAGMA table_info(products)").fetchall()}
    if "cost_price" not in product_columns:
        conn.execute("ALTER TABLE products ADD COLUMN cost_price INTEGER NOT NULL DEFAULT 0")
    if "category" not in product_columns:
        conn.execute("ALTER TABLE products ADD COLUMN category TEXT NOT NULL DEFAULT '바류'")
        # Existing products get a reasonable initial category based on their name/description.
        conn.execute("""UPDATE products SET category = CASE
            WHEN name LIKE '%펜슬%' OR description LIKE '%펜슬%' THEN '펜슬류'
            WHEN name LIKE '%샌드%' OR description LIKE '%샌드%' THEN '샌드류'
            WHEN name LIKE '%카톤%' OR description LIKE '%카톤%' THEN '카톤류'
            WHEN name LIKE '%컵%' OR description LIKE '%컵%' THEN '컵류'
            WHEN name LIKE '%콘%' OR description LIKE '%콘%' THEN '콘류'
            ELSE '바류' END""")
    count = conn.execute("SELECT COUNT(*) FROM stores").fetchone()[0]
    if count == 0:
        now = datetime.now().isoformat(timespec="seconds")
        cur = conn.execute("""INSERT INTO stores
            (name,city,district,neighborhood,address,phone,delivery_fee,min_order,active,created_at)
            VALUES (?,?,?,?,?,?,?,?,1,?)""",
            ("아이스동네 테스트 매장", "안산시", "단원구", "고잔동",
             "경기도 안산시 단원구 고잔동 (테스트 주소)", "031-000-0000", 2500, 8000, now))
        sid = cur.lastrowid
        sample = [
            ("바닐라 콘", "바닐라 아이스크림 콘", 1500, 40),
            ("초코바", "초콜릿 코팅 아이스크림", 1200, 50),
            ("멜론바", "시원한 멜론맛 아이스바", 1000, 35),
            ("패밀리 컵", "가족과 함께 먹는 아이스크림", 5500, 12),
            ("딸기 샌드", "딸기맛 아이스크림 샌드", 1800, 24),
        ]
        for name, desc, price, stock in sample:
            conn.execute("""INSERT INTO products
                (store_id,name,description,price,stock,active,created_at)
                VALUES (?,?,?,?,?,1,?)""", (sid,name,desc,price,stock,now))
    conn.commit()
    conn.close()

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login", next=request.path))
        return fn(*args, **kwargs)
    return wrapped

@app.context_processor
def inject_globals():
    return {"areas": AREAS, "product_categories": PRODUCT_CATEGORIES, "money": lambda n: f"{int(n):,}원"}

@app.route("/")
def index():
    city = request.args.get("city", "").strip()
    district = request.args.get("district", "").strip()
    neighborhood = request.args.get("neighborhood", "").strip()
    keyword = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sql = """SELECT p.*, s.name AS store_name, s.city, s.district, s.neighborhood,
             s.address AS store_address, s.delivery_fee, s.min_order
             FROM products p JOIN stores s ON p.store_id=s.id
             WHERE p.active=1 AND s.active=1 AND p.stock>0"""
    params = []
    if city:
        sql += " AND s.city=?"; params.append(city)
    if district:
        sql += " AND s.district=?"; params.append(district)
    if neighborhood:
        sql += " AND s.neighborhood LIKE ?"; params.append(f"%{neighborhood}%")
    if keyword:
        sql += " AND (p.name LIKE ? OR p.description LIKE ? OR s.name LIKE ?)"
        params.extend([f"%{keyword}%"]*3)
    if category in PRODUCT_CATEGORIES:
        sql += " AND p.category=?"
        params.append(category)
    sql += " ORDER BY s.city, s.district, s.neighborhood, p.name"
    products = db().execute(sql, params).fetchall()
    return render_template("index.html", products=products, selected={
        "city":city, "district":district, "neighborhood":neighborhood, "q":keyword, "category":category
    })

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        if len(username) < 4 or len(password) < 8 or not name or not phone:
            flash("아이디는 4자 이상, 비밀번호는 8자 이상이며 이름과 전화번호를 입력해 주세요.", "error")
            return render_template("signup.html")
        try:
            db().execute("INSERT INTO members (username,name,phone,password_hash,created_at) VALUES (?,?,?,?,?)",
                         (username, name, phone, generate_password_hash(password), datetime.now().isoformat(timespec="seconds")))
            db().commit()
        except sqlite3.IntegrityError:
            flash("이미 사용 중인 아이디입니다. 다른 아이디를 입력해 주세요.", "error")
            return render_template("signup.html")
        flash("회원가입이 완료되었습니다.", "success")
        return redirect(url_for("index"))
    return render_template("signup.html")

@app.route("/member/login", methods=["GET", "POST"])
def member_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        member = db().execute("SELECT id, username, name, password_hash FROM members WHERE username=?", (username,)).fetchone()
        if member and check_password_hash(member["password_hash"], password):
            session["member_id"] = member["id"]
            session["member_name"] = member["name"]
            flash("로그인되었습니다.", "success")
            return redirect(url_for("index"))
        flash("아이디 또는 비밀번호를 확인해 주세요.", "error")
    return render_template("member_login.html")

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = db().execute("""SELECT p.*,s.name store_name,s.city,s.district,s.neighborhood,
        s.address store_address,s.delivery_fee,s.min_order FROM products p
        JOIN stores s ON p.store_id=s.id WHERE p.id=? AND p.active=1 AND s.active=1""",
        (product_id,)).fetchone()
    if not product: abort(404)
    return render_template("product.html", product=product)

@app.route("/api/cart-details")
def cart_details():
    """Return current server-side names/prices for product IDs in the browser cart."""
    raw_ids = request.args.get("ids", "").strip()
    try:
        ids = list(dict.fromkeys(int(value) for value in raw_ids.split(",") if value.strip()))
        if not ids or len(ids) > 100 or any(value < 1 for value in ids):
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": "장바구니 상품 정보를 읽을 수 없습니다. 상품을 다시 담아 주세요."}), 400
    placeholders = ",".join("?" for _ in ids)
    rows = db().execute(f"""SELECT p.id, p.name, p.price, p.stock, p.active,
            s.id AS store_id, s.name AS store_name, s.delivery_fee, s.min_order, s.active AS store_active
        FROM products p JOIN stores s ON p.store_id=s.id
        WHERE p.id IN ({placeholders})""", ids).fetchall()
    products = []
    for row in rows:
        if row["active"] and row["store_active"]:
            products.append({"id": row["id"], "name": row["name"], "price": row["price"],
                "stock": row["stock"], "store_id": row["store_id"], "store_name": row["store_name"],
                "delivery_fee": row["delivery_fee"], "min_order": row["min_order"]})
    return jsonify({"products": products})


@app.route("/checkout", methods=["GET","POST"])
def checkout():
    if request.method == "GET":
        return render_template("checkout.html")
    name = request.form.get("name","").strip()
    phone = request.form.get("phone","").strip()
    address = request.form.get("address","").strip()
    city = request.form.get("city","").strip()
    district = request.form.get("district","").strip()
    neighborhood = request.form.get("neighborhood","").strip()
    memo = request.form.get("memo","").strip()
    raw = request.form.get("cart_json","").strip()
    if not all([name,phone,address,city,district,neighborhood,raw]):
        flash("필수 정보를 모두 입력하고 장바구니를 확인해 주세요.", "error")
        return redirect(url_for("checkout"))
    import json
    try:
        cart = json.loads(raw)
        if not isinstance(cart, dict) or not cart:
            raise ValueError()
        cart = {int(k): int(v) for k,v in cart.items() if int(v) > 0}
        if not cart or any(v > 99 for v in cart.values()):
            raise ValueError()
    except Exception:
        flash("장바구니 정보가 올바르지 않습니다. 상품을 다시 담아 주세요.", "error")
        return redirect(url_for("index"))
    conn = db()
    ids = list(cart.keys())
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(f"""SELECT p.*,s.delivery_fee,s.min_order,s.active store_active
        FROM products p JOIN stores s ON p.store_id=s.id
        WHERE p.id IN ({placeholders}) AND p.active=1 AND s.active=1""", ids).fetchall()
    by_id = {r["id"]:r for r in rows}
    if len(by_id) != len(cart):
        flash("판매가 중단된 상품이 포함되어 있습니다. 장바구니를 다시 확인해 주세요.", "error")
        return redirect(url_for("index"))
    store_ids = {r["store_id"] for r in rows}
    if len(store_ids) != 1:
        flash("한 번의 주문은 한 매장 상품만 가능합니다. 매장별로 주문해 주세요.", "error")
        return redirect(url_for("index"))
    subtotal = 0
    for pid, qty in cart.items():
        if pid not in by_id or by_id[pid]["stock"] < qty:
            flash("재고가 부족한 상품이 있습니다. 수량을 확인해 주세요.", "error")
            return redirect(url_for("index"))
        subtotal += by_id[pid]["price"] * qty
    store = rows[0]
    if subtotal < store["min_order"]:
        flash(f"최소 주문 금액은 {store['min_order']:,}원입니다.", "error")
        return redirect(url_for("checkout"))
    fee = store["delivery_fee"]
    total = subtotal + fee
    order_code = "ICE-" + secrets.token_hex(3).upper()
    now = datetime.now().isoformat(timespec="seconds")
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute("""INSERT INTO orders
            (order_code,customer_name,phone,address,city,district,neighborhood,memo,
             subtotal,delivery_fee,total,status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,'주문접수',?)""",
            (order_code,name,phone,address,city,district,neighborhood,memo,subtotal,fee,total,now))
        oid = cur.lastrowid
        for pid, qty in cart.items():
            p = by_id[pid]
            changed = conn.execute("UPDATE products SET stock=stock-? WHERE id=? AND stock>=?",
                                   (qty,pid,qty)).rowcount
            if changed != 1:
                raise ValueError("재고가 변경되었습니다. 다시 주문해 주세요.")
            conn.execute("""INSERT INTO order_items
                (order_id,product_id,product_name,unit_price,quantity,line_total)
                VALUES (?,?,?,?,?,?)""",
                (oid,pid,p["name"],p["price"],qty,p["price"]*qty))
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(str(e) if "재고가 변경" in str(e) else "주문 처리 중 문제가 발생했습니다. 다시 시도해 주세요.", "error")
        return redirect(url_for("checkout"))
    return render_template("order_success.html", code=order_code, total=total)

@app.route("/order-lookup", methods=["GET","POST"])
def order_lookup():
    order = None
    items = []
    if request.method == "POST":
        code = request.form.get("code","").strip().upper()
        phone = request.form.get("phone","").strip()
        order = db().execute("SELECT * FROM orders WHERE order_code=? AND phone=?", (code,phone)).fetchone()
        if order:
            items = db().execute("SELECT * FROM order_items WHERE order_id=?", (order["id"],)).fetchall()
        else:
            flash("주문번호와 전화번호를 확인해 주세요.", "error")
    return render_template("order_lookup.html", order=order, items=items)

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password","")
        if secrets.compare_digest(password, ADMIN_PASSWORD):
            session["admin"] = True
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("비밀번호가 올바르지 않습니다.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = db()
    stores = conn.execute("SELECT * FROM stores ORDER BY id DESC").fetchall()
    products = conn.execute("""SELECT p.*,s.name store_name FROM products p
        JOIN stores s ON s.id=p.store_id ORDER BY p.id DESC""").fetchall()
    orders = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 100").fetchall()
    stats = {
        "stores": conn.execute("SELECT COUNT(*) FROM stores WHERE active=1").fetchone()[0],
        "products": conn.execute("SELECT COUNT(*) FROM products WHERE active=1").fetchone()[0],
        "orders": conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
        "sales": conn.execute("SELECT COALESCE(SUM(subtotal),0) FROM orders WHERE status!='취소'").fetchone()[0],
        "delivery_fees": conn.execute("SELECT COALESCE(SUM(delivery_fee),0) FROM orders WHERE status!='취소'").fetchone()[0],
        "cost": conn.execute("SELECT COALESCE(SUM(oi.quantity*p.cost_price),0) FROM order_items oi JOIN products p ON p.id=oi.product_id JOIN orders o ON o.id=oi.order_id WHERE o.status!='취소'").fetchone()[0]
    }
    stats["gross_profit_estimate"] = stats["sales"] - stats["cost"]
    return render_template("admin.html", stores=stores, products=products, orders=orders, stats=stats,
                           statuses=["주문접수","상품준비중","배송중","배송완료","취소"])

@app.route("/admin/store", methods=["POST"])
@admin_required
def admin_store_add():
    f = request.form
    required = [f.get(k,"").strip() for k in ["name","city","district","neighborhood","address"]]
    if not all(required):
        flash("매장 필수 항목을 입력해 주세요.", "error")
        return redirect(url_for("admin_dashboard"))
    try:
        fee = max(0, int(f.get("delivery_fee","2500")))
        minimum = max(0, int(f.get("min_order","10000")))
    except ValueError:
        flash("배송비와 최소 주문 금액은 숫자로 입력해 주세요.", "error")
        return redirect(url_for("admin_dashboard"))
    db().execute("""INSERT INTO stores
        (name,city,district,neighborhood,address,phone,delivery_fee,min_order,active,created_at)
        VALUES (?,?,?,?,?,?,?,?,1,?)""",
        (*required, f.get("phone","").strip(), fee, minimum, datetime.now().isoformat(timespec="seconds")))
    db().commit()
    flash("판매처를 등록했습니다.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/product", methods=["POST"])
@admin_required
def admin_product_add():
    f = request.form
    try:
        store_id = int(f.get("store_id",""))
        price = int(f.get("price",""))
        cost_price = int(f.get("cost_price", "0"))
        stock = int(f.get("stock",""))
    except ValueError:
        flash("매장, 가격, 재고를 확인해 주세요.", "error")
        return redirect(url_for("admin_dashboard"))
    name = f.get("name","").strip()
    category = f.get("category", "").strip()
    store = db().execute("SELECT id FROM stores WHERE id=? AND active=1",(store_id,)).fetchone()
    if not name or not store or category not in PRODUCT_CATEGORIES or price < 0 or cost_price < 0 or stock < 0:
        flash("상품 정보를 올바르게 입력해 주세요.", "error")
        return redirect(url_for("admin_dashboard"))
    db().execute("""INSERT INTO products
        (store_id,name,description,category,price,cost_price,stock,image_url,active,created_at)
        VALUES (?,?,?,?,?,?,?,'',1,?)""",
        (store_id,name,f.get("description","").strip(),category,price,cost_price,stock,datetime.now().isoformat(timespec="seconds")))
    db().commit()
    flash("상품을 등록했습니다.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/product/<int:pid>/update", methods=["POST"])
@admin_required
def admin_product_update(pid):
    f = request.form
    try:
        price, stock = int(f.get("price","")), int(f.get("stock",""))
        cost_price = int(f.get("cost_price", "0"))
    except ValueError:
        flash("가격과 재고는 숫자로 입력해 주세요.", "error")
        return redirect(url_for("admin_dashboard"))
    if price < 0 or stock < 0 or cost_price < 0:
        flash("원가·판매가·재고는 0 이상이어야 합니다.", "error")
    else:
        category = f.get("category", "").strip()
        if category not in PRODUCT_CATEGORIES:
            flash("상품 카테고리를 선택해 주세요.", "error")
            return redirect(url_for("admin_dashboard"))
        db().execute("UPDATE products SET price=?,cost_price=?,stock=?,category=?,active=? WHERE id=?",
                     (price,cost_price,stock,category,1 if f.get("active")=="on" else 0,pid))
        db().commit()
        flash("상품 정보를 수정했습니다.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/store/<int:sid>/toggle", methods=["POST"])
@admin_required
def admin_store_toggle(sid):
    db().execute("UPDATE stores SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?",(sid,))
    db().commit()
    flash("매장 상태를 변경했습니다.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/order/<int:oid>/status", methods=["POST"])
@admin_required
def admin_order_status(oid):
    status = request.form.get("status","")
    allowed = ["주문접수","상품준비중","배송중","배송완료","취소"]
    if status not in allowed:
        abort(400)
    conn = db()
    old = conn.execute("SELECT status FROM orders WHERE id=?",(oid,)).fetchone()
    if not old:
        abort(404)
    if old["status"] == "취소" and status != "취소":
        flash("취소된 주문은 이 화면에서 복구할 수 없습니다.", "error")
    elif old["status"] != "취소" and status == "취소":
        items = conn.execute("SELECT product_id,quantity FROM order_items WHERE order_id=?",(oid,)).fetchall()
        for item in items:
            conn.execute("UPDATE products SET stock=stock+? WHERE id=?",(item["quantity"],item["product_id"]))
        conn.execute("UPDATE orders SET status=? WHERE id=?",(status,oid))
        conn.commit()
        flash("주문을 취소하고 재고를 복구했습니다.", "success")
    else:
        conn.execute("UPDATE orders SET status=? WHERE id=?",(status,oid))
        conn.commit()
        flash("주문 상태를 변경했습니다.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/health")
def health():
    return {"status":"ok"}

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT","5000")), debug=False)
