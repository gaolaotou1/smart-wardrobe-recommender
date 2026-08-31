import json
import os
from datetime import datetime

import cv2
import jwt
import numpy as np
import pymysql
import requests
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as T
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from PIL import Image
from rembg import remove
from werkzeug.utils import secure_filename

BACKEND_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_ROOT)
STATIC_FOLDER = os.path.join(BACKEND_ROOT, 'static')

app = Flask(__name__, static_folder=STATIC_FOLDER)
CORS(app, resources={r"/*": {"origins": "*"}})

def load_env_file(env_path=os.path.join(PROJECT_ROOT, '.env')):
    if not os.path.exists(env_path):
        return

    with open(env_path, encoding='utf-8') as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_bool_env(name, default=False):
    return os.environ.get(name, str(default)).lower() in {'1', 'true', 'yes', 'on'}


load_env_file()


# 数据库连接配置
db_config = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '3306')),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', ''),
    'db': os.environ.get('DB_NAME', 'fashion_system'),
    'charset': os.environ.get('DB_CHARSET', 'utf8mb4')
}

ARK_API_URL = os.environ.get('ARK_API_URL', '')
ARK_API_TOKEN = os.environ.get('ARK_API_TOKEN', '')
ARK_MODEL = os.environ.get('ARK_MODEL', 'doubao-1-5-vision-pro-32k-250115')
SUPERBED_UPLOAD_URL = os.environ.get('SUPERBED_UPLOAD_URL', '')
SUPERBED_TOKEN = os.environ.get('SUPERBED_TOKEN', '')

# 文件上传配置
UPLOAD_FOLDER = os.path.join(STATIC_FOLDER, 'uploads')
PROCESSED_FOLDER = os.path.join(STATIC_FOLDER, 'processed')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_image_to_imgbed(file_obj, filename, content_type='image/png'):
    if not SUPERBED_UPLOAD_URL:
        raise RuntimeError('SUPERBED_UPLOAD_URL 未配置')
    if not SUPERBED_TOKEN:
        raise RuntimeError('SUPERBED_TOKEN 未配置')

    data = {'token': SUPERBED_TOKEN}
    files = {'file': (filename, file_obj, content_type)}
    print("正在上传到图床...")
    response = requests.post(SUPERBED_UPLOAD_URL, data=data, files=files)
    print("图床响应:", response.text)
    return response


@app.route('/api/upload-to-imgbed', methods=['POST'])
def upload_to_imgbed():
    if 'file' not in request.files:
        return jsonify({'err': 1, 'msg': '没有文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'err': 1, 'msg': '没有选择文件'}), 400

    try:
        filename = secure_filename(file.filename)
        content_type = file.mimetype or 'image/png'
        response = upload_image_to_imgbed(file.stream, filename, content_type)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        print("上传到图床失败:", str(e))
        return jsonify({'err': 1, 'msg': str(e)}), 500

def calculate_image_hash(image_path):
    """
    计算图片的感知哈希值
    :param image_path: 图片路径
    :return: 图片的哈希值（字符串）
    """
    try:
        # 打开图片并转换为灰度图
        img = Image.open(image_path).convert('L')
        
        # 调整图片大小为8x8
        img = img.resize((8, 8), Image.Resampling.LANCZOS)
        
        # 转换为numpy数组
        pixels = np.array(img)
        
        # 计算平均值
        avg = pixels.mean()
        
        # 生成哈希值：大于平均值的像素设为1，否则设为0
        hash_value = ''.join(['1' if pixel > avg else '0' for pixel in pixels.flatten()])
        
        return hash_value
    except Exception as e:
        print(f"计算图片哈希值时出错: {e}")
        return None

# 登录接口
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    try:
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        sql = "SELECT id, username FROM users WHERE username=%s AND password=%s"
        cursor.execute(sql, (username, password))
        result = cursor.fetchone()
        
        if result:
            # 生成token
            token = {
                'id': result['id'],
                'username': result['username']
            }
            
            return jsonify({
                'code': 200,
                'message': '登录成功',
                'data': {
                    'id': result['id'],
                    'username': result['username'],
                    'token': json.dumps(token)
                }
            })
        else:
            return jsonify({
                'code': 401,
                'message': '用户名或密码错误'
            })
            
    except Exception as e:
        print("登录错误:", str(e))
        return jsonify({
            'code': 500,
            'message': str(e)
        })
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

# 获取衣物列表
@app.route('/api/clothes', methods=['GET'])
def get_clothes():
    try:
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取查询参数
        user_id = request.args.get('user_id')
        keyword = request.args.get('keyword', '')
        category = request.args.get('category', '')
        season = request.args.get('season', '')
        occasion = request.args.get('occasion', '')
        
        sql = "SELECT * FROM clothes WHERE user_id = %s"
        params = [user_id] if user_id else []
        if keyword:
            sql += " AND (name LIKE %s OR brand LIKE %s OR style LIKE %s OR material LIKE %s OR description LIKE %s)"
            keyword_param = f"%{keyword}%"
            params.extend([keyword_param] * 5)
        if category:
            sql += " AND category = %s"
            params.append(category)
        if season:
            sql += " AND season = %s"
            params.append(season)
        if occasion:
            sql += " AND FIND_IN_SET(%s, occasion)"
            params.append(occasion)
        print(f"执行SQL: {sql}")
        print(f"参数: {params}")
        if not user_id:
            return jsonify({'code': 200, 'data': []})
        cursor.execute(sql, params)
        clothes = cursor.fetchall()
        for item in clothes:
            if item['occasion']:
                item['occasions'] = item['occasion'].split(',')
            else:
                item['occasions'] = []
            # 分类兼容
            item['category'] = item.get('category', '')
            item['subCategory'] = item.get('sub_category', '')
            item['color'] = item.get('color', '')
            item['subColor'] = item.get('sub_color', '')
        return jsonify({'code': 200, 'data': clothes})
    except Exception as e:
        print(f"获取衣物列表失败: {str(e)}")
        return jsonify({'code': 500, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

# 添加衣物
@app.route('/api/clothes', methods=['POST'])
def add_clothes():
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({'code': 400, 'message': '用户ID不能为空'})
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()
        sql = """
            INSERT INTO clothes (
                user_id, name, image_url, category, sub_category, brand,
                style, color, sub_color, season, material,
                occasion, description, thickness, hash
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        category = data.get('category', '')
        sub_category = data.get('subCategory', '')
        color = data.get('color', '')
        sub_color = data.get('subColor', '')
        occasion = ','.join(data['occasions']) if data.get('occasions') else ''
        cursor.execute(sql, (
            user_id, data['name'], data['image_url'],
            category, sub_category, data['brand'],
            data['style'], color, sub_color,
            data['season'], data['material'], occasion,
            data['description'], data['thickness'], data['hash']
        ))
        conn.commit()
        return jsonify({'code': 200, 'message': '添加成功'})
    except Exception as e:
        conn.rollback()
        print(f"添加衣物失败: {str(e)}")
        return jsonify({'code': 500, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

# 获取用户ID的辅助函数
def get_user_id():
    user_str = request.headers.get('Authorization')
    if user_str:
        try:
            user_data = json.loads(user_str)
            return user_data.get('id')
        except:
            return None
    return None


# 添加 AI 分析函数
def analyze_image_with_ai(image_url):
    try:
        if not ARK_API_URL:
            raise RuntimeError('ARK_API_URL 未配置')
        if not ARK_API_TOKEN:
            raise RuntimeError('ARK_API_TOKEN 未配置')

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {ARK_API_TOKEN}'
        }
        data = {
            "model": ARK_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        },
                        {
                            "type": "text",
                            "text": """请分析这件衣物并按以下格式返回信息：
                            {
                                "category": "上装/下装/套装（只返回一个）",
                                "style": "休闲/正装/运动/复古/优雅/简约/街头/民族/其他（只返回一个风格）",
                                "color": "红色系/蓝色系/绿色系/黄色系/紫色系/黑色系/白色系/灰色系（只返回一个颜色）",
                                "season": "spring_and_autumn/summer/winter/all_season(只返回一个季节)",
                                "occasions": ["旅行度假场合", "都市休闲场合", "户外运动场合", "日常社交场合", "商务交流场合", "正式职业场合"],
                                "material": "棉质/丝绸/羊毛/尼龙/涤纶/皮革/牛仔/麻料/其他（必须选择一个）",
                                "description": "简短描述，只描述这件衣服本身的特性，不要涉及风格，适用场合等额外信息的描述"，
                                "thickness"："常规/薄款/厚款/加绒/加厚"，
                            }
                            """
                        }
                    ]
                }
            ]
        }
        
        response = requests.post(ARK_API_URL, json=data, headers=headers)
        if response.status_code == 200:
            result = response.json()
            # 解析 AI 返回的文本，提取 JSON 部分
            try:
                content = result['choices'][0]['message']['content']
                # 提取 JSON 字符串并解析
                import re
                json_str = re.search(r'\{.*\}', content, re.DOTALL)
                if json_str:
                    print(json.loads(json_str.group()))
                    return json.loads(json_str.group())
            except Exception as e:
                print("解析 AI 响应失败:", str(e))
        return None
    except Exception as e:
        print("AI 分析失败:", str(e))
        return None

class ClothesClassifier:
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = self.load_model()
        self.transform = T.Compose([
            T.Resize((224, 224)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        
    def load_model(self):
        model = models.resnet50()
        num_features = model.fc.in_features
        model.fc = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(num_features, 2)
        )
        
        model_path = os.environ.get(
            'CLOTHES_MODEL_PATH',
            os.path.join(PROJECT_ROOT, 'models', 'final_model_20250328_212820.pth')
        )
        if not os.path.isabs(model_path):
            model_path = os.path.join(PROJECT_ROOT, model_path)
        checkpoint = torch.load(model_path, map_location=self.device)
        if 'model_state_dict' in checkpoint:
            model.load_state_dict(checkpoint['model_state_dict'])
        else:
            model.load_state_dict(checkpoint)
            
        model = model.to(self.device)
        model.eval()
        return model
        
    def classify_image(self, image):
        try:
            image_tensor = self.transform(image).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(image_tensor)
                probabilities = torch.nn.functional.softmax(outputs, dim=1)
                prob, pred = torch.max(probabilities, dim=1)
                
                is_clothes = pred[0].item() == 0  # 假设0表示衣物类
                confidence = prob[0].item()
                
                return is_clothes, confidence
                
        except Exception as e:
            print(f"分类错误: {str(e)}")
            return False, 0.0

# 创建分类器实例
classifier = ClothesClassifier()

# 修改上传处理函数
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({
            'code': 400,
            'message': '没有文件'
        })
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({
            'code': 400,
            'message': '没有选择文件'
        })
        
    if file and allowed_file(file.filename):
        try:
            # 保存临时文件
            temp_filename = 'temp_' + secure_filename(file.filename)
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
            file.save(temp_path)
            
            # 读取图片并进行分类
            image = Image.open(temp_path).convert('RGB')
            is_clothes, confidence = classifier.classify_image(image)
            
            # 如果不是衣物，保存原始图片并返回
            if not is_clothes:
                # 保存原始图片
                filename = secure_filename(file.filename)
                processed_filename = f"processed_{filename.rsplit('.', 1)[0]}.png"
                processed_path = os.path.join(app.config['PROCESSED_FOLDER'], processed_filename)
                cv2.imwrite(processed_path, cv2.imread(temp_path))
                
                # 清理临时文件
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                
                with open(processed_path, 'rb') as img_file:
                    response = upload_image_to_imgbed(img_file, processed_filename)
                    
                    if response.status_code == 200:
                        try:
                            result = response.json()
                            if not result.get('err'):
                                image_url = result.get('url')
                                if image_url:
                                    return jsonify({
                                        'code': 400,
                                        'message': '检测到非衣物图片，请上传衣物照片',
                                        'is_clothes': False,
                                        'confidence': confidence,
                                        'url': f'/static/processed/{processed_filename}',
                                        'bed_url': image_url
                                    })
                        except Exception as e:
                            print("解析图床响应失败:", str(e))
                
                return jsonify({
                    'code': 400,
                    'message': '检测到非衣物图片，请上传衣物照片',
                    'is_clothes': False,
                    'confidence': confidence,
                    'url': f'/static/processed/{processed_filename}'
                })
            
            # 计算图片的hash值
            hash_value = calculate_image_hash(temp_path)
            print(f"计算得到的新图片hash值: {hash_value}")
            
            # 检查是否已存在相似图片
            conn = pymysql.connect(**db_config)
            cursor = conn.cursor()
            
            # 从请求头中获取用户ID
            user_id = request.headers.get('X-User-ID')
            if not user_id:
                print("未找到用户ID")
                return jsonify({
                    'code': 401,
                    'message': '未提供用户ID'
                })
            
            print(f"获取到的用户ID: {user_id}")  # 添加调试日志
            
            sql = "SELECT hash FROM clothes WHERE user_id = %s AND hash IS NOT NULL"
            print(f"执行的SQL语句: {sql}")
            print(f"参数 user_id: {user_id}")
            cursor.execute(sql, (user_id,))
            existing_hashes = cursor.fetchall()
            cursor.close()
            conn.close()
            
            print(f"数据库中已有的hash值数量: {len(existing_hashes)}")
            if len(existing_hashes) > 0:
                print("数据库中已有的hash值:")
                for idx, hash_tuple in enumerate(existing_hashes):
                    print(f"第 {idx + 1} 个hash值: {hash_tuple[0]}")
            
            # 计算与现有图片的相似度
            max_similarity = 0
            for idx, existing_hash in enumerate(existing_hashes):
                if existing_hash[0]:  # 确保hash值不为空
                    print(f"\n对比第 {idx + 1} 个hash值:")
                    print(f"数据库中的hash值: {existing_hash[0]}")
                    hamming_distance = sum(c1 != c2 for c1, c2 in zip(hash_value, existing_hash[0]))
                    similarity = 1 - (hamming_distance / len(hash_value))
                    print(f"汉明距离: {hamming_distance}")
                    print(f"相似度: {similarity:.4f}")
                    max_similarity = max(max_similarity, similarity)
            
            print(f"\n最大相似度: {max_similarity:.4f}")
            
            # 如果相似度超过阈值，返回提示
            if max_similarity > 0.95:
                print("检测到相似图片，返回提示信息")
                return jsonify({
                    'code': 400,
                    'message': '检测到相似图片，该衣物可能已经上传过',
                    'similarity': max_similarity,
                    'is_duplicate': True
                })
            
            # 继续处理衣物图片
            input_image = cv2.imread(temp_path)
            output_image = remove(input_image)
            
            # 保存处理后的图片
            filename = secure_filename(file.filename)
            processed_filename = f"processed_{filename.rsplit('.', 1)[0]}.png"
            processed_path = os.path.join(app.config['PROCESSED_FOLDER'], processed_filename)
            cv2.imwrite(processed_path, output_image)
            
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            # 上传到图床并进行 AI 分析
            with open(processed_path, 'rb') as img_file:
                response = upload_image_to_imgbed(img_file, processed_filename)
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        if not result.get('err'):
                            image_url = result.get('url')
                            if image_url:
                                ai_result = analyze_image_with_ai(image_url)
                                return jsonify({
                                    'code': 200,
                                    'message': '上传成功',
                                    'url': f'/static/processed/{processed_filename}',
                                    'bed_url': image_url,
                                    'ai_analysis': ai_result,
                                    'hash': hash_value
                                })
                    except Exception as e:
                        print("解析图床响应失败:", str(e))
                
            return jsonify({
                'code': 200,
                'message': '上传成功',
                'url': f'/static/processed/{processed_filename}',
                'hash': hash_value
            })
                    
        except Exception as e:
            print(f"处理图片时出错: {str(e)}")
            # 清理临时文件
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({
                'code': 500,
                'message': f'处理图片时出错: {str(e)}'
            })
            
    return jsonify({
        'code': 400,
        'message': '不支持的文件类型'
    })

# 添加静态文件路由
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

# 获取统计数据
@app.route('/api/clothes/statistics', methods=['GET'])
def get_clothes_statistics():
    try:
        user_id = request.args.get('user_id')  # 添加用户ID参数
        if not user_id:  # 如果没有用户ID，返回默认值
            return jsonify({
                'code': 200,
                'data': {
                    'total': 0,
                    'season': 0,
                    'outfit': 0
                }
            })
            
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取当前季节
        current_month = datetime.now().month
        current_season = ''
        if 3 <= current_month <= 5:
            current_season = 'spring_and_autumn'
        elif 6 <= current_month <= 8:
            current_season = 'summer'
        elif 9 <= current_month <= 11:
            current_season = 'spring_and_autumn'
        else:
            current_season = 'winter'
        
        # 获取衣物总数（添加用户ID过滤）
        cursor.execute("SELECT COUNT(*) as total FROM clothes WHERE user_id = %s", (user_id,))
        total_count = cursor.fetchone()['total']
        
        # 获取本季衣物数量（添加用户ID过滤）
        cursor.execute("""
            SELECT COUNT(*) as season_count 
            FROM clothes 
            WHERE user_id = %s AND season = %s
        """, (user_id, current_season))
        season_count = cursor.fetchone()['season_count']
        
        # 获取穿搭总数（添加用户ID过滤）
        cursor.execute("SELECT COUNT(*) as outfit_count FROM outfits WHERE user_id = %s", (user_id,))
        outfit_count = cursor.fetchone()['outfit_count']
        
        return jsonify({
            'code': 200,
            'data': {
                'total': total_count,
                'season': season_count,
                'outfit': outfit_count
            }
        })
    except Exception as e:
        print(f"获取统计数据失败: {str(e)}")
        return jsonify({
            'code': 500,
            'message': str(e)
        })
    finally:
        cursor.close()
        conn.close()

# 获取穿搭列表
@app.route('/api/outfits', methods=['GET'])
def get_outfits():
    try:
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取当前用户ID
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({
                'code': 400,
                'message': '缺少用户ID'
            })
        
        print(f"正在获取用户 {user_id} 的穿搭列表")
        
        # 获取穿搭列表
        cursor.execute("""
            SELECT o.*, GROUP_CONCAT(oc.clothes_id) as clothes_ids
            FROM outfits o
            LEFT JOIN outfit_clothes oc ON o.id = oc.outfit_id
            WHERE o.user_id = %s
            GROUP BY o.id
        """, (user_id,))
        outfits = cursor.fetchall()
        
        print(f"查询到的穿搭列表: {outfits}")
        
        # 获取每个穿搭的衣物详情
        for outfit in outfits:
            if outfit['clothes_ids']:
                clothes_ids = outfit['clothes_ids'].split(',')
                cursor.execute("""
                    SELECT c.*, oc.position
                    FROM clothes c
                    JOIN outfit_clothes oc ON c.id = oc.clothes_id
                    WHERE c.id IN (%s)
                """ % ','.join(['%s'] * len(clothes_ids)), clothes_ids)
                outfit['clothes'] = cursor.fetchall()
            else:
                outfit['clothes'] = []
        
        print(f"处理后的穿搭列表: {outfits}")
        
        return jsonify({
            'code': 200,
            'data': outfits
        })
    except Exception as e:
        print(f"获取穿搭列表失败: {str(e)}")
        return jsonify({
            'code': 500,
            'message': str(e)
        })
    finally:
        cursor.close()
        conn.close()

# 创建穿搭
@app.route('/api/outfits', methods=['POST'])
def create_outfit():
    try:
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        data = request.get_json()
        
        # 创建穿搭记录
        cursor.execute("""
            INSERT INTO outfits (name, description, image_url, user_id)
            VALUES (%s, %s, %s, %s)
        """, (data['name'], data['description'], data['image_url'], data['user_id']))
        outfit_id = cursor.lastrowid
        
        # 创建穿搭衣物关联
        for clothes in data['clothes']:
            cursor.execute("""
                INSERT INTO outfit_clothes (outfit_id, clothes_id, position)
                VALUES (%s, %s, %s)
            """, (outfit_id, clothes['id'], clothes['position']))
        
        conn.commit()
        
        return jsonify({
            'code': 200,
            'message': '创建成功'
        })
    except Exception as e:
        conn.rollback()
        print(f"创建穿搭失败: {str(e)}")
        return jsonify({
            'code': 500,
            'message': str(e)
        })
    finally:
        cursor.close()
        conn.close()

# 更新穿搭
@app.route('/api/outfits/<int:outfit_id>', methods=['PUT'])
def update_outfit(outfit_id):
    try:
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        data = request.get_json()
        
        # 更新穿搭记录
        cursor.execute("""
            UPDATE outfits
            SET name = %s, description = %s, image_url = %s
            WHERE id = %s
        """, (data['name'], data['description'], data['image_url'], outfit_id))
        
        # 删除旧的衣物关联
        cursor.execute("DELETE FROM outfit_clothes WHERE outfit_id = %s", (outfit_id,))
        
        # 创建新的衣物关联
        for clothes in data['clothes']:
            cursor.execute("""
                INSERT INTO outfit_clothes (outfit_id, clothes_id, position)
                VALUES (%s, %s, %s)
            """, (outfit_id, clothes['id'], clothes['position']))
        
        conn.commit()
        
        return jsonify({
            'code': 200,
            'message': '更新成功'
        })
    except Exception as e:
        conn.rollback()
        print(f"更新穿搭失败: {str(e)}")
        return jsonify({
            'code': 500,
            'message': str(e)
        })
    finally:
        cursor.close()
        conn.close()

# 删除穿搭
@app.route('/api/outfits/<int:outfit_id>', methods=['DELETE'])
def delete_outfit(outfit_id):
    try:
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 删除穿搭记录
        cursor.execute("DELETE FROM outfits WHERE id = %s", (outfit_id,))
        conn.commit()
        
        return jsonify({
            'code': 200,
            'message': '删除成功'
        })
    except Exception as e:
        conn.rollback()
        print(f"删除穿搭失败: {str(e)}")
        return jsonify({
            'code': 500,
            'message': str(e)
        })
    finally:
        cursor.close()
        conn.close()

# 删除衣物
@app.route('/api/clothes/<int:clothes_id>', methods=['DELETE'])
def delete_clothes(clothes_id):
    try:
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 删除衣物记录
        cursor.execute("DELETE FROM clothes WHERE id = %s", (clothes_id,))
        conn.commit()
        
        return jsonify({
            'code': 200,
            'message': '删除成功'
        })
    except Exception as e:
        conn.rollback()
        print(f"删除衣物失败: {str(e)}")
        return jsonify({
            'code': 500,
            'message': str(e)
        })
    finally:
        cursor.close()
        conn.close()

# 更新衣物
@app.route('/api/clothes/<int:clothes_id>', methods=['PUT'])
def update_clothes(clothes_id):
    try:
        data = request.get_json()
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor()
        sql = """
            UPDATE clothes 
            SET name = %s, image_url = %s, category = %s, sub_category = %s,
                brand = %s, style = %s, color = %s, sub_color = %s,
                season = %s, material = %s, occasion = %s,
                description = %s, thickness = %s
            WHERE id = %s
        """
        category = data.get('category', '')
        sub_category = data.get('subCategory', '')
        color = data.get('color', '')
        sub_color = data.get('subColor', '')
        occasion = ','.join(data['occasions']) if data.get('occasions') else ''
        cursor.execute(sql, (
            data['name'], data['image_url'],
            category, sub_category, data['brand'],
            data['style'], color, sub_color,
            data['season'], data['material'], occasion,
            data['description'], data['thickness'],
            clothes_id
        ))
        conn.commit()
        return jsonify({'code': 200, 'message': '更新成功'})
    except Exception as e:
        conn.rollback()
        print(f"更新衣物失败: {str(e)}")
        return jsonify({'code': 500, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()

# 添加AI搭配推荐接口
@app.route('/api/recommend', methods=['POST'])
def recommend_outfit():
    try:
        data = request.get_json()
        clothes = data.get('clothes', [])
        question = data.get('question', '')
        image_url = data.get('image_url', '')
        
        print("收到的请求数据：")
        print("问题:", question)
        print("上传的图片:", image_url)
        print("选择的衣物:", clothes)
        
        # 调用AI接口获取推荐
        if not ARK_API_URL:
            raise RuntimeError('ARK_API_URL 未配置')
        if not ARK_API_TOKEN:
            raise RuntimeError('ARK_API_TOKEN 未配置')

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {ARK_API_TOKEN}'
        }
        
        # 构建消息内容
        content = []
        
        # 如果有用户上传的图片，先添加图片
        if image_url:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": image_url
                }
            })
            print("添加用户上传的图片:", image_url)
        
        # 添加衣物图片
        clothes_images = data.get('clothes_images', [])
        if clothes and clothes_images:
            for item, img_url in zip(clothes, clothes_images):
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": img_url
                    }
                })
                print("添加衣物图片:", img_url)

        # 构建提示词
        base_prompt = f"你是一个专业的服装穿搭搭配师。请根据我提供的衣物和图片，回答以下问题：\n\n问题：{question}\n\n"
        
        if clothes:
            base_prompt += "我在衣柜中已经选择了以下衣物（请严格按照列出的顺序在回答中引用这些衣物）：\n"
            for i, (item, image_url) in enumerate(zip(clothes, clothes_images), 1):
                base_prompt += f"""
{i}. {item.get('name', '')} - {item.get('category', '')}
    图片链接: {image_url}
    风格: {item.get('style', '')}
    颜色: {item.get('color', '')}
    季节: {item.get('season', '')}
    材质: {item.get('material', '')}
    场合: {', '.join(item.get('occasions', []))}
   描述: {item.get('description', '')}
"""
        print(base_prompt)
        # 添加固定格式要求
        base_prompt += """
请直接返回以下JSON格式的回答（不要包含任何其他文本）：
{
    "问题回答": "对问题的回答，不要扩展发散思维",
    "推荐图片": ["根据我的回答选择我已经有的图片链接"]
}

注意事项：
1. 必须按照上述格式返回JSON字符串
2. 问题回答应该语言自然，富有亲和力，不应直接套用对应的服装信息，要加工后用自己的话回答
3. 推荐图片数组必须从我提供的衣物图片链接中选择，并且根据我的回答提供涉及的图片链接
4. 请你严格根据我的回答提供涉及的图片链接
5. 不要在JSON之外添加任何其他文本
6. 确保JSON格式正确，可以被解析
7. 不要生成或使用其他图片链接
8.我的是上传图片的话，需要将我的上传图片也显示出来
9.若用户的问题为服装搭配推荐，应注意：
    (1)若用户想要搭配裙子，应该告诉用户裙子无法搭配，只能搭配上下装
    (2)只需要告诉用户推荐的衣服并根据衣服的相关信息说明理由，不需要告诉用户不推荐搭配什么
    (3)搭配时默认应用以下搭配原则，若用户有其他搭配倾向，以用户为准：
        <1>色彩搭配：考虑互补色、类似色、同色系等色彩理论
        <2>风格统一：确保搭配中的上下装风格协调一致
        <3>场景适配：根据用户需求推荐适合特定场合的搭配
        <4>季节适应：推荐符合当季气候的搭配
10.若用户问题为总结衣柜内的相关信息，如询问衣柜内有几件衣服，有几件连衣裙等问题，除非用户要求提供图片，否则不需要返回图片链接，即推荐图片应该为空
"""

        # 添加文本到内容中
        content.append({
            "type": "text",
            "text": base_prompt
        })
        
        # 构建完整的请求数据
        ai_data = {
            "model": ARK_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ]
        }
        
        print("发送到AI的数据：", json.dumps(ai_data, ensure_ascii=False, indent=2))
        
        response = requests.post(ARK_API_URL, json=ai_data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            
            # 尝试解析AI响应中的JSON格式
            try:
                # 查找JSON格式的响应
                import re
                json_match = re.search(r'\{[\s\S]*\}', ai_response)
                if json_match:
                    json_str = json_match.group()
                    response_data = json.loads(json_str)
                    
                    # 如果AI没有返回推荐图片，使用选择的衣物图片
                    if not response_data.get('推荐图片'):
                        response_data['推荐图片'] = [item.get('image_url') for item in clothes if item.get('image_url')]
                    
                    return jsonify({
                        'code': 200,
                        'data': response_data
                    })
            except Exception as e:
                print(f"解析AI响应失败: {str(e)}")
                print("原始响应:", ai_response)
            
            # 如果解析失败，构造一个基本的响应
            return jsonify({
                'code': 200,
                'data': {
                    '问题回答': ai_response,
                    '推荐图片': [item.get('image_url') for item in clothes if item.get('image_url')]
                }
            })
        else:
            print(f"AI接口调用失败: {response.text}")
            error_message = "AI服务暂时不可用，请稍后再试"
            try:
                error_data = response.json()
                if 'error' in error_data and 'message' in error_data['error']:
                    error_message = error_data['error']['message']
                    if 'Timeout while downloading url' in error_message:
                        error_message = "图片加载超时，请重试或使用其他图片"
                    elif 'Invalid image URL' in error_message:
                        error_message = "图片链接无效，请使用其他图片"
            except:
                pass
            
            return jsonify({
                'code': 200,
                'message': error_message
            })
            
    except Exception as e:
        print(f"推荐搭配失败: {str(e)}")
        return jsonify({
            'code': 500,
            'message': str(e)
        })

# 获取仪表盘数据
@app.route('/api/dashboard', methods=['GET'])
def get_dashboard_data():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({
                'code': 400,
                'message': '缺少用户ID'
            })

        conn = pymysql.connect(**db_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # 1. 获取衣物统计数据
        cursor.execute('''
            SELECT 
                COUNT(*) as total_clothes,
                COUNT(DISTINCT category) as category_count,
                COUNT(DISTINCT style) as style_count
            FROM clothes 
            WHERE user_id = %s
        ''', (user_id,))
        clothes_stats = cursor.fetchone()

        # 2. 获取本月穿搭数
        cursor.execute('''
            SELECT COUNT(*) as monthly_outfits
            FROM outfits 
            WHERE user_id = %s 
            AND DATE_FORMAT(create_time, '%%Y-%%m') = DATE_FORMAT(CURRENT_DATE(), '%%Y-%%m')
        ''', (user_id,))
        monthly_stats = cursor.fetchone()

        # 3. 获取衣物分类分布
        cursor.execute('''
            SELECT category as name, COUNT(*) as value 
            FROM clothes 
            WHERE user_id = %s 
            GROUP BY category
            ORDER BY value DESC
        ''', (user_id,))
        category_distribution = cursor.fetchall()

        # 4. 获取最近7天的穿搭趋势（修改为兼容MySQL 5.6的写法）
        cursor.execute('''
            SELECT 
                DATE_FORMAT(selected_date.date, '%%m.%%d') as date,
                COUNT(o.id) as count
            FROM (
                SELECT CURDATE() - INTERVAL (a.a) DAY as date
                FROM (
                    SELECT 0 as a UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL 
                    SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6
                ) as a
            ) as selected_date
            LEFT JOIN outfits o ON DATE(o.create_time) = selected_date.date AND o.user_id = %s
            GROUP BY selected_date.date
            ORDER BY selected_date.date
        ''', (user_id,))
        weekly_trend = cursor.fetchall()

        # 5. 获取最近的穿搭记录
        cursor.execute('''
            SELECT 
                o.id,
                DATE_FORMAT(o.create_time, '%%m.%%d') as date,
                o.name as title,
                o.description as description,
                o.image_url,
                GROUP_CONCAT(DISTINCT c.category) as categories
            FROM outfits o
            LEFT JOIN outfit_clothes oc ON o.id = oc.outfit_id
            LEFT JOIN clothes c ON oc.clothes_id = c.id
            WHERE o.user_id = %s
            GROUP BY o.id
            ORDER BY o.create_time DESC
            LIMIT 3
        ''', (user_id,))
        recent_outfits = cursor.fetchall()

        # 处理穿搭记录数据
        recent_recommends = []
        for outfit in recent_outfits:
            categories = outfit['categories'].split(',') if outfit['categories'] else []
            tags = categories[:3] if categories else ['日常搭配']
            recent_recommends.append({
                'date': outfit['date'],
                'title': outfit['title'] or '我的穿搭',
                'desc': outfit['description'] or '精心搭配的穿搭方案',
                'image': outfit['image_url'],
                'tags': tags
            })

        # 6. 获取季节分布
        cursor.execute('''
            SELECT season, COUNT(*) as count
            FROM clothes
            WHERE user_id = %s
            GROUP BY season
        ''', (user_id,))
        season_stats = cursor.fetchall()

        # 7. 获取上装子类别分布
        cursor.execute('''
                    SELECT sub_category, COUNT(*) as count
                    FROM clothes
                    WHERE user_id = %s and category = "上装"
                    GROUP BY sub_category
                ''', (user_id,))
        sub_categoryDistribution = cursor.fetchall()

        # 8. 获取下装子类别分布
        cursor.execute('''
                            SELECT sub_category, COUNT(*) as count
                            FROM clothes
                            WHERE user_id = %s and category = "下装"
                            GROUP BY sub_category
                        ''', (user_id,))
        sub_categoryDistribution1 = cursor.fetchall()

        # 9. 获取本月新增衣物数
        cursor.execute('''
                    SELECT COUNT(*) as monthly_newClothes
                    FROM clothes 
                    WHERE user_id = %s 
                    AND DATE_FORMAT(create_time, '%%Y-%%m') = DATE_FORMAT(CURRENT_DATE(), '%%Y-%%m')
                ''', (user_id,))
        monthly_newClothes_stat = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({
            'code': 200,
            'data': {
                'statistics': {
                    'totalClothes': clothes_stats['total_clothes'],
                    'monthlyOutfits': monthly_stats['monthly_outfits'],
                    'categoryCount': clothes_stats['category_count'],
                    'styleCount': clothes_stats['style_count'],
                    'monthly_newClothesCount': monthly_newClothes_stat['monthly_newClothes'],
                },
                'categoryDistribution': category_distribution,
                'weeklyTrend': weekly_trend,
                'recentOutfits': recent_recommends,
                'seasonStats': season_stats,
                'sub_categoryDistribution': sub_categoryDistribution,
                'sub_categoryDistribution1': sub_categoryDistribution1,
            }
        })
    except Exception as e:
        print('获取仪表盘数据失败:', str(e))
        return jsonify({
            'code': 500,
            'message': '获取数据失败'
        })

# 获取上装和下装类别分布
@app.route('/api/clothes/category-distribution', methods=['GET'])
def get_category_distribution():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({
                'code': 200,
                'data': {
                    'top': [],
                    'bottom': []
                }
            })
            
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取上装类别分布
        cursor.execute("""
            SELECT sub_category, COUNT(*) as count 
            FROM clothes 
            WHERE user_id = %s AND category = '上装' AND sub_category IS NOT NULL
            GROUP BY sub_category
        """, (user_id,))
        top_distribution = cursor.fetchall()
        
        # 获取下装类别分布
        cursor.execute("""
            SELECT sub_category, COUNT(*) as count 
            FROM clothes 
            WHERE user_id = %s AND category = '下装' AND sub_category IS NOT NULL
            GROUP BY sub_category
        """, (user_id,))
        bottom_distribution = cursor.fetchall()
        
        # 处理上装数据
        top_data = [{
            'name': item['sub_category'],
            'value': item['count']
        } for item in top_distribution]
        
        # 处理下装数据
        bottom_data = [{
            'name': item['sub_category'],
            'value': item['count']
        } for item in bottom_distribution]
        
        return jsonify({
            'code': 200,
            'data': {
                'top': top_data,
                'bottom': bottom_data
            }
        })
    except Exception as e:
        print(f"获取类别分布失败: {str(e)}")
        return jsonify({
            'code': 500,
            'message': str(e)
        })
    finally:
        cursor.close()
        conn.close()

# 注册接口
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({
                'code': 400,
                'message': '用户名和密码不能为空'
            })
            
        if len(username) < 4 or len(username) > 20:
            return jsonify({
                'code': 400,
                'message': '用户名长度应为4-20个字符'
            })
            
        if len(password) < 6 or len(password) > 20:
            return jsonify({
                'code': 400,
                'message': '密码长度应为6-20个字符'
            })
        
        conn = pymysql.connect(**db_config)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 检查用户名是否已存在
        cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
        if cursor.fetchone():
            return jsonify({
                'code': 400,
                'message': '用户名已存在'
            })
        
        # 创建新用户
        cursor.execute(
            'INSERT INTO users (username, password) VALUES (%s, %s)',
            (username, password)
        )
        conn.commit()
        
        return jsonify({
            'code': 200,
            'message': '注册成功'
        })
    except Exception as e:
        conn.rollback()
        print("注册错误:", str(e))
        return jsonify({
            'code': 500,
            'message': str(e)
        })
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

if __name__ == '__main__':
    app.run(
        host=os.environ.get('FLASK_HOST', '127.0.0.1'),
        port=int(os.environ.get('FLASK_PORT', '8088')),
        debug=get_bool_env('FLASK_DEBUG', True)
    )
