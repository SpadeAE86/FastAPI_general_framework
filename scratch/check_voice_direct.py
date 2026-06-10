import pymysql

def check_db(env, host, user, pwd, db):
    print(f"\n--- Checking {env} ---")
    try:
        conn = pymysql.connect(host=host, user=user, password=pwd, database=db, cursorclass=pymysql.cursors.DictCursor)
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, voice_character, voice_code FROM volcovoice_sample WHERE voice_character LIKE '%广州德哥%'")
            rows = cursor.fetchall()
            if not rows:
                print("❌ 没找到 '广州德哥'")
            else:
                for r in rows:
                    print(r)
        conn.close()
    except Exception as e:
        print(f"Error connecting to {env}: {e}")

check_db("test", "1.94.143.208", "freeu", "RootDev123", "ai_recommend_test")
check_db("prod", "1.94.143.208", "freeu_prod", "Prod~!@#189", "ai_recommend_prod")
