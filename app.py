# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, session, render_template, send_from_directory
import os
import pyodbc
from datetime import datetime
import traceback
import logging
from flask_cors import CORS
import hashlib
import json

app = Flask(__name__)
CORS(app)
app.secret_key = 'guilin_travel_secret_key'

# 静态资源路由（特色美食图片）
@app.route('/特色美食/<path:filename>')
def special_food_img(filename):
    return send_from_directory(os.path.join(app.root_path, 'static', '特色美食'), filename)

# 日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 数据库配置（按实际修改）
db_config = {
    'driver': '{ODBC Driver 17 for SQL Server}',
    'server': 'localhost',
    'database': 'guilin_travel',
    'uid': 'sa',
    'pwd': '040305',
    'autocommit': True
}

# 密码哈希
def generate_password_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(hashed_password, password):
    return hashlib.sha256(password.encode()).hexdigest() == hashed_password

# 获取数据库连接
def get_db_connection():
    try:
        return pyodbc.connect(**db_config)
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return jsonify({'success': False, 'message': '数据库连接错误'}), 500

# --------------------------------------------------
# 首页
@app.route('/')
def index():
    return render_template('index.html')

# --------------------------------------------------
# 注册
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        phone = data.get('phone')
        name = data.get('name')
        password = data.get('password')
        nickname = data.get('nickname', '用户')
        gender = data.get('gender', '男')
        birthdate = data.get('birthdate')
        if not phone or not password or not name:
            return jsonify({'success': False, 'message': '手机号、密码、姓名不能为空'}), 400
        if len(password) < 6:
            return jsonify({'success': False, 'message': '密码至少6位'}), 400
        conn = get_db_connection()
        if isinstance(conn, tuple):
            return conn
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM user_info WHERE phone_number=?", phone)
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'message': '手机号已注册'}), 400
        birthdate_obj = datetime.strptime(birthdate, '%Y-%m-%d').date() if birthdate else None
        hashed = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO user_info (phone_number, name, password, nickname, gender, birthdate, register_time) VALUES (?,?,?,?,?,?,?)",
            phone, name, hashed, nickname, gender, birthdate_obj, datetime.now()
        )
        conn.close()
        return jsonify({'success': True, 'message': '注册成功'}), 200
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'注册失败: {e}'}), 500

# --------------------------------------------------
# 登录
@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        phone = data.get('phone')
        password = data.get('password')
        if not phone or not password:
            return jsonify({'success': False, 'message': '手机号和密码不能为空'}), 400
        conn = get_db_connection()
        if isinstance(conn, tuple):
            return conn
        cursor = conn.cursor()
        cursor.execute("SELECT password, nickname FROM user_info WHERE phone_number=?", phone)
        row = cursor.fetchone()
        conn.close()
        if not row or not verify_password(row[0], password):
            return jsonify({'success': False, 'message': '用户不存在或密码错误'}), 401
        session['phone'] = phone
        session['nickname'] = row[1]
        return jsonify({'success': True, 'message': '登录成功', 'user': {'phone': phone, 'nickname': row[1]}}), 200
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'登录失败: {e}'}), 500

# --------------------------------------------------
# 检查登录
@app.route('/api/check_login', methods=['GET'])
def check_login():
    if 'phone' in session:
        return jsonify({'success': True, 'user': {'phone': session['phone'], 'nickname': session.get('nickname')}}), 200
    return jsonify({'success': False, 'message': '未登录'}), 401

# --------------------------------------------------
# 退出
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': '已退出登录'}), 200

# --------------------------------------------------
# 修改密码（带手机号验证）
@app.route('/api/change_password', methods=['POST'])
def change_password():
    if 'phone' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401
    try:
        data = request.get_json()
        cur_pwd   = data.get('current_password', '').strip()
        new_pwd   = data.get('new_password', '').strip()
        cur_phone = data.get('current_phone', '').strip()

        if not cur_pwd or not new_pwd or not cur_phone:
            return jsonify({'success': False, 'message': '请完整填写信息'}), 400
        if len(new_pwd) < 6:
            return jsonify({'success': False, 'message': '新密码至少6位'}), 400

        # 关键：必须和当前登录手机号一致
        if cur_phone != session['phone']:
            return jsonify({'success': False, 'message': '当前手机号输入错误'}), 403

        conn = get_db_connection()
        if isinstance(conn, tuple):
            return conn
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM user_info WHERE phone_number=?", session['phone'])
        hashed = cursor.fetchone()[0]
        if not verify_password(hashed, cur_pwd):
            conn.close()
            return jsonify({'success': False, 'message': '当前密码错误'}), 401

        cursor.execute("UPDATE user_info SET password=? WHERE phone_number=?",
                       generate_password_hash(new_pwd), session['phone'])
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '密码修改成功'}), 200
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'修改失败: {e}'}), 500

# --------------------------------------------------
# 大家去过 —— 发布攻略（含图片）
@app.route('/api/submit_guide', methods=['POST'])
def submit_guide():
    if 'phone' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401
    try:
        data = request.get_json()
        content = data.get('content', '').strip()
        images = data.get('images', [])
        if not content:
            return jsonify({'success': False, 'message': '内容不能为空'}), 400
        images_json = json.dumps(images, ensure_ascii=False)
        conn = get_db_connection()
        if isinstance(conn, tuple):
            return conn
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO travel_guides (phone_number, Content, images) VALUES (?,?,?)",
            session['phone'], content, images_json
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '发布成功'}), 200
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'发布失败: {e}'}), 500

# --------------------------------------------------
# 大家去过 —— 获取攻略列表（含图片、点赞、子评论）
@app.route('/api/get_guides', methods=['GET'])
def get_guides():
    try:
        phone = session.get('phone', None)
        conn = get_db_connection()
        if isinstance(conn, tuple):
            return conn
        cursor = conn.cursor()
        sql = """
        SELECT g.guide_id,
               g.phone_number,
               g.Content,
               g.images,
               g.PublishDate,
               u.nickname,
               (SELECT COUNT(*) FROM guide_likes l WHERE l.guide_id=g.guide_id) AS likes,
               CASE WHEN ? IS NOT NULL THEN
                    (SELECT 1 FROM guide_likes ll WHERE ll.guide_id=g.guide_id AND ll.phone=?)
               ELSE 0 END AS user_liked
        FROM travel_guides g
        LEFT JOIN user_info u ON g.phone_number=u.phone_number
        ORDER BY g.PublishDate DESC
        """
        cursor.execute(sql, phone, phone)
        rows = cursor.fetchall()

        guides = []
        for r in rows:
            guide_id, ph, content, images_json, pub, nickname, likes, user_liked = r
            images = json.loads(images_json) if images_json else []
            cursor.execute(
                "SELECT content, phone, reply_time FROM guide_replies WHERE guide_id=? ORDER BY reply_time",
                guide_id
            )
            replies = [{'content': c, 'phone': p, 'time': t.strftime('%m-%d %H:%M')} for c, p, t in cursor.fetchall()]
            guides.append({
                'guide_id': guide_id,
                'phone_number': ph,
                'nickname': nickname or ph,
                'content': content,
                'images': images,
                'PublishDate': pub.strftime('%Y-%m-%d %H:%M:%S'),
                'likes': likes,
                'user_liked': bool(user_liked),
                'replies': replies
            })
        conn.close()
        return jsonify({'success': True, 'guides': guides}), 200
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'加载失败: {e}'}), 500

# --------------------------------------------------
# 点赞
@app.route('/api/guide/like', methods=['POST'])
def guide_like():
    if 'phone' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401
    guide_id = request.get_json().get('guide_id')
    if not guide_id:
        return jsonify({'success': False, 'message': '缺少guide_id'}), 400
    phone = session['phone']
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn
    cursor = conn.cursor()
    cursor.execute(
        "IF NOT EXISTS (SELECT 1 FROM guide_likes WHERE guide_id=? AND phone=?) "
        "INSERT INTO guide_likes(guide_id,phone) VALUES(?,?)",
        guide_id, phone, guide_id, phone
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '已点赞'})

# --------------------------------------------------
# 子评论
@app.route('/api/guide/reply', methods=['POST'])
def guide_reply():
    if 'phone' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401
    data = request.get_json()
    guide_id = data.get('guide_id')
    content = data.get('content', '').strip()
    if not guide_id or not content:
        return jsonify({'success': False, 'message': '参数缺失'}), 400
    phone = session['phone']
    conn = get_db_connection()
    if isinstance(conn, tuple):
        return conn
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO guide_replies(guide_id,phone,content) VALUES(?,?,?)",
        guide_id, phone, content
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': '回复成功'})

# --------------------------------------------------
# 收藏 —— 添加/取消
@app.route('/api/favorite', methods=['POST'])
def toggle_favorite():
    if 'phone' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401
    try:
        data = request.get_json()
        phone = session['phone']
        poi_id = data.get('poi_id')
        name = data.get('poi_name')
        address = data.get('poi_address', '')
        ptype = data.get('poi_type')          # scenic / hotel / food
        lon = data.get('lon')
        lat = data.get('lat')
        if not poi_id or not name or ptype not in ('scenic', 'hotel', 'food'):
            return jsonify({'success': False, 'message': '参数缺失'}), 400
        conn = get_db_connection()
        if isinstance(conn, tuple):
            return conn
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM user_favorite_poi WHERE phone=? AND poi_id=?", phone, poi_id)
        if cursor.fetchone():
            cursor.execute("DELETE FROM user_favorite_poi WHERE phone=? AND poi_id=?", phone, poi_id)
            msg, favorited = '已取消收藏', False
        else:
            cursor.execute(
                "INSERT INTO user_favorite_poi(phone,poi_id,poi_name,poi_address,poi_type,lon,lat) VALUES (?,?,?,?,?,?,?)",
                phone, poi_id, name, address, ptype, lon, lat
            )
            msg, favorited = '收藏成功', True
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': msg, 'favorited': favorited})
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'收藏操作失败: {e}'}), 500

# --------------------------------------------------
# 个人资料更新
@app.route('/api/profile', methods=['POST'])
def update_profile():
    if 'phone' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401
    try:
        data = request.get_json()
        new_phone = data.get('phone_number', '').strip()
        nickname  = data.get('nickname', '').strip()
        gender    = data.get('gender',   '').strip()

        if not new_phone or not nickname:
            return jsonify({'success': False, 'message': '手机号和昵称不能为空'}), 400
        if gender not in ('男', '女'):
            return jsonify({'success': False, 'message': '性别只能为男或女'}), 400

        conn = get_db_connection()
        if isinstance(conn, tuple):  # 数据库连接异常
            return conn
        cursor = conn.cursor()

        # 如果修改了手机号，检查是否已被占用
        if new_phone != session['phone']:
            cursor.execute("SELECT 1 FROM user_info WHERE phone_number=?", new_phone)
            if cursor.fetchone():
                conn.close()
                return jsonify({'success': False, 'message': '新手机号已被占用'}), 400

        # 更新数据库
        cursor.execute(
            "UPDATE user_info SET phone_number=?, nickname=?, gender=? WHERE phone_number=?",
            new_phone, nickname, gender, session['phone']
        )
        conn.commit()
        conn.close()

        # 同步 session
        session['phone']    = new_phone
        session['nickname'] = nickname
        return jsonify({'success': True, 'message': '资料已更新'}), 200
    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'更新失败: {e}'}), 500

# --------------------------------------------------
# 启动
if __name__ == '__main__':
    logger.info("桂林旅游后端启动 …")
    app.run(debug=True, host='0.0.0.0', port=5000)