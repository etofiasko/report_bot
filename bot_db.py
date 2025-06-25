import psycopg2
from config import DB_CONFIG, USERS_DB_CONFIG


def get_connection():
    conn = psycopg2.connect(**DB_CONFIG)
    return conn


def get_regions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT r.name
        FROM regions r
        JOIN data d ON r.id = d.region_id
        ORDER BY r.name;
    """)
    regions = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return regions


def get_partners():
    conn = get_connection()
    cursor = conn.cursor()

    partners = ["весь мир"]   
    
    cursor.execute("""
        SELECT name
        FROM country_groups
        WHERE parent_id IS NOT NULL
        AND name <> 'весь мир'
        ORDER BY name
    """)
    partners.extend(row[0] for row in cursor.fetchall())

    cursor.execute("""
        SELECT DISTINCT c.name_ru
        FROM data d
        JOIN countries c ON d.country_id = c.id
        WHERE d.region_id = 1
        ORDER BY c.name_ru
    """)
    partners.extend(row[0] for row in cursor.fetchall())

    cursor.close()
    conn.close()
    return partners


def get_years():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT year
        FROM data
        WHERE year > (
            SELECT MIN(year)
            FROM data)
        ORDER BY year;
    """,)
    years = [str(row[0]) for row in cursor.fetchall()]

    cursor.close()
    conn.close()
    return years


def get_categories():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM public.tn_ved_categories where parent_id is null;
    """)
    categories = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return categories


def get_subcategories(parent_name: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sc.name
        FROM tn_ved_categories p
        JOIN tn_ved_categories sc ON sc.parent_id = p.id
        WHERE p.name = %s
        ORDER BY sc.name;
    """, (parent_name,))
    subcategories = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return subcategories


def get_users_connection():
    return psycopg2.connect(**USERS_DB_CONFIG)


def setup_users_tables():
    conn = get_users_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE,
            username TEXT,
            role TEXT CHECK (role IN ('admin', 'user')) NOT NULL DEFAULT 'user'
        );
    """)
    conn.commit()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS download_history (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT,
            username TEXT,
            region TEXT,
            partner TEXT,
            year TEXT,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()

    cursor.close()
    conn.close()


def register_user(telegram_id, username):
    conn = get_users_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO users (telegram_id, username)
        VALUES (%s, %s)
        ON CONFLICT (telegram_id) DO UPDATE
            SET username = EXCLUDED.username;
    """, (telegram_id, username))
    
    conn.commit()
    cursor.close()
    conn.close()


def get_user_role(telegram_id):
    conn = get_users_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role
        FROM users
        WHERE telegram_id = %s;
    """, (telegram_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else None


async def add_download_history(telegram_id, username, region, partner, year):
    if not username:
        username = f"user_{telegram_id}"

    conn = get_users_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO download_history (telegram_id, username, region, partner, year)
        VALUES (%s, %s, %s, %s, %s);
    """, (telegram_id, username, region, partner, year))
    conn.commit()
    cursor.close()
    conn.close()
