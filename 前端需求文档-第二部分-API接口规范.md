# Qring 健康数据仪表板 - 前端需求文档

## 第二部分：API接口规范

### 2.1 API基础配置

**API基础路径配置：**

前端必须支持可配置的API基础路径，以适配不同的部署场景：

**方式一：相对路径（同源部署）**
- 如果前端和后端部署在同一域名下，使用相对路径：`/api`
- 例如：前端在 `https://example.com`，后端在 `https://example.com/api`
- 代码示例：`const API_BASE = '/api'`

**方式二：环境变量（跨域部署或不同环境）**
- 如果前端和后端部署在不同域名，或需要支持多环境，使用环境变量
- 环境变量名：`VITE_API_BASE`（Vite要求以VITE_开头）
- 代码示例：`const API_BASE = import.meta.env.VITE_API_BASE || '/api'`
- 配置方法：
  - 开发环境：创建 `.env.development` 文件，内容：`VITE_API_BASE=http://localhost:5002/api`
  - 生产环境：创建 `.env.production` 文件，内容：`VITE_API_BASE=https://your-backend-domain.com/api`
  - 或者在部署时设置环境变量

**推荐实现方式：**
```javascript
// 在 Dashboard.jsx 或独立的 config.js 文件中
const API_BASE = import.meta.env.VITE_API_BASE || '/api'
```

**请求方式：** 所有接口使用HTTP GET方法（数据上传由iOS App完成，前端只负责读取）

**响应格式：** 所有接口返回JSON格式数据

**标准响应结构：**
```json
{
  "success": true/false,
  "data": [...],  // 数据数组或对象
  "count": 数字,   // 数据条数（可选）
  "timestamp": "ISO格式时间字符串"  // 响应时间戳（可选）
}
```

**错误响应结构：**
```json
{
  "success": false,
  "error": "错误信息描述"
}
```

### 2.2 数据获取接口列表

#### 2.2.1 心率数据接口

**接口路径：** `GET /api/heartrate`

**请求参数：**
- `hours` (整数，可选，默认168)：获取最近N小时的数据（168小时=7天）
- `include_zero` (字符串，可选，默认"true")：是否包含心率为0的数据点
  - `"true"`: 包含所有数据（包括0值），确保横坐标连续无断档
  - `"false"`: 只返回有效数据（bpm > 0）

**响应数据格式：**
```json
{
  "success": true,
  "data": [
    {
      "timestamp": "2025-12-26T12:00:00",  // ISO格式时间字符串
      "bpm": 75,                            // 心率值（BPM）
      "hrId": 144                           // 心率数据ID（用于去重）
    },
    ...
  ],
  "count": 864,                            // 总数据条数
  "valid_count": 171,                      // 有效数据条数（bpm > 0）
  "timestamp": "2025-12-26T17:00:00"       // 响应时间戳
}
```

**重要说明：**
- `timestamp`字段必须是ISO 8601格式的字符串
- `bpm`字段可能为0（表示该时间点没有有效心率数据）
- `hrId`字段用于唯一标识每个数据点，用于去重

#### 2.2.2 HRV数据接口

**接口路径：** `GET /api/hrv`

**请求参数：**
- `hours` (整数，可选，默认168)：获取最近N小时的数据

**响应数据格式：**
```json
{
  "success": true,
  "data": [
    {
      "date": "2025-12-26T14:00:00",  // ISO格式时间字符串
      "hrv": 115,                      // HRV值
      "hrvId": 28,                     // HRV数据ID
      "secondInterval": 1800           // 数据采集间隔（秒），通常是1800秒（30分钟）
    },
    ...
  ],
  "count": 144,
  "timestamp": "2025-12-26T17:00:00"
}
```

**重要说明：**
- `date`字段是ISO格式时间字符串，但可能只有日期部分（如 `"2025-12-26"`）
- 如果date只有日期部分，前端需要使用 `hrvId` 和 `secondInterval` 计算实际时间
- `hrv`字段可能为0（表示该时间点没有有效HRV数据）
- `secondInterval`表示设备的数据采集间隔（通常是1800秒=30分钟），用于计算实际时间
- 时间计算公式：`实际时间 = 基准日期（00:00:00） + hrvId * secondInterval`

#### 2.2.3 压力数据接口

**接口路径：** `GET /api/stress`

**请求参数：**
- `hours` (整数，可选，默认168)：获取最近N小时的数据

**响应数据格式：**
```json
{
  "success": true,
  "data": [
    {
      "date": "2025-12-26T14:00:00",  // ISO格式时间字符串
      "stress": 45,                    // 压力值
      "stressId": 28,                  // 压力数据ID
      "secondInterval": 1800           // 数据采集间隔（秒），通常是1800秒（30分钟）
    },
    ...
  ],
  "count": 144,
  "timestamp": "2025-12-26T17:00:00"
}
```

**重要说明：**
- 格式与HRV数据类似
- `date`字段可能只有日期部分，需要使用 `stressId` 和 `secondInterval` 计算实际时间
- `stress`字段可能为0（表示该时间点没有有效压力数据）
- 时间计算公式：`实际时间 = 基准日期（00:00:00） + stressId * secondInterval`

#### 2.2.4 血氧数据接口

**接口路径：** `GET /api/blood-oxygen`

**请求参数：**
- `hours` (整数，可选，默认168)：获取最近N小时的数据

**响应数据格式：**
```json
{
  "success": true,
  "data": [
    {
      "date": "2025-12-26T01:00:00",  // ISO格式时间字符串
      "soa2": 98,                      // 血氧饱和度（%）
      "maxSoa2": 99,                   // 最大血氧值
      "minSoa2": 97,                   // 最小血氧值
      "soa2Type": 1,                   // 血氧类型（0=低氧, 1=正常, 2=偏高）
      "sourceType": 0,                 // 数据来源（0=定时数据, 1=手动测量）
      "device": "Qring"                // 设备名称
    },
    ...
  ],
  "count": 72,
  "timestamp": "2025-12-26T17:00:00"
}
```

**重要说明：**
- `soa2`字段是主要显示值，可能为0
- 血氧数据通常按小时记录（约1小时一条）

#### 2.2.5 活动数据接口

**接口路径：** `GET /api/daily-activity`

**请求参数：**
- `days` (整数，可选，默认30)：获取最近N天的数据

**响应数据格式：**
```json
{
  "success": true,
  "data": [
    {
      "day": "2025-12-26",            // 日期（YYYY-MM-DD格式）
      "totalStepCount": 1234,          // 总步数
      "runStepCount": 0,               // 跑步步数
      "calories": 5678,                // 卡路里
      "distance": 890,                 // 距离（米）
      "activeTime": 3600,              // 活动时长（秒）
      "happenDate": "2025-12-26 10:00:00"  // 发生时间
    },
    ...
  ],
  "count": 6,
  "timestamp": "2025-12-26T17:00:00"
}
```

**重要说明：**
- 活动数据按天汇总
- `happenDate`字段可能包含多个时间点（同一天可能有多个活动记录）

#### 2.2.6 睡眠数据接口

**接口路径：** `GET /api/sleep`

**请求参数：**
- `days` (整数，可选，默认30)：获取最近N天的数据

**响应数据格式：**
```json
{
  "success": true,
  "data": [
    {
      "date": "2025-12-25",           // 日期（YYYY-MM-DD格式）
      "sleepDuration": 28800,          // 睡眠时长（秒）
      "deepSleepDuration": 7200,      // 深度睡眠时长（秒）
      "lightSleepDuration": 18000,    // 浅度睡眠时长（秒）
      "remSleepDuration": 3600,        // REM睡眠时长（秒）
      "awakeDuration": 1800,          // 清醒时长（秒）
      "sleepStartTime": "2025-12-25T22:00:00",  // 睡眠开始时间
      "sleepEndTime": "2025-12-26T06:00:00"    // 睡眠结束时间
    },
    ...
  ],
  "count": 0,
  "timestamp": "2025-12-26T17:00:00"
}
```

**重要说明：**
- 睡眠数据按天汇总
- 如果某天没有睡眠记录，可能返回空数组

#### 2.2.7 运动记录数据接口

**接口路径：** `GET /api/exercise`

**请求参数：**
- `hours` (整数，可选，默认168)：获取最近N小时的数据

**响应数据格式：**
```json
{
  "success": true,
  "data": [
    {
      "startTime": "2025-12-26T10:00:00",  // 运动开始时间
      "type": 0,                            // 运动类型（0=跑步, 1=骑行, 2=举重, 3=步行）
      "lastSeconds": 3600,                  // 运动时长（秒）
      "steps": 5000,                        // 步数
      "meters": 4000,                       // 距离（米）
      "calories": 300                       // 卡路里
    },
    ...
  ],
  "count": 0,
  "timestamp": "2025-12-26T17:00:00"
}
```

#### 2.2.8 运动+数据接口

**接口路径：** `GET /api/sport-plus`

**请求参数：**
- `hours` (整数，可选，默认168)：获取最近N小时的数据

**响应数据格式：**
```json
{
  "success": true,
  "data": [
    {
      "startTime": "2025-12-26T10:00:00",  // 运动开始时间
      "exerciseType": 0,                   // 运动类型
      "duration": 3600,                     // 运动时长（秒）
      "distance": 5000,                     // 距离（米）
      "calories": 400,                      // 卡路里
      "averageHeartRate": 140,              // 平均心率
      "maxHeartRate": 165,                  // 最大心率
      "locations": [...]                    // GPS位置数据（如果有）
    },
    ...
  ],
  "count": 0,
  "timestamp": "2025-12-26T17:00:00"
}
```

#### 2.2.9 久坐提醒数据接口

**接口路径：** `GET /api/sedentary`

**请求参数：**
- `hours` (整数，可选，默认168)：获取最近N小时的数据

**响应数据格式：**
```json
{
  "success": true,
  "data": [
    {
      "date": "2025-12-26T04:15:00",  // 提醒时间
      "endTime": "2025-12-26T04:15:00",  // 结束时间
      "duration": 255,                 // 久坐时长（秒）
      "type": 128                      // 提醒类型
    },
    ...
  ],
  "count": 68,
  "timestamp": "2025-12-26T17:00:00"
}
```

#### 2.2.10 统计数据接口

**接口路径：** `GET /api/stats`

**请求参数：** 无

**响应数据格式：**
```json
{
  "success": true,
  "data": {
    "heartrate_count": 864,           // 心率数据总数
    "hrv_count": 144,                 // HRV数据总数
    "stress_count": 144,               // 压力数据总数
    "blood_oxygen_count": 72,         // 血氧数据总数
    "activity_count": 6,               // 活动数据总数
    "sleep_count": 0,                  // 睡眠数据总数
    "exercise_count": 0,               // 运动记录总数
    "sport_plus_count": 0,             // 运动+数据总数
    "sedentary_count": 68,             // 久坐提醒总数
    "manual_measurements_count": 419,  // 主动测量数据总数
    "last_update": {                   // 各数据类型最后更新时间
      "heartrate": "2025-12-26T16:15:00",
      "hrv": "2025-12-26T16:15:00",
      "stress": "2025-12-26T16:15:00",
      "blood_oxygen": "2025-12-26T16:15:00",
      "activity": "2025-12-26T16:15:00",
      "sleep": null,
      "exercise": null,
      "sport_plus": null,
      "sedentary": "2025-12-26T16:15:00",
      "manual_measurements": "2025-12-26T16:15:00"
    }
  },
  "timestamp": "2025-12-26T17:00:00"
}
```

#### 2.2.11 用户信息接口

**接口路径：** `GET /api/user-info`

**请求参数：** 无

**响应数据格式：**
```json
{
  "success": true,
  "data": {
    "timeFormat": 24,                  // 时间格式（12/24小时制）
    "metricSystem": true,              // 是否使用公制单位
    "gender": 1,                       // 性别（0=未知, 1=男, 2=女）
    "age": 30,                         // 年龄
    "height": 175,                     // 身高（厘米）
    "weight": 70,                      // 体重（公斤）
    "sbpBase": 120,                    // 收缩压基准值
    "dbpBase": 80,                     // 舒张压基准值
    "hrAlarmValue": 100                // 心率报警值
  },
  "timestamp": "2025-12-26T17:00:00"
}
```

#### 2.2.12 目标设置接口

**接口路径：** `GET /api/target-info`

**请求参数：** 无

**响应数据格式：**
```json
{
  "success": true,
  "data": {
    "stepTarget": 10000,               // 步数目标
    "calorieTarget": 2000,             // 卡路里目标
    "distanceTarget": 8000,            // 距离目标（米）
    "sportDurationTarget": 3600,       // 运动时长目标（秒）
    "sleepDurationTarget": 28800       // 睡眠时长目标（秒）
  },
  "timestamp": "2025-12-26T17:00:00"
}
```

#### 2.2.13 主动测量数据接口

**接口路径：** `GET /api/manual-measurements`

**请求参数：**
- `hours` (整数，可选，默认24)：获取最近N小时的主动测量数据
- `type` (字符串，可选)：过滤类型（"manual"=单次测量, "realtime"=实时监测, "one_key"=一键体测）

**响应数据格式：**
```json
{
  "success": true,
  "data": [
    {
      "type": "manual_heartrate",      // 测量类型
      "heartRate": 75,                  // 心率值（如果适用）
      "bloodOxygen": null,              // 血氧值（如果适用）
      "stress": null,                   // 压力值（如果适用）
      "hrv": null,                      // HRV值（如果适用）
      "timestamp": "2025-12-26T16:00:00",  // 测量时间
      "measurementType": "manual"       // 测量方式（manual/realtime/one_key）
    },
    ...
  ],
  "count": 419,
  "timestamp": "2025-12-26T17:00:00"
}
```

**重要说明：**
- `type`字段可能的值：
  - `"manual_heartrate"`: 单次心率测量
  - `"manual_blood_oxygen"`: 单次血氧测量
  - `"manual_stress"`: 单次压力测量
  - `"manual_hrv"`: 单次HRV测量
  - `"realtime_heartrate"`: 实时心率监测
  - `"one_key_measure"`: 一键体测（可能包含多种数据）

### 2.3 错误处理要求

**网络错误：**
- 请求超时：显示友好的错误提示
- 网络断开：显示网络连接错误
- 服务器错误（500）：显示服务器错误提示

**数据错误：**
- 数据格式错误：在控制台输出警告，不中断应用运行
- 数据为空：显示"暂无数据"提示，不显示错误

**错误提示要求：**
- 使用用户友好的中文提示
- 不显示技术性错误信息给最终用户
- 在浏览器控制台输出详细错误信息（用于调试）

### 2.4 请求频率要求

**自动刷新：**
- 默认每30秒自动刷新一次所有数据
- 用户可以选择开启/关闭自动刷新
- 刷新时显示加载状态（可选）

**手动刷新：**
- 提供"刷新数据"按钮
- 点击后立即获取最新数据
- 刷新过程中禁用按钮，显示加载动画

### 2.5 时间范围参数说明

**hours参数：**
- 用于按小时数获取数据（如心率、HRV、压力、血氧、运动等）
- 前端计算：`hours = timeRange * 24`（timeRange是天数）
- 例如：选择"7天"时，传递`hours=168`

**days参数：**
- 用于按天数获取数据（如活动、睡眠）
- 直接使用timeRange值
- 例如：选择"7天"时，传递`days=7`

---

**文档说明：** 本文档详细说明了所有API接口的请求参数和响应格式。前端开发时必须严格按照此规范实现数据获取逻辑。

