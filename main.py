import httpx
from urllib.parse import quote # 导入用于URL转义的函数
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

# --- CSS部分已修正 ---
WEATHER_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            /* --- 修正点 1: 移除外边距，并设置为内联块元素以实现尺寸自适应 --- */
            margin: 0;
            display: inline-block; 
            
            font-family: -apple-system, 'Noto Sans SC', 'Helvetica Neue', Helvetica, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
            background: linear-gradient(135deg, {{ data.weather.weather_colors[0] | default('#4891FF') }}, {{ data.weather.weather_colors[1] | default('#9AD2F9') }});
            color: white;
            padding: 20px;
            width: 420px;
            border-radius: 15px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.25);
            box-sizing: border-box;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 1px solid rgba(255, 255, 255, 0.3);
            padding-bottom: 10px;
            margin-bottom: 15px;
        }
        .location { font-size: 26px; font-weight: bold; }
        .updated { font-size: 13px; opacity: 0.8; }
        .main-weather {
            display: flex;
            align-items: center;
            justify-content: space-around;
            padding: 10px 0;
        }
        .temperature { font-size: 64px; font-weight: bold; }
        .condition { text-align: center; }
        .condition img { width: 60px; height: 60px; }
        .condition span { display: block; font-size: 18px; margin-top: 5px; font-weight: 500; }
        .details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            font-size: 14px;
            background: rgba(0, 0, 0, 0.15);
            padding: 15px;
            border-radius: 10px;
            margin-top: 15px;
        }
        .detail-item { display: flex; align-items: center; }
        .detail-item strong { margin-right: 8px; opacity: 0.9; }
        .indices { margin-top: 20px; }
        .indices h3 {
            font-size: 16px; margin-top:0; margin-bottom: 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.3);
            padding-bottom: 5px; font-weight: bold;
        }
        .index-item { font-size: 14px; margin-bottom: 8px; line-height: 1.5; }
        .index-item strong { font-weight: bold; }
    </style>
</head>
<body>
    <div class="header">
        <span class="location">{{ data.location.name }}</span>
        <span class="updated">更新于 {{ data.weather.updated.split(' ')[1] }}</span>
    </div>

    <div class="main-weather">
        <span class="temperature">{{ data.weather.temperature }}°</span>
        <div class="condition">
            <img src="{{ data.weather.weather_icon }}" alt="{{ data.weather.condition }}">
            <span>{{ data.weather.condition }}</span>
        </div>
    </div>

    <div class="details">
        <div class="detail-item"><strong>湿度</strong> {{ data.weather.humidity }}%</div>
        <div class="detail-item"><strong>风力</strong> {{ data.weather.wind_direction }} {{ data.weather.wind_power }}级</div>
        <div class="detail-item"><strong>空气</strong> {{ data.air_quality.quality }} ({{ data.air_quality.aqi }})</div>
        <div class="detail-item"><strong>紫外线</strong> {{ indices.ultraviolet.level }}</div>
    </div>
    
    <div class="indices">
        <h3>生活指数</h3>
        <div class="index-item">
            <strong>穿衣建议:</strong> {{ indices.clothes.description }}
        </div>
        <div class="index-item">
            <strong>感冒风险:</strong> {{ indices.cold.description }}
        </div>
    </div>
</body>
</html>
"""

def find_life_index(indices, key):
    for index in indices:
        if index['key'] == key:
            return index
    return {"level": "暂无", "description": "暂无数据"}

@register(
    "weather", 
    "kuank", 
    "通过指令查询实时天气信息", 
    "1.1.5", 
    "https://github.com/kuankqaq/astrbot_weather"
)
class WeatherPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        logger.info("天气查询插件加载成功。")

    @filter.command("天气")
    async def get_weather(self, event: AstrMessageEvent, city: str = None):
        if not city:
            yield event.plain_result("请输入要查询的城市，例如：/天气 北京")
            return

        logger.info(f"用户输入城市: {city}")
        encoded_city = quote(city)
url = f"https://60s.viki.moe/v2/weather?query={encoded_city}&encoding=json"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10)
                response.raise_for_status()

            weather_data = response.json()
            logger.info(f"API返回: {weather_data}")

            if weather_data.get("code") != 200:
                error_message = weather_data.get("message", "未知错误")
                yield event.plain_result(f"查询「{city}」天气失败：{error_message}")
                return

            data = weather_data["data"]
            logger.info(f"API返回城市: {data.get('location', {}).get('name', '未知')} (用户输入: {city})")
            render_context = {
                "data": data,
                "indices": {
                    "clothes": find_life_index(data['life_indices'], 'clothes'),
                    "cold": find_life_index(data['life_indices'], 'cold'),
                    "ultraviolet": find_life_index(data['life_indices'], 'ultraviolet'),
                }
            }

            image_url = await self.html_render(WEATHER_TEMPLATE, render_context)
            yield event.image_result(image_url)

        except httpx.RequestError as e:
            logger.error(f"天气API请求失败: {e}")
            yield event.plain_result(f"网络请求失败，无法查询「{city}」的天气。")
        except Exception as e:
            logger.error(f"处理天气数据时发生未知错误: {e}")
            yield event.plain_result(f"处理「{city}」的天气数据时发生了一个内部错误。")