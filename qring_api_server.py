#!/usr/bin/env python3
"""
Qring 数据 API 服务器

接收来自 iOS App 的 Qring 数据，并提供 REST API 接口供前端调用
"""

import os
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime, timedelta, date
import threading
import time
from pytz import timezone

# 设置时区（新加坡时间 UTC+8）
SINGAPORE_TZ = timezone('Asia/Singapore')

def get_local_time():
    """获取新加坡本地时间"""
    return datetime.now(SINGAPORE_TZ)

def parse_datetime_with_tz(date_str):
    """解析日期字符串并转换为新加坡时区"""
    try:
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        
        # 如果是 naive datetime，添加新加坡时区
        if dt.tzinfo is None:
            dt = SINGAPORE_TZ.localize(dt)
        else:
            # 如果有时区信息，转换为新加坡时区
            dt = dt.astimezone(SINGAPORE_TZ)
        
        return dt
    except Exception as e:
        print(f"   ⚠️ 日期解析错误: {date_str}, 错误: {e}")
        return get_local_time()  # 解析失败时返回当前时间

load_dotenv()

app = Flask(__name__)

# CORS配置 - 支持环境变量配置允许的来源
cors_origins = os.getenv('CORS_ORIGINS', '*')
if cors_origins == '*':
    # 开发环境：允许所有来源
    CORS(app)
else:
    # 生产环境：只允许指定的来源
    origins = [origin.strip() for origin in cors_origins.split(',')]
    CORS(app, origins=origins)

def get_client_source():
    """获取客户端来源标识"""
    client_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    
    # 判断是否为本地请求（Web前端）
    is_local = client_ip == '127.0.0.1' or client_ip.startswith('::1')
    
    # 判断是否为手机App（通过IP段或User-Agent）
    is_mobile = (
        'iOS' in user_agent or 
        'iPhone' in user_agent or 
        'iPad' in user_agent or
        (client_ip.startswith('10.') and not is_local) or
        client_ip.startswith('192.168.')
    )
    
    if is_local:
        return "💻 Web前端", client_ip
    elif is_mobile:
        return "📱 手机App", client_ip
    else:
        return f"🌐 其他客户端", client_ip

# 数据存储（实际项目中应使用数据库）
data_store = {
    "heartrate": [],           # 心率数据
    "sleep": [],               # 睡眠数据
    "activity": [],            # 活动数据
    "blood_pressure": [],      # 血压数据
    "blood_oxygen": [],         # 血氧数据
    "temperature": [],         # 体温数据
    "stress": [],              # 压力数据
    "hrv": [],                 # HRV 数据
    "exercise": [],            # 运动记录数据
    "sport_plus": [],          # 运动+数据
    "sedentary": [],           # 久坐提醒数据
    "user_info": [],           # 用户信息（只保留最新一条）
    "target_info": [],         # 目标设置（只保留最新一条）
    "manual_measurements": [],  # 主动测量数据（单次测量、实时监测）
    "last_update": {}
}

# 数据文件路径
# 支持 Railway Volume 持久化存储
DATA_DIR = os.getenv('DATA_DIR', os.getenv('RAILWAY_VOLUME_MOUNT_PATH', '.'))
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "qring_data.json")


def load_data():
    """从文件加载数据"""
    global data_store
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded_data = json.load(f)
                # 确保所有必需的键都存在
                for key in ["heartrate", "sleep", "activity", "blood_pressure", "blood_oxygen", 
                           "temperature", "stress", "hrv", "exercise", "sport_plus", "sedentary",
                           "user_info", "target_info", "manual_measurements", "last_update"]:
                    if key not in loaded_data:
                        loaded_data[key] = [] if key != "last_update" else {}
                data_store = loaded_data
                # 转换时间字符串为 datetime 对象（如果需要）
    except Exception as e:
        print(f"加载数据失败: {e}")
        # 如果加载失败，使用默认的空数据结构
        data_store = {
            "heartrate": [],
            "sleep": [],
            "activity": [],
            "blood_pressure": [],
            "blood_oxygen": [],
            "temperature": [],
            "stress": [],
            "hrv": [],
            "exercise": [],
            "sport_plus": [],
            "sedentary": [],
            "user_info": [],
            "target_info": [],
            "manual_measurements": [],
            "last_update": {}
        }


def save_data():
    """保存数据到文件"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data_store, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"保存数据失败: {e}")


def convert_qring_heartrate_to_api(qring_data):
    """
    将 Qring 心率数据转换为 API 格式
    
    Qring 格式: {hrId, date, heartrate}
    API 格式: {timestamp, bpm}
    """
    result = []
    zero_count = 0
    non_zero_count = 0
    future_count = 0  # 未来时间数据计数
    now = get_local_time()
    
    for item in qring_data:
        if isinstance(item, dict):
            # 处理日期格式 - 使用 parse_datetime_with_tz 确保返回 aware datetime
            date_str = item.get("date", "")
            dt = None
            if date_str:
                dt = parse_datetime_with_tz(date_str)
            
            # 过滤未来时间的数据（超过当前时间5分钟以上的数据）
            if dt and dt > now + timedelta(minutes=5):
                future_count += 1
                if future_count <= 3:  # 只打印前3条未来时间数据的详情
                    print(f"   ⏰ [convert_qring_heartrate_to_api] 跳过未来时间数据: date={date_str}, dt={dt.strftime('%Y-%m-%d %H:%M:%S')}, 距离现在={(dt - now).total_seconds() / 60:.1f}分钟")
                continue  # 跳过未来时间的数据
            
            if dt:
                timestamp = dt.isoformat()
            else:
                timestamp = get_local_time().isoformat()
            
            # 获取心率值，支持多种可能的字段名
            heartrate_value = item.get("heartrate") or item.get("heartRate") or item.get("bpm") or item.get("hr") or 0
            
            # 如果是字符串，尝试转换为整数
            if isinstance(heartrate_value, str):
                try:
                    heartrate_value = int(heartrate_value)
                except:
                    heartrate_value = 0
            
            if heartrate_value == 0:
                zero_count += 1
            else:
                non_zero_count += 1
            
            # 添加 hrId 到结果中（用于去重）
            result.append({
                "timestamp": timestamp,
                "hrId": item.get("hrId", 0),
                "bpm": int(heartrate_value) if heartrate_value else 0,
            })
    
    if future_count > 0:
        print(f"   ⚠️ 过滤掉未来时间数据: {future_count} 条")
    
    if zero_count > 0 or non_zero_count > 0:
        print(f"   数据统计: 有效数据(bpm>0)={non_zero_count} 条, 零值数据={zero_count} 条")
        if non_zero_count == 0 and zero_count > 0:
            print(f"   ⚠️ 警告: 所有 {zero_count} 条数据的心率值都是0，可能是数据格式问题或设备未正确记录")
            # 打印前几条原始数据用于调试
            if len(qring_data) > 0:
                print(f"   原始数据示例（前3条）: {qring_data[:3]}")
    
    return result


def convert_qring_sleep_to_api(qring_data):
    """
    将 Qring 睡眠数据转换为 API 格式
    
    Qring 格式: {type, happenDate, endTime, total}
    API 格式: {day, bedtime_start, bedtime_end, duration, ...}
    """
    # 按日期分组
    sleep_by_day = {}
    
    for item in qring_data:
        if isinstance(item, dict):
            happen_date = item.get("happenDate", "")
            if happen_date:
                # 提取日期部分
                try:
                    dt = datetime.strptime(happen_date, "%Y-%m-%d %H:%M:%S")
                    day_key = dt.strftime("%Y-%m-%d")
                except:
                    day_key = date.today().strftime("%Y-%m-%d")
            else:
                day_key = date.today().strftime("%Y-%m-%d")
            
            if day_key not in sleep_by_day:
                sleep_by_day[day_key] = {
                    "day": day_key,
                    "bedtime_start": happen_date,
                    "bedtime_end": item.get("endTime", happen_date),
                    "duration": 0,
                    "total": 0,
                    "awake": 0,
                    "light": 0,
                    "deep": 0,
                    "rem": 0,
                    "periods": []
                }
            
            sleep_type = item.get("type", 0)
            total_minutes = item.get("total", 0)
            
            # 累加各类型睡眠时长
            if sleep_type == 1:  # SLEEPTYPESOBER - 清醒
                sleep_by_day[day_key]["awake"] += total_minutes
            elif sleep_type == 2:  # SLEEPTYPELIGHT - 浅睡
                sleep_by_day[day_key]["light"] += total_minutes
            elif sleep_type == 3:  # SLEEPTYPEDEEP - 深睡
                sleep_by_day[day_key]["deep"] += total_minutes
            elif sleep_type == 4:  # SLEEPTYPEREM - 快速眼动
                sleep_by_day[day_key]["rem"] += total_minutes
            
            sleep_by_day[day_key]["duration"] += total_minutes
            sleep_by_day[day_key]["total"] += total_minutes
            
            # 添加时间段
            sleep_by_day[day_key]["periods"].append({
                "type": sleep_type,
                "start": happen_date,
                "end": item.get("endTime", happen_date),
                "duration": total_minutes
            })
    
    return list(sleep_by_day.values())


def convert_qring_activity_to_api(qring_data):
    """
    将 Qring 活动数据转换为 API 格式
    
    Qring 格式: {totalStepCount, runStepCount, calories, distance, activeTime, happenDate}
    API 格式: {day, totalStepCount, runStepCount, calories, distance, activeTime, happenDate}
    """
    # 按日期分组并汇总
    activity_by_day = {}
    
    for item in qring_data:
        if isinstance(item, dict):
            happen_date = item.get("happenDate", "")
            if happen_date:
                try:
                    dt = datetime.strptime(happen_date, "%Y-%m-%d %H:%M:%S")
                    day_key = dt.strftime("%Y-%m-%d")
                except:
                    day_key = date.today().strftime("%Y-%m-%d")
            else:
                day_key = date.today().strftime("%Y-%m-%d")
            
            if day_key not in activity_by_day:
                activity_by_day[day_key] = {
                    "day": day_key,
                    "totalStepCount": 0,
                    "runStepCount": 0,
                    "calories": 0.0,
                    "distance": 0,
                    "activeTime": 0,
                    "happenDate": happen_date  # 使用第一个记录的happenDate
                }
            
            activity_by_day[day_key]["totalStepCount"] += item.get("totalStepCount", 0)
            activity_by_day[day_key]["runStepCount"] += item.get("runStepCount", 0)
            activity_by_day[day_key]["calories"] += item.get("calories", 0.0)
            activity_by_day[day_key]["distance"] += item.get("distance", 0)
            activity_by_day[day_key]["activeTime"] += item.get("activeTime", 0)
            # 如果有更新的happenDate，更新它
            if happen_date and happen_date > activity_by_day[day_key]["happenDate"]:
                activity_by_day[day_key]["happenDate"] = happen_date
    
    return list(activity_by_day.values())


# ==================== 数据接收接口（来自 iOS App）====================

@app.route('/api/qring/upload', methods=['POST'])
def upload_qring_data():
    """接收来自 iOS App 的 Qring 数据"""
    try:
        # 获取客户端IP和标识来源
        client_ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'Unknown')
        is_mobile = 'iOS' in user_agent or 'iPhone' in user_agent or 'iPad' in user_agent or client_ip.startswith('10.') or client_ip.startswith('192.168.')
        source = "📱 手机App" if is_mobile else "💻 Web前端"
        
        print(f"\n{'='*60}")
        print(f"📥 [上传接口] 收到请求")
        print(f"   来源: {source}")
        print(f"   客户端IP: {client_ip}")
        print(f"   User-Agent: {user_agent}")
        print(f"   请求方法: {request.method}")
        print(f"   请求路径: {request.path}")
        print(f"   请求时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
        print(f"{'='*60}")
        
        data = request.json
        
        if not data:
            print(f"\n❌ {source} 上传失败: 无数据 (IP: {client_ip})")
            print(f"   请求头: {dict(request.headers)}")
            print(f"   请求体: {request.get_data(as_text=True)[:200]}")
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        data_type = data.get("type")
        qring_data = data.get("data", [])
        
        print(f"\n{'='*60}")
        print(f"{source} 数据上传")
        print(f"   客户端IP: {client_ip}")
        print(f"   数据类型: {data_type}")
        print(f"   数据条数: {len(qring_data)}")
        print(f"   接收时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
        print(f"{'='*60}")
        
        if not data_type:
            return jsonify({"success": False, "error": "Missing data type"}), 400
        
        # 根据数据类型处理
        if data_type == "heartrate":
            print(f"\n{'='*60}")
            print(f"📥 收到心率数据上传请求")
            print(f"   原始数据条数: {len(qring_data)}")
            print(f"   接收时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
            
            # 打印原始数据示例（用于调试）
            if qring_data and len(qring_data) > 0:
                print(f"   原始数据示例（前3条）: {qring_data[:3]}")
                # 检查原始数据中的心率值
                sample_heartrates = [item.get("heartrate", item.get("heartRate", item.get("bpm", "N/A"))) for item in qring_data[:10]]
                print(f"   原始数据心率值示例（前10条）: {sample_heartrates}")
                
                # 检查26号12-14点的数据
                target_data = []
                for item in qring_data:
                    if isinstance(item, dict):
                        date_str = item.get("date", "")
                        if "2025-12-26" in date_str:
                            try:
                                if " " in date_str:
                                    time_str = date_str.split(" ")[1]
                                    hour = int(time_str.split(":")[0])
                                    if 12 <= hour < 14:
                                        target_data.append(item)
                            except:
                                pass
                
                if target_data:
                    print(f"   📋 [后端接收检查] 26号12-14点数据: {len(target_data)} 条")
                    print(f"   前5条数据:")
                    for i, item in enumerate(target_data[:5]):
                        date_str = item.get("date", "N/A")
                        heartrate = item.get("heartrate", item.get("heartRate", item.get("bpm", "N/A")))
                        hr_id = item.get("hrId", "N/A")
                        print(f"      [{i}] date={date_str}, heartrate={heartrate}, hrId={hr_id}")
                    
                    # 统计非0值
                    non_zero_count = 0
                    for item in target_data:
                        hr_value = item.get("heartrate") or item.get("heartRate") or item.get("bpm") or 0
                        if isinstance(hr_value, str):
                            try:
                                hr_value = int(hr_value)
                            except:
                                hr_value = 0
                        if hr_value and hr_value != 0:
                            non_zero_count += 1
                    print(f"   📋 [后端接收检查] 26号12-14点数据中，非0值: {non_zero_count} / {len(target_data)}")
                    
                    if non_zero_count == 0:
                        print(f"   ⚠️ [后端警告] 26号12-14点的所有数据心率值都是0！")
                else:
                    print(f"   📋 [后端接收检查] 26号12-14点数据: 0 条（未找到）")
            
            # 转换并存储（转换函数内部已过滤未来时间数据）
            print(f"   🔄 开始转换数据...")
            converted_data = convert_qring_heartrate_to_api(qring_data)
            print(f"   ✅ 转换后数据条数: {len(converted_data)}")
            if converted_data:
                print(f"   📋 转换后数据示例（前5条）:")
                for i, item in enumerate(converted_data[:5]):
                    print(f"      [{i}] timestamp={item.get('timestamp', 'N/A')}, bpm={item.get('bpm', 'N/A')}, hrId={item.get('hrId', 'N/A')}")
                # 统计转换后的数据
                zero_count = len([x for x in converted_data if x.get('bpm', 0) == 0])
                non_zero_count = len([x for x in converted_data if x.get('bpm', 0) > 0])
                print(f"   📊 转换后数据统计: 非0值={non_zero_count}条, 0值={zero_count}条")
            
            # 再次过滤未来时间数据（双重保险）
            now = get_local_time()
            filtered_data = []
            future_filtered = 0
            for item in converted_data:
                try:
                    item_time = datetime.fromisoformat(item.get("timestamp", ""))
                    # 过滤掉超过当前时间5分钟以上的数据
                    if item_time > now + timedelta(minutes=5):
                        future_filtered += 1
                        continue
                    filtered_data.append(item)
                except:
                    # 如果时间解析失败，保留数据（可能是格式问题）
                    filtered_data.append(item)
            
            if future_filtered > 0:
                print(f"   ⚠️ 额外过滤掉未来时间数据: {future_filtered} 条")
            
            converted_data = filtered_data
            
            # 分析新数据的时间戳范围
            if converted_data:
                timestamps = [item.get("timestamp", "") for item in converted_data]
                valid_timestamps = [ts for ts in timestamps if ts]
                if valid_timestamps:
                    try:
                        times = [datetime.fromisoformat(ts) for ts in valid_timestamps]
                        min_time = min(times)
                        max_time = max(times)
                        now = get_local_time()
                        print(f"   新数据时间范围: {min_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {max_time.strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"   最新数据距离现在: {(now - max_time).total_seconds() / 60:.1f} 分钟")
                        
                        # 检查有效数据（bpm>0）
                        valid_data = [item for item in converted_data if item.get("bpm", 0) > 0]
                        if valid_data:
                            valid_times = [datetime.fromisoformat(item.get("timestamp", "")) for item in valid_data if item.get("timestamp")]
                            if valid_times:
                                latest_valid = max(valid_times)
                                print(f"   最新有效数据(bpm>0): {latest_valid.strftime('%Y-%m-%d %H:%M:%S')}, 距离现在: {(now - latest_valid).total_seconds() / 60:.1f} 分钟")
                            print(f"   有效数据条数(bpm>0): {len(valid_data)} / {len(converted_data)}")
                    except Exception as e:
                        print(f"   ⚠️ 时间戳分析错误: {e}")
            
            # 去重：基于 timestamp 和 hrId 的唯一性（而不是 bpm，因为同一时间点可能有不同的hrId）
            # 先保留最近的数据（例如最近7天）
            cutoff = get_local_time() - timedelta(days=7)
            existing_data = [
                item for item in data_store["heartrate"]
                if parse_datetime_with_tz(item["timestamp"]) > cutoff
            ]
            print(f"   现有数据(最近7天): {len(existing_data)} 条")
            
            # 不清理数据，保留所有数据（包括时间戳为00:00:00和数值为0的数据）
            # 让数据如实反映设备记录的情况，方便后端验证数据缺失和问题
            cleaned_data = existing_data
            
            # 使用字典去重（key: (timestamp, hrId)）
            # 优先保留非0值数据：如果新数据的bpm>0，即使key已存在也更新
            unique_data = {}
            for item in cleaned_data:
                key = (item.get("timestamp"), item.get("hrId", 0))
                unique_data[key] = item
            
            # 添加新数据（如果不存在，或新数据是非0值则更新）
            new_count = 0
            duplicate_count = 0
            updated_count = 0
            for item in converted_data:
                key = (item.get("timestamp"), item.get("hrId", 0))
                new_bpm = item.get("bpm", 0)
                
                if key not in unique_data:
                    unique_data[key] = item
                    new_count += 1
                else:
                    # 如果已存在，检查是否需要更新（新数据是非0值，旧数据是0值）
                    old_item = unique_data[key]
                    old_bpm = old_item.get("bpm", 0)
                    
                    if new_bpm > 0 and old_bpm == 0:
                        # 新数据是非0值，旧数据是0值，更新
                        unique_data[key] = item
                        updated_count += 1
                    elif new_bpm == 0 and old_bpm > 0:
                        # 新数据是0值，旧数据是非0值，保留旧数据
                        duplicate_count += 1
                    else:
                        # 其他情况（都是0或都是非0），保留旧数据
                        duplicate_count += 1
            
            data_store["heartrate"] = list(unique_data.values())
            data_store["last_update"]["heartrate"] = get_local_time().isoformat()
            
            print(f"   新增: {new_count} 条, 更新(0→非0): {updated_count} 条, 重复: {duplicate_count} 条")
            print(f"   去重后总数: {len(data_store['heartrate'])} 条")
            
            # 检查最终数据的最新时间戳
            if data_store["heartrate"]:
                final_timestamps = [item.get("timestamp", "") for item in data_store["heartrate"]]
                valid_final = [datetime.fromisoformat(ts) for ts in final_timestamps if ts]
                if valid_final:
                    latest_final = max(valid_final)
                    now = get_local_time()
                    print(f"   最终数据最新时间戳: {latest_final.strftime('%Y-%m-%d %H:%M:%S')}, 距离现在: {(now - latest_final).total_seconds() / 60:.1f} 分钟")
                    
                    # 检查最新有效数据
                    final_valid = [item for item in data_store["heartrate"] if item.get("bpm", 0) > 0]
                    if final_valid:
                        valid_times = [datetime.fromisoformat(item.get("timestamp", "")) for item in final_valid if item.get("timestamp")]
                        if valid_times:
                            latest_valid_final = max(valid_times)
                            print(f"   最终最新有效数据(bpm>0): {latest_valid_final.strftime('%Y-%m-%d %H:%M:%S')}, 距离现在: {(now - latest_valid_final).total_seconds() / 60:.1f} 分钟")
            
            print(f"{'='*60}\n")
            
        elif data_type == "sleep":
            print(f"\n{'='*60}")
            print(f"📥 收到睡眠数据上传请求")
            print(f"   原始数据条数: {len(qring_data)}")
            print(f"   接收时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
            
            converted_data = convert_qring_sleep_to_api(qring_data)
            print(f"   转换后数据条数: {len(converted_data)}")
            
            if converted_data:
                days = [item.get("day", "") for item in converted_data]
                print(f"   数据日期范围: {min(days) if days else 'N/A'} ~ {max(days) if days else 'N/A'}")
                total_duration = sum(item.get("duration", 0) for item in converted_data)
                total_deep = sum(item.get("deepSleep", 0) for item in converted_data)
                print(f"   总睡眠时长: {total_duration} 分钟 ({total_duration/60:.1f} 小时)")
                print(f"   总深度睡眠: {total_deep} 分钟 ({total_deep/60:.1f} 小时)")
            
            # 合并或更新同一天的数据
            existing_days = {item["day"]: item for item in data_store["sleep"]}
            existing_count = len(existing_days)
            for item in converted_data:
                existing_days[item["day"]] = item
            new_count = len(converted_data) - (existing_count - len(existing_days))
            data_store["sleep"] = list(existing_days.values())
            data_store["last_update"]["sleep"] = get_local_time().isoformat()
            print(f"   现有记录数: {existing_count} 条")
            print(f"   新增/更新: {new_count} 条")
            print(f"   更新后总数: {len(data_store['sleep'])} 条")
            print(f"{'='*60}\n")
            
        elif data_type == "activity":
            print(f"\n{'='*60}")
            print(f"📥 收到活动数据上传请求")
            print(f"   原始数据条数: {len(qring_data)}")
            print(f"   接收时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
            
            converted_data = convert_qring_activity_to_api(qring_data)
            print(f"   转换后数据条数: {len(converted_data)}")
            
            if converted_data:
                days = [item.get("day", "") for item in converted_data]
                print(f"   数据日期范围: {min(days) if days else 'N/A'} ~ {max(days) if days else 'N/A'}")
                total_steps = sum(item.get("totalStepCount", 0) for item in converted_data)
                total_calories = sum(item.get("calories", 0) for item in converted_data)
                total_distance = sum(item.get("distance", 0) for item in converted_data)
                print(f"   总步数: {total_steps:,} 步")
                print(f"   总卡路里: {total_calories:.0f} 卡")
                print(f"   总距离: {total_distance} 米 ({total_distance/1000:.2f} 公里)")
            
            # 合并或更新同一天的数据
            existing_days = {item["day"]: item for item in data_store["activity"]}
            existing_count = len(existing_days)
            for item in converted_data:
                existing_days[item["day"]] = item
            new_count = len(converted_data) - (existing_count - len(existing_days))
            data_store["activity"] = list(existing_days.values())
            data_store["last_update"]["activity"] = get_local_time().isoformat()
            print(f"   现有记录数: {existing_count} 条")
            print(f"   新增/更新: {new_count} 条")
            print(f"   更新后总数: {len(data_store['activity'])} 条")
            print(f"{'='*60}\n")
            
        elif data_type == "manual_measurement":
            # 主动测量数据（单次测量、实时监测）
            # 确保 manual_measurements 键存在
            if "manual_measurements" not in data_store:
                data_store["manual_measurements"] = []
            
            for item in qring_data:
                # 确保 item 是字典类型
                if not isinstance(item, dict):
                    continue
                # 添加接收时间戳
                item["received_at"] = get_local_time().isoformat()
            
            data_store["manual_measurements"].extend(qring_data)
            
            # 保留最近的数据（例如最近7天）
            cutoff = get_local_time() - timedelta(days=7)
            filtered_measurements = []
            for item in data_store["manual_measurements"]:
                try:
                    # 获取时间戳
                    ts_str = item.get("received_at") or item.get("timestamp") or get_local_time().isoformat()
                    # 解析时间戳（处理不同的格式）
                    if isinstance(ts_str, str):
                        # 尝试解析 ISO 格式
                        try:
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        except:
                            # 如果不是 ISO 格式，尝试其他格式
                            try:
                                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                            except:
                                ts = get_local_time()
                    else:
                        ts = get_local_time()
                    
                    if ts > cutoff:
                        filtered_measurements.append(item)
                except Exception as e:
                    print(f"处理测量数据项时出错: {e}, 数据: {item}")
                    # 如果解析失败，保留该项（避免数据丢失）
                    filtered_measurements.append(item)
            
            data_store["manual_measurements"] = filtered_measurements
            data_store["last_update"]["manual_measurements"] = get_local_time().isoformat()
            print(f"\n{'='*60}")
            print(f"📥 收到主动测量数据上传请求")
            print(f"   原始数据条数: {len(qring_data)}")
            print(f"   接收时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
            print(f"   更新前总数: {len(data_store['manual_measurements']) - len(qring_data)} 条")
            print(f"   更新后总数: {len(data_store['manual_measurements'])} 条")
            print(f"{'='*60}\n")
            
        elif data_type in ["exercise", "sport_plus", "sedentary"]:
            # 运动记录、运动+、久坐提醒数据
            # 直接追加，基于唯一标识去重
            if data_type == "exercise":
                # 运动记录：基于 startTime 去重
                cutoff = get_local_time() - timedelta(days=7)
                existing_data = [
                    item for item in data_store.get(data_type, [])
                    if parse_datetime_with_tz(item.get("startTime", get_local_time().isoformat())) > cutoff
                ]
                unique_data = {item.get("startTime", ""): item for item in existing_data}
                for item in qring_data:
                    start_time = item.get("startTime", "")
                    if start_time and start_time not in unique_data:
                        unique_data[start_time] = item
                data_store[data_type] = list(unique_data.values())
            elif data_type == "sport_plus":
                # 运动+：基于 startTime 去重
                cutoff = get_local_time() - timedelta(days=7)
                existing_data = [
                    item for item in data_store.get(data_type, [])
                    if parse_datetime_with_tz(item.get("startTime", get_local_time().isoformat())) > cutoff
                ]
                unique_data = {item.get("startTime", ""): item for item in existing_data}
                for item in qring_data:
                    start_time = item.get("startTime", "")
                    if start_time and start_time not in unique_data:
                        unique_data[start_time] = item
                data_store[data_type] = list(unique_data.values())
            elif data_type == "sedentary":
                # 久坐提醒：基于 (date, endTime) 去重
                cutoff = get_local_time() - timedelta(days=7)
                existing_data = [
                    item for item in data_store.get(data_type, [])
                    if parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) > cutoff
                ]
                unique_data = {}
                for item in existing_data:
                    key = (item.get("date", ""), item.get("endTime", ""))
                    unique_data[key] = item
                for item in qring_data:
                    key = (item.get("date", ""), item.get("endTime", ""))
                    if key not in unique_data:
                        unique_data[key] = item
                data_store[data_type] = list(unique_data.values())
            
            data_store["last_update"][data_type] = get_local_time().isoformat()
            print(f"\n{'='*60}")
            print(f"📥 收到 {data_type} 数据上传请求")
            print(f"   原始数据条数: {len(qring_data)}")
            print(f"   接收时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
            print(f"   新增: {len(qring_data)} 条")
            print(f"   去重后总数: {len(data_store[data_type])} 条")
            if data_type == "exercise" and data_store[data_type]:
                total_duration = sum(item.get("duration", 0) for item in data_store[data_type])
                print(f"   总运动时长: {total_duration} 分钟 ({total_duration/60:.1f} 小时)")
            print(f"{'='*60}\n")
        
        elif data_type in ["user_info", "target_info"]:
            # 用户信息和目标设置：只保留最新一条
            if qring_data and len(qring_data) > 0:
                data_store[data_type] = [qring_data[0]]  # 只保留最新一条
                data_store["last_update"][data_type] = get_local_time().isoformat()
                print(f"{data_type} 数据已更新")
        
        elif data_type in ["blood_pressure", "blood_oxygen", "temperature", "stress", "hrv"]:
            # 直接存储其他类型数据，但需要去重
            # 对于 stress 和 hrv，基于唯一ID去重（避免同一天不同时间点的数据被去重）
            if data_type in ["stress", "hrv"]:
                # 保留最近的数据（例如最近7天）
                cutoff = get_local_time() - timedelta(days=7)
                existing_data = [
                    item for item in data_store.get(data_type, [])
                    if parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) > cutoff
                ]
                
                # 使用字典去重（key: (date, id) 或 (date, stressId/hrvId)）
                unique_data = {}
                for item in existing_data:
                    # 使用唯一ID作为去重key（如果有的话）
                    unique_id = item.get("stressId" if data_type == "stress" else "hrvId", None)
                    if unique_id is not None:
                        key = (item.get("date", ""), unique_id)
                    else:
                        # 如果没有ID，使用 (date, value) 作为备选
                        key = (item.get("date", ""), item.get("stress" if data_type == "stress" else "hrv", 0))
                    unique_data[key] = item
                
                # 过滤未来时间数据
                now = get_local_time()
                filtered_data = []
                future_filtered = 0
                for item in qring_data:
                    try:
                        date_str = item.get("date", "")
                        if date_str:
                            if "T" in date_str:
                                item_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            else:
                                item_time = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                            # 过滤掉超过当前时间5分钟以上的数据
                            if item_time > now + timedelta(minutes=5):
                                future_filtered += 1
                                continue
                        filtered_data.append(item)
                    except:
                        # 如果时间解析失败，保留数据
                        filtered_data.append(item)
                
                if future_filtered > 0:
                    print(f"   ⚠️ 过滤掉未来时间数据: {future_filtered} 条")
                
                # 检查26号14点的数据（用于调试）
                target_data = []
                for item in filtered_data:
                    date_str = item.get("date", "")
                    if "2025-12-26" in date_str and "14:" in date_str:
                        target_data.append(item)
                
                if target_data:
                    print(f"   📋 [后端接收检查] 26号14点数据: {len(target_data)} 条")
                    for i, item in enumerate(target_data[:5]):
                        date_str = item.get("date", "N/A")
                        value = item.get("stress" if data_type == "stress" else "hrv", "N/A")
                        item_id = item.get("stressId" if data_type == "stress" else "hrvId", "N/A")
                        print(f"      [{i}] date={date_str}, {data_type}={value}, id={item_id}")
                
                # 添加新数据（如果不存在，或新数据是非0值则更新）
                new_count = 0
                duplicate_count = 0
                updated_count = 0
                for item in filtered_data:
                    unique_id = item.get("stressId" if data_type == "stress" else "hrvId", None)
                    if unique_id is not None:
                        key = (item.get("date", ""), unique_id)
                    else:
                        key = (item.get("date", ""), item.get("stress" if data_type == "stress" else "hrv", 0))
                    
                    # 获取新数据的值
                    new_value = item.get("stress" if data_type == "stress" else "hrv", 0)
                    
                    if key not in unique_data:
                        unique_data[key] = item
                        new_count += 1
                    else:
                        # 如果已存在，检查是否需要更新（新数据是非0值，旧数据是0值）
                        old_item = unique_data[key]
                        old_value = old_item.get("stress" if data_type == "stress" else "hrv", 0)
                        
                        if new_value > 0 and old_value == 0:
                            # 新数据是非0值，旧数据是0值，更新
                            unique_data[key] = item
                            updated_count += 1
                        elif new_value == 0 and old_value > 0:
                            # 新数据是0值，旧数据是非0值，保留旧数据
                            duplicate_count += 1
                        else:
                            # 其他情况（都是0或都是非0），保留旧数据
                            duplicate_count += 1
                
                existing_count = len(existing_data)
                new_count = len(qring_data)
                data_store[data_type] = list(unique_data.values())
                print(f"\n{'='*60}")
                print(f"📥 收到 {data_type} 数据上传请求")
                print(f"   原始数据条数: {new_count}")
                print(f"   接收时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
                print(f"   现有数据(最近7天): {existing_count} 条")
                print(f"   新增: {new_count} 条")
                print(f"   去重后总数: {len(data_store[data_type])} 条")
                if data_store[data_type]:
                    if data_type == "stress":
                        valid_data = [item for item in data_store[data_type] if item.get("stress", 0) > 0]
                        if valid_data:
                            avg_stress = sum(item.get("stress", 0) for item in valid_data) / len(valid_data)
                            max_stress = max(item.get("stress", 0) for item in valid_data)
                            min_stress = min(item.get("stress", 0) for item in valid_data)
                            print(f"   有效数据: {len(valid_data)} 条")
                            print(f"   平均压力值: {avg_stress:.1f}")
                            print(f"   最高压力值: {max_stress}")
                            print(f"   最低压力值: {min_stress}")
                    elif data_type == "hrv":
                        valid_data = [item for item in data_store[data_type] if item.get("hrv", 0) > 0]
                        if valid_data:
                            avg_hrv = sum(item.get("hrv", 0) for item in valid_data) / len(valid_data)
                            max_hrv = max(item.get("hrv", 0) for item in valid_data)
                            min_hrv = min(item.get("hrv", 0) for item in valid_data)
                            print(f"   有效数据: {len(valid_data)} 条")
                            print(f"   平均HRV值: {avg_hrv:.1f}")
                            print(f"   最高HRV值: {max_hrv}")
                            print(f"   最低HRV值: {min_hrv}")
                print(f"{'='*60}\n")
            elif data_type == "temperature":
                # 体温数据去重：基于 (date, temperature) 去重
                cutoff = get_local_time() - timedelta(days=7)
                existing_data = [
                    item for item in data_store.get(data_type, [])
                    if parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) > cutoff
                ]
                
                unique_data = {}
                for item in existing_data:
                    key = (item.get("date", ""), item.get("temperature", 0))
                    unique_data[key] = item
                
                # 过滤未来时间数据
                now = get_local_time()
                filtered_data = []
                future_filtered = 0
                for item in qring_data:
                    try:
                        date_str = item.get("date", "")
                        if date_str:
                            if "T" in date_str:
                                item_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            else:
                                item_time = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                            # 过滤掉超过当前时间5分钟以上的数据
                            if item_time > now + timedelta(minutes=5):
                                future_filtered += 1
                                continue
                        filtered_data.append(item)
                    except:
                        filtered_data.append(item)
                
                if future_filtered > 0:
                    print(f"   ⚠️ 过滤掉未来时间数据: {future_filtered} 条")
                
                # 添加新数据（如果不存在，或新数据是非0值则更新）
                new_count = 0
                duplicate_count = 0
                updated_count = 0
                for item in filtered_data:
                    key = (item.get("date", ""), item.get("temperature", 0))
                    new_value = item.get("temperature", 0)
                    
                    if key not in unique_data:
                        unique_data[key] = item
                        new_count += 1
                    else:
                        # 如果已存在，检查是否需要更新（新数据是非0值，旧数据是0值）
                        old_item = unique_data[key]
                        old_value = old_item.get("temperature", 0)
                        
                        if new_value > 0 and old_value == 0:
                            unique_data[key] = item
                            updated_count += 1
                        elif new_value == 0 and old_value > 0:
                            duplicate_count += 1
                        else:
                            duplicate_count += 1
                
                existing_count = len(existing_data)
                data_store[data_type] = list(unique_data.values())
                print(f"\n{'='*60}")
                print(f"📥 收到 {data_type} 数据上传请求")
                print(f"   原始数据条数: {len(qring_data)}")
                print(f"   接收时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
                print(f"   现有数据(最近7天): {existing_count} 条")
                print(f"   新增: {new_count} 条, 更新(0→非0): {updated_count} 条, 重复: {duplicate_count} 条")
                print(f"   去重后总数: {len(data_store[data_type])} 条")
                if data_store[data_type]:
                    avg_temp = sum(item.get("temperature", 0) for item in data_store[data_type]) / len(data_store[data_type])
                    print(f"   平均体温: {avg_temp:.2f}°C")
                print(f"{'='*60}\n")
            elif data_type == "blood_oxygen":
                # 血氧数据去重：基于 (date, soa2) 去重，如果同一时间点有多个值，保留最新的
                cutoff = get_local_time() - timedelta(days=7)
                existing_data = [
                    item for item in data_store.get(data_type, [])
                    if parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) > cutoff
                ]
                
                # 使用字典去重，key为date，保留最新的数据
                unique_data = {}
                for item in existing_data:
                    date_key = item.get("date", "")
                    if date_key:
                        # 如果已存在，比较时间戳，保留更新的
                        if date_key not in unique_data:
                            unique_data[date_key] = item
                        else:
                            # 保留时间戳更晚的数据
                            existing_time = datetime.fromisoformat(unique_data[date_key].get("date", ""))
                            new_time = datetime.fromisoformat(item.get("date", ""))
                            if new_time > existing_time:
                                unique_data[date_key] = item
                
                # 过滤未来时间数据
                now = get_local_time()
                filtered_data = []
                future_filtered = 0
                for item in qring_data:
                    try:
                        date_str = item.get("date", "")
                        if date_str:
                            if "T" in date_str:
                                item_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                            else:
                                item_time = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                            # 过滤掉超过当前时间5分钟以上的数据
                            if item_time > now + timedelta(minutes=5):
                                future_filtered += 1
                                continue
                        filtered_data.append(item)
                    except:
                        filtered_data.append(item)
                
                if future_filtered > 0:
                    print(f"   ⚠️ 过滤掉未来时间数据: {future_filtered} 条")
                
                # 添加新数据（如果不存在，或新数据是非0值则更新）
                new_count = 0
                duplicate_count = 0
                updated_count = 0
                for item in filtered_data:
                    date_key = item.get("date", "")
                    if date_key:
                        new_value = item.get("bloodOxygen") or item.get("blood_oxygen") or item.get("soa2", 0)
                        
                        if date_key not in unique_data:
                            unique_data[date_key] = item
                            new_count += 1
                        else:
                            # 如果已存在，检查是否需要更新
                            old_item = unique_data[date_key]
                            old_value = old_item.get("bloodOxygen") or old_item.get("blood_oxygen") or old_item.get("soa2", 0)
                            
                            # 比较时间戳，保留更新的
                            try:
                                existing_time = datetime.fromisoformat(unique_data[date_key].get("date", ""))
                                new_time = datetime.fromisoformat(item.get("date", ""))
                                
                                if new_time > existing_time:
                                    # 新数据时间更晚，更新
                                    unique_data[date_key] = item
                                    updated_count += 1
                                elif new_time == existing_time:
                                    # 时间相同，优先保留非0值
                                    if new_value > 0 and old_value == 0:
                                        unique_data[date_key] = item
                                        updated_count += 1
                                    else:
                                        duplicate_count += 1
                                else:
                                    duplicate_count += 1
                            except:
                                # 时间解析失败，优先保留非0值
                                if new_value > 0 and old_value == 0:
                                    unique_data[date_key] = item
                                    updated_count += 1
                                else:
                                    duplicate_count += 1
                
                existing_count = len(existing_data)
                data_store[data_type] = list(unique_data.values())
                data_store["last_update"][data_type] = get_local_time().isoformat()
                print(f"\n{'='*60}")
                print(f"📥 收到 {data_type} 数据上传请求")
                print(f"   原始数据条数: {len(qring_data)}")
                print(f"   接收时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
                print(f"   现有数据(最近7天): {existing_count} 条")
                print(f"   新增: {new_count} 条, 更新(0→非0): {updated_count} 条, 重复: {duplicate_count} 条")
                print(f"   去重后总数: {len(data_store[data_type])} 条")
                if data_store[data_type]:
                    valid_data = [item for item in data_store[data_type] if item.get("soa2", 0) > 0]
                    if valid_data:
                        avg_soa2 = sum(item.get("soa2", 0) for item in valid_data) / len(valid_data)
                        max_soa2 = max(item.get("soa2", 0) for item in valid_data)
                        min_soa2 = min(item.get("soa2", 0) for item in valid_data)
                        print(f"   有效数据: {len(valid_data)} 条")
                        print(f"   平均血氧: {avg_soa2:.1f}%")
                        print(f"   最高血氧: {max_soa2}%")
                        print(f"   最低血氧: {min_soa2}%")
                print(f"{'='*60}\n")
            else:
                # 其他类型直接追加（暂时不去重）
                data_store[data_type].extend(qring_data)
            
            data_store["last_update"][data_type] = get_local_time().isoformat()
        
        # 保存到文件
        save_data()
        
        return jsonify({
            "success": True,
            "message": f"Received {len(qring_data)} {data_type} records",
            "timestamp": get_local_time().isoformat()
        })
        
    except Exception as e:
        print(f"上传数据错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ==================== 前端 API 接口 ====================

@app.route('/', methods=['GET'])
def root():
    """根路径，返回 API 信息"""
    return jsonify({
        "service": "Qring API Server",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/api/health",
            "upload": "/api/qring/upload",
            "stats": "/api/stats",
            "heartrate": "/api/heartrate",
            "hrv": "/api/hrv",
            "stress": "/api/stress",
            "blood_oxygen": "/api/blood-oxygen",
            "activity": "/api/daily-activity",
            "sleep": "/api/sleep",
        }
    })

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "timestamp": get_local_time().isoformat(),
        "version": "1.0.0",
        "data_file": DATA_FILE,
        "data_file_exists": os.path.exists(DATA_FILE)
    })

@app.errorhandler(404)
def not_found(error):
    """404错误处理"""
    return jsonify({"error": "Not found", "message": "The requested resource was not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    """500错误处理"""
    return jsonify({"error": "Internal server error", "message": "An internal error occurred"}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """全局异常处理"""
    # 生产环境不暴露详细错误信息
    if os.getenv('FLASK_ENV', 'development') == 'production':
        return jsonify({"error": "Internal server error"}), 500
    else:
        # 开发环境显示详细错误
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/api/heartrate', methods=['GET'])
def get_heartrate():
    """获取心率数据"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    hours = request.args.get('hours', 168, type=int)  # 默认7天（168小时）
    # 默认包含所有数据（包括0值），确保横坐标连续无断档
    include_zero = request.args.get('include_zero', 'true').lower() == 'true'  # 默认包含心率=0的数据
    
    cutoff_time = get_local_time() - timedelta(hours=hours)
    now = get_local_time()
    
    print(f"\n📤 {source} 请求: /api/heartrate")
    print(f"   客户端IP: {client_ip}")
    print(f"   请求参数: hours={hours}, include_zero={include_zero}")
    print(f"   当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
    print(f"   数据总数: {len(data_store['heartrate'])} 条")
    
    filtered_data = [
        item for item in data_store["heartrate"]
        if parse_datetime_with_tz(item["timestamp"]) >= cutoff_time
        and parse_datetime_with_tz(item["timestamp"]) <= now  # 过滤掉未来时间戳的数据
    ]
    
    print(f"   时间过滤后: {len(filtered_data)} 条 (cutoff: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')})")
    
    # 如果不包含0值数据，过滤掉心率=0的记录（但默认包含，确保横坐标连续）
    if not include_zero:
        before_count = len(filtered_data)
        filtered_data = [item for item in filtered_data if item.get("bpm", 0) > 0]
        print(f"   过滤0值后: {len(filtered_data)} 条 (过滤了 {before_count - len(filtered_data)} 条)")
    
    # 按时间排序
    filtered_data.sort(key=lambda x: x["timestamp"])
    
    # 检查返回数据的时间范围
    if filtered_data:
        first_time = datetime.fromisoformat(filtered_data[0]["timestamp"])
        last_time = datetime.fromisoformat(filtered_data[-1]["timestamp"])
        print(f"   返回数据时间范围: {first_time.strftime('%Y-%m-%d %H:%M:%S')} ~ {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   最新数据距离现在: {(now - last_time).total_seconds() / 60:.1f} 分钟")
        
        # 打印返回数据示例
        print(f"   📋 返回数据示例（前5条）:")
        for i, item in enumerate(filtered_data[:5]):
            print(f"      [{i}] timestamp={item.get('timestamp', 'N/A')}, bpm={item.get('bpm', 'N/A')}, hrId={item.get('hrId', 'N/A')}")
        print(f"   📋 返回数据示例（后5条）:")
        for i, item in enumerate(filtered_data[-5:]):
            idx = len(filtered_data) - 5 + i
            print(f"      [{idx}] timestamp={item.get('timestamp', 'N/A')}, bpm={item.get('bpm', 'N/A')}, hrId={item.get('hrId', 'N/A')}")
    else:
        print(f"   ⚠️ 警告: 没有数据返回给前端！")
    
    valid_count = len([x for x in filtered_data if x.get("bpm", 0) > 0])
    print(f"   有效数据(bpm>0): {valid_count} 条")
    print(f"   📤 准备返回给前端: {len(filtered_data)} 条数据")
    print(f"{'='*60}\n")
    
    return jsonify({
        "success": True,
        "data": filtered_data,
        "count": len(filtered_data),
        "valid_count": valid_count,
        "timestamp": get_local_time().isoformat()
    })


@app.route('/api/daily-activity', methods=['GET'])
def get_daily_activity():
    """获取活动数据"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    days = request.args.get('days', 30, type=int)
    
    cutoff_date = date.today() - timedelta(days=days)
    
    filtered_data = [
        item for item in data_store["activity"]
        if datetime.strptime(item["day"], "%Y-%m-%d").date() >= cutoff_date
    ]
    
    # 按日期排序
    filtered_data.sort(key=lambda x: x["day"], reverse=True)
    
    print(f"\n📤 {source} 请求: /api/daily-activity")
    print(f"   客户端IP: {client_ip}")
    print(f"   请求参数: days={days}")
    print(f"   当前时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
    print(f"   数据总数: {len(data_store['activity'])} 条")
    print(f"   返回数据: {len(filtered_data)} 条")
    if filtered_data:
        total_steps = sum(item.get("totalStepCount", 0) for item in filtered_data)
        total_calories = sum(item.get("calories", 0) for item in filtered_data)
        total_distance = sum(item.get("distance", 0) for item in filtered_data)
        print(f"   总步数: {total_steps:,} 步")
        print(f"   总卡路里: {total_calories:.0f} 卡")
        print(f"   总距离: {total_distance} 米 ({total_distance/1000:.2f} 公里)")
    print()
    
    return jsonify({
        "success": True,
        "data": filtered_data,
        "count": len(filtered_data),
        "timestamp": get_local_time().isoformat()
    })


@app.route('/api/daily-readiness', methods=['GET'])
def get_daily_readiness():
    """获取准备度数据（Qring 可能没有，返回空或基于其他数据计算）"""
    # Qring 没有直接的 readiness 数据，可以基于心率、睡眠等计算
    # 这里先返回空数据，前端可以处理
    return jsonify({
        "success": True,
        "data": [],
        "count": 0,
        "timestamp": get_local_time().isoformat(),
        "note": "Qring does not provide readiness data directly"
    })


@app.route('/api/sleep', methods=['GET'])
def get_sleep():
    """获取睡眠数据"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    days = request.args.get('days', 30, type=int)
    
    cutoff_date = date.today() - timedelta(days=days)
    
    filtered_data = [
        item for item in data_store["sleep"]
        if datetime.strptime(item["day"], "%Y-%m-%d").date() >= cutoff_date
    ]
    
    print(f"\n📤 {source} 请求: /api/sleep")
    print(f"   客户端IP: {client_ip}")
    print(f"   请求参数: days={days}")
    print(f"   当前时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
    print(f"   数据总数: {len(data_store['sleep'])} 条")
    print(f"   返回数据: {len(filtered_data)} 条")
    if filtered_data:
        total_duration = sum(item.get("duration", 0) for item in filtered_data)
        total_deep = sum(item.get("deepSleep", 0) for item in filtered_data)
        avg_duration = total_duration / len(filtered_data) if filtered_data else 0
        avg_deep = total_deep / len(filtered_data) if filtered_data else 0
        print(f"   总睡眠时长: {total_duration} 分钟 ({total_duration/60:.1f} 小时)")
        print(f"   总深度睡眠: {total_deep} 分钟 ({total_deep/60:.1f} 小时)")
        print(f"   平均睡眠时长: {avg_duration:.1f} 分钟 ({avg_duration/60:.1f} 小时)")
        print(f"   平均深度睡眠: {avg_deep:.1f} 分钟 ({avg_deep/60:.1f} 小时)")
    print()
    
    # 按日期排序
    filtered_data.sort(key=lambda x: x["day"], reverse=True)
    
    return jsonify({
        "success": True,
        "data": filtered_data,
        "count": len(filtered_data),
        "timestamp": get_local_time().isoformat()
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    stats = {
        "heartrate_count": len(data_store.get("heartrate", [])),
        "activity_count": len(data_store.get("activity", [])),
        "readiness_count": 0,  # Qring 没有
        "sleep_count": len(data_store.get("sleep", [])),
        "hrv_count": len(data_store.get("hrv", [])),
        "stress_count": len(data_store.get("stress", [])),
        "blood_oxygen_count": len(data_store.get("blood_oxygen", [])),
        "temperature_count": len(data_store.get("temperature", [])),
        "exercise_count": len(data_store.get("exercise", [])),
        "sport_plus_count": len(data_store.get("sport_plus", [])),
        "sedentary_count": len(data_store.get("sedentary", [])),
        "manual_measurements_count": len(data_store.get("manual_measurements", [])),
        "last_update": data_store.get("last_update", {})
    }
    
    print(f"\n📊 {source} 请求: /api/stats")
    print(f"   客户端IP: {client_ip}")
    print(f"   请求时间: {get_local_time().strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
    print(f"   心率数据: {stats['heartrate_count']} 条")
    print(f"   活动数据: {stats['activity_count']} 条")
    print(f"   睡眠数据: {stats['sleep_count']} 条")
    print(f"   HRV数据: {stats['hrv_count']} 条")
    print(f"   压力数据: {stats['stress_count']} 条")
    print(f"   血氧数据: {stats['blood_oxygen_count']} 条")
    print(f"   体温数据: {stats['temperature_count']} 条")
    print(f"   运动数据: {stats['exercise_count']} 条")
    print(f"   运动+数据: {stats['sport_plus_count']} 条")
    print(f"   久坐数据: {stats['sedentary_count']} 条")
    print(f"   主动测量: {stats['manual_measurements_count']} 条")
    print(f"   总计: {sum([stats['heartrate_count'], stats['activity_count'], stats['sleep_count'], stats['hrv_count'], stats['stress_count'], stats['blood_oxygen_count'], stats['temperature_count'], stats['exercise_count'], stats['sport_plus_count'], stats['sedentary_count'], stats['manual_measurements_count']])} 条\n")
    
    return jsonify({
        "success": True,
        "data": stats
    })


@app.route('/api/hrv', methods=['GET'])
def get_hrv():
    """获取HRV数据"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    hours = request.args.get('hours', 168, type=int)  # 默认7天
    cutoff_time = get_local_time() - timedelta(hours=hours)
    now = get_local_time()
    
    print(f"\n📤 {source} 请求: /api/hrv")
    print(f"   客户端IP: {client_ip}")
    print(f"   请求参数: hours={hours}")
    print(f"   当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   数据总数: {len(data_store.get('hrv', []))} 条")
    
    filtered_data = [
        item for item in data_store.get("hrv", [])
        if parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) >= cutoff_time
        and parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) <= now  # 过滤掉未来时间戳的数据
    ]
    
    print(f"   时间过滤后: {len(filtered_data)} 条 (cutoff: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')})")
    
    filtered_data.sort(key=lambda x: x.get("date", ""))
    
    if filtered_data:
        valid_data = [item for item in filtered_data if item.get("hrv", 0) > 0]
        print(f"   有效数据(hrv>0): {len(valid_data)} 条")
        if valid_data:
            avg_hrv = sum(item.get("hrv", 0) for item in valid_data) / len(valid_data)
            max_hrv = max(item.get("hrv", 0) for item in valid_data)
            min_hrv = min(item.get("hrv", 0) for item in valid_data)
            print(f"   平均HRV: {avg_hrv:.1f}")
            print(f"   最高HRV: {max_hrv}")
            print(f"   最低HRV: {min_hrv}")
    print()
    
    return jsonify({
        "success": True,
        "data": filtered_data,
        "count": len(filtered_data),
        "timestamp": get_local_time().isoformat()
    })


@app.route('/api/stress', methods=['GET'])
def get_stress():
    """获取压力数据"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    hours = request.args.get('hours', 168, type=int)  # 默认7天
    cutoff_time = get_local_time() - timedelta(hours=hours)
    now = get_local_time()
    
    print(f"\n📤 {source} 请求: /api/stress")
    print(f"   客户端IP: {client_ip}")
    print(f"   请求参数: hours={hours}")
    print(f"   当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   数据总数: {len(data_store.get('stress', []))} 条")
    
    filtered_data = [
        item for item in data_store.get("stress", [])
        if parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) >= cutoff_time
        and parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) <= now  # 过滤掉未来时间戳的数据
    ]
    
    print(f"   时间过滤后: {len(filtered_data)} 条 (cutoff: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')})")
    
    filtered_data.sort(key=lambda x: x.get("date", ""))
    
    if filtered_data:
        valid_data = [item for item in filtered_data if item.get("stress", 0) > 0]
        print(f"   有效数据(stress>0): {len(valid_data)} 条")
        if valid_data:
            avg_stress = sum(item.get("stress", 0) for item in valid_data) / len(valid_data)
            max_stress = max(item.get("stress", 0) for item in valid_data)
            min_stress = min(item.get("stress", 0) for item in valid_data)
            print(f"   平均压力: {avg_stress:.1f}")
            print(f"   最高压力: {max_stress}")
            print(f"   最低压力: {min_stress}")
    print()
    
    return jsonify({
        "success": True,
        "data": filtered_data,
        "count": len(filtered_data),
        "timestamp": get_local_time().isoformat()
    })


@app.route('/api/blood-oxygen', methods=['GET'])
def get_blood_oxygen():
    """获取血氧数据"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    hours = request.args.get('hours', 168, type=int)  # 默认7天
    cutoff_time = get_local_time() - timedelta(hours=hours)
    now = get_local_time()
    
    print(f"\n📤 {source} 请求: /api/blood-oxygen")
    print(f"   客户端IP: {client_ip}")
    print(f"   请求参数: hours={hours}")
    print(f"   当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   数据总数: {len(data_store.get('blood_oxygen', []))} 条")
    
    filtered_data = [
        item for item in data_store.get("blood_oxygen", [])
        if parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) >= cutoff_time
        and parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) <= now  # 过滤掉未来时间戳的数据
    ]
    
    print(f"   时间过滤后: {len(filtered_data)} 条 (cutoff: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')})")
    
    filtered_data.sort(key=lambda x: x.get("date", ""))
    
    if filtered_data:
        valid_data = [item for item in filtered_data if item.get("soa2", 0) > 0]
        print(f"   有效数据(soa2>0): {len(valid_data)} 条")
        if valid_data:
            avg_soa2 = sum(item.get("soa2", 0) for item in valid_data) / len(valid_data)
            max_soa2 = max(item.get("soa2", 0) for item in valid_data)
            min_soa2 = min(item.get("soa2", 0) for item in valid_data)
            print(f"   平均血氧: {avg_soa2:.1f}%")
            print(f"   最高血氧: {max_soa2}%")
            print(f"   最低血氧: {min_soa2}%")
    print()
    
    return jsonify({
        "success": True,
        "data": filtered_data,
        "count": len(filtered_data),
        "timestamp": get_local_time().isoformat()
    })


@app.route('/api/temperature', methods=['GET'])
def get_temperature():
    """获取体温数据"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    hours = request.args.get('hours', 168, type=int)  # 默认7天
    cutoff_time = get_local_time() - timedelta(hours=hours)
    
    print(f"\n📤 {source} 请求: /api/temperature")
    print(f"   客户端IP: {client_ip}")
    
    filtered_data = [
        item for item in data_store.get("temperature", [])
        if parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) >= cutoff_time
    ]
    
    filtered_data.sort(key=lambda x: x.get("date", ""))
    print(f"   返回数据: {len(filtered_data)} 条\n")
    
    return jsonify({
        "success": True,
        "data": filtered_data,
        "count": len(filtered_data),
        "timestamp": get_local_time().isoformat()
    })


@app.route('/api/exercise', methods=['GET'])
def get_exercise():
    """获取运动记录数据"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    hours = request.args.get('hours', 168, type=int)  # 默认7天
    cutoff_time = get_local_time() - timedelta(hours=hours)
    now = get_local_time()
    
    print(f"\n📤 {source} 请求: /api/exercise")
    print(f"   客户端IP: {client_ip}")
    print(f"   请求参数: hours={hours}")
    print(f"   当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   数据总数: {len(data_store.get('exercise', []))} 条")
    
    filtered_data = [
        item for item in data_store.get("exercise", [])
        if parse_datetime_with_tz(item.get("startTime", get_local_time().isoformat())) >= cutoff_time
        and parse_datetime_with_tz(item.get("startTime", get_local_time().isoformat())) <= now  # 过滤掉未来时间戳的数据
    ]
    
    print(f"   时间过滤后: {len(filtered_data)} 条 (cutoff: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')})")
    
    filtered_data.sort(key=lambda x: x.get("startTime", ""))
    
    if filtered_data:
        total_duration = sum(item.get("duration", 0) for item in filtered_data)
        total_calories = sum(item.get("calories", 0) for item in filtered_data)
        print(f"   总运动时长: {total_duration} 分钟 ({total_duration/60:.1f} 小时)")
        print(f"   总卡路里: {total_calories:.0f} 卡")
    print()
    
    return jsonify({
        "success": True,
        "data": filtered_data,
        "count": len(filtered_data),
        "timestamp": get_local_time().isoformat()
    })


@app.route('/api/sport-plus', methods=['GET'])
def get_sport_plus():
    """获取运动+数据"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    hours = request.args.get('hours', 168, type=int)  # 默认7天
    cutoff_time = get_local_time() - timedelta(hours=hours)
    now = get_local_time()
    
    print(f"\n📤 {source} 请求: /api/sport-plus")
    print(f"   客户端IP: {client_ip}")
    print(f"   请求参数: hours={hours}")
    print(f"   当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   数据总数: {len(data_store.get('sport_plus', []))} 条")
    
    filtered_data = [
        item for item in data_store.get("sport_plus", [])
        if parse_datetime_with_tz(item.get("startTime", get_local_time().isoformat())) >= cutoff_time
        and parse_datetime_with_tz(item.get("startTime", get_local_time().isoformat())) <= now  # 过滤掉未来时间戳的数据
    ]
    
    print(f"   时间过滤后: {len(filtered_data)} 条 (cutoff: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')})")
    
    filtered_data.sort(key=lambda x: x.get("startTime", ""))
    
    if filtered_data:
        total_duration = sum(item.get("duration", 0) for item in filtered_data)
        total_calories = sum(item.get("calories", 0) for item in filtered_data)
        avg_hr = sum(item.get("averageHR", 0) for item in filtered_data if item.get("averageHR", 0) > 0) / max(1, len([x for x in filtered_data if x.get("averageHR", 0) > 0]))
        print(f"   总运动时长: {total_duration} 分钟 ({total_duration/60:.1f} 小时)")
        print(f"   总卡路里: {total_calories:.0f} 卡")
        if avg_hr > 0:
            print(f"   平均心率: {avg_hr:.1f} bpm")
    print()
    
    return jsonify({
        "success": True,
        "data": filtered_data,
        "count": len(filtered_data),
        "timestamp": get_local_time().isoformat()
    })


@app.route('/api/sedentary', methods=['GET'])
def get_sedentary():
    """获取久坐提醒数据"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    hours = request.args.get('hours', 168, type=int)  # 默认7天
    cutoff_time = get_local_time() - timedelta(hours=hours)
    now = get_local_time()
    
    print(f"\n📤 {source} 请求: /api/sedentary")
    print(f"   客户端IP: {client_ip}")
    print(f"   请求参数: hours={hours}")
    print(f"   当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')} (新加坡时间)")
    print(f"   数据总数: {len(data_store.get('sedentary', []))} 条")
    
    filtered_data = [
        item for item in data_store.get("sedentary", [])
        if parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) >= cutoff_time
        and parse_datetime_with_tz(item.get("date", get_local_time().isoformat())) <= now  # 过滤掉未来时间戳的数据
    ]
    
    print(f"   时间过滤后: {len(filtered_data)} 条 (cutoff: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')})")
    
    filtered_data.sort(key=lambda x: x.get("date", ""))
    
    if filtered_data:
        total_duration = sum(item.get("duration", 0) for item in filtered_data)
        print(f"   总久坐时长: {total_duration} 分钟 ({total_duration/60:.1f} 小时)")
    print()
    
    return jsonify({
        "success": True,
        "data": filtered_data,
        "count": len(filtered_data),
        "timestamp": get_local_time().isoformat()
    })


@app.route('/api/user-info', methods=['GET'])
def get_user_info():
    """获取用户信息（最新一条）"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    print(f"\n📤 {source} 请求: /api/user-info")
    print(f"   客户端IP: {client_ip}\n")
    
    user_info = data_store.get("user_info", [])
    latest_info = user_info[0] if user_info else None
    
    return jsonify({
        "success": True,
        "data": latest_info,
        "timestamp": get_local_time().isoformat()
    })


@app.route('/api/target-info', methods=['GET'])
def get_target_info():
    """获取目标设置（最新一条）"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    print(f"\n📤 {source} 请求: /api/target-info")
    print(f"   客户端IP: {client_ip}\n")
    
    target_info = data_store.get("target_info", [])
    latest_info = target_info[0] if target_info else None
    
    return jsonify({
        "success": True,
        "data": latest_info,
        "timestamp": get_local_time().isoformat()
    })


@app.route('/api/manual-measurements', methods=['GET'])
def get_manual_measurements():
    """获取主动测量数据"""
    # 获取客户端来源
    source, client_ip = get_client_source()
    
    hours = request.args.get('hours', 24, type=int)  # 默认24小时
    measurement_type = request.args.get('type', None)  # 可选：manual, realtime, one_key
    
    print(f"\n📤 {source} 请求: /api/manual-measurements")
    print(f"   客户端IP: {client_ip}")
    print(f"   请求参数: hours={hours}, type={measurement_type}")
    
    cutoff_time = get_local_time() - timedelta(hours=hours)
    
    filtered_data = [
        item for item in data_store.get("manual_measurements", [])
        if parse_datetime_with_tz(item.get("received_at", item.get("timestamp", get_local_time().isoformat()))) >= cutoff_time
    ]
    
    # 如果指定了测量类型，进行过滤
    if measurement_type:
        filtered_data = [
            item for item in filtered_data
            if item.get("measurementType") == measurement_type
        ]
    
    # 按时间排序（最新的在前）
    filtered_data.sort(key=lambda x: x.get("received_at", x.get("timestamp", "")), reverse=True)
    
    # 统计各种类型的测量数量
    manual_count = len([x for x in filtered_data if x.get("measurementType") == "manual"])
    realtime_count = len([x for x in filtered_data if x.get("measurementType") == "realtime"])
    one_key_count = len([x for x in filtered_data if x.get("measurementType") == "one_key"])
    
    print(f"   返回数据: {len(filtered_data)} 条 (手动: {manual_count}, 实时: {realtime_count}, 一键: {one_key_count})\n")
    
    return jsonify({
        "success": True,
        "data": filtered_data,
        "count": len(filtered_data),
        "manual_count": manual_count,
        "realtime_count": realtime_count,
        "one_key_count": one_key_count,
        "timestamp": get_local_time().isoformat()
    })


if __name__ == '__main__':
    # 加载已有数据
    load_data()
    
    # 从环境变量读取配置，生产环境使用
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5002))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    flask_env = os.getenv('FLASK_ENV', 'development')
    
    # 生产环境自动关闭debug
    if flask_env == 'production':
        debug = False
    
    print("\n" + "="*80)
    print("Qring 数据 API 服务器")
    print("="*80)
    print(f"\n服务器运行在: http://{host}:{port}")
    print("\n数据接收接口（iOS App 使用）:")
    print("  - POST /api/qring/upload - 上传 Qring 数据")
    print("    请求体: {\"type\": \"heartrate|sleep|activity|...\", \"data\": [...]}")
    print("\n前端 API 接口:")
    print("  - GET /api/health - 健康检查")
    print("  - GET /api/heartrate?hours=24 - 心率数据")
    print("  - GET /api/daily-activity?days=30 - 活动数据")
    print("  - GET /api/daily-readiness?days=30 - 准备度数据（Qring 不支持）")
    print("  - GET /api/sleep?days=30 - 睡眠数据")
    print("  - GET /api/stats - 统计信息")
    print(f"\n数据存储: {DATA_FILE}")
    print("="*80 + "\n")
    
    # 开发环境才显示本地 IP 提示
    if flask_env == 'development':
        print("\n⚠️  重要提示：")
        print("   iOS 设备无法访问 localhost，必须使用 Mac 的 IP 地址")
        print("   在 Mac 终端运行: ifconfig | grep 'inet ' | grep -v 127.0.0.1")
        print("   然后在 iOS App 中使用这个 IP 地址作为服务器地址")
        print("="*80 + "\n")
    
    print(f"环境配置:")
    print(f"  FLASK_ENV: {flask_env}")
    print(f"  DEBUG: {debug}")
    print(f"  HOST: {host}")
    print(f"  PORT: {port}")
    print(f"  CORS_ORIGINS: {cors_origins}")
    print("="*80 + "\n")
    
    app.run(host=host, port=port, debug=debug)

